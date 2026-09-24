/* Package 47, Tier 1 — does the Worker this build will call have a vault?
 *
 * The site must never offer to keep a profile when the Worker behind it has
 * no /profile route, and it must not ask from the reader's browser: package
 * 22's second property is that nothing is sent until the reader confirms, and
 * a probe on page load would break it. So the Deploy workflow asks instead,
 * once per build, and bakes the answer into the bundle as VITE_CV_VAULT.
 *
 * THE QUESTION IT ASKS CANNOT CREATE OR READ ANYTHING. A plain GET /profile
 * with no Origin header. worker/src/index.ts's handleVault() checks the Origin
 * first, before the rate limiter, before the read counter, before storage,
 * and answers 403 {"ok":false,"code":"origin_forbidden",...}. A Worker built
 * before package 45 has no /profile route and falls through to its 404,
 * body `not found`. So the answer says which code is deployed.
 *
 * AND A CONTROL, so that answer means what it seems to. A random path must
 * still get the fall-through 404. If some later Worker checked the Origin for
 * every path before routing, /profile would say origin_forbidden whether or
 * not the route existed; the control catches exactly that and turns the flag
 * off rather than on.
 *
 * FAIL CLOSED. Only this combination prints `on`: /profile -> 403 with the
 * vault's own JSON refusal, AND the control -> 404. Anything else — the old
 * 404, an HTML 403 from Cloudflare, a 5xx, a redirect, unreadable JSON, a
 * network error, a timeout — prints `off`. What it cannot tell: whether the
 * Durable Object behind the route works. Only a request that passes the
 * Origin check reaches storage, and this one is built not to.
 *
 *   node scripts/probe_vault.mjs <worker-base-url>   stdout: on | off
 *   node scripts/probe_vault.mjs --self-test
 *
 * Node's http client adds no Origin header of its own; the only headers sent
 * are the two named in `ask()`.
 */
import { request as httpsRequest } from 'node:https'
import { request as httpRequest } from 'node:http'
import { randomBytes } from 'node:crypto'

const TIMEOUT_MS = 10_000

/** One GET, no Origin. Resolves to { status, body } or { error }. Never throws. */
export function ask(url) {
  return new Promise((resolve) => {
    let u
    try { u = new URL(url) } catch { return resolve({ error: `not a URL: ${url}` }) }
    const req = (u.protocol === 'http:' ? httpRequest : httpsRequest)(u, {
      method: 'GET',
      headers: { 'user-agent': 'cs-compass-deploy-probe', accept: 'application/json' },
    }, (res) => {
      let body = ''
      res.setEncoding('utf8')
      res.on('data', (d) => { if (body.length < 4096) body += d })
      res.on('end', () => resolve({ status: res.statusCode, body }))
      res.on('error', (e) => resolve({ error: String(e.message || e) }))
    })
    req.setTimeout(TIMEOUT_MS, () => req.destroy(new Error(`timed out after ${TIMEOUT_MS}ms`)))
    req.on('error', (e) => resolve({ error: String(e.message || e) }))
    req.end()
  })
}

/** The decision, separate from the network so it can be tested on its own.
 *  `profile` and `control` are what ask() resolved to. */
export function decide(profile, control) {
  if (profile.error) return { on: false, why: `GET /profile failed: ${profile.error}` }
  if (profile.status !== 403) {
    const old = profile.status === 404 && /not found/i.test(profile.body)
    return { on: false, why: `GET /profile answered ${profile.status}${old ? ' "not found" — the Worker has no vault route (the code before package 45)' : ''}` }
  }
  let j = null
  try { j = JSON.parse(profile.body) } catch { /* handled below */ }
  if (!j || j.ok !== false || j.code !== 'origin_forbidden') {
    return { on: false, why: 'GET /profile answered 403, but not with the vault\'s own refusal (origin_forbidden JSON)' }
  }
  if (control.error) return { on: false, why: `the control request failed: ${control.error}` }
  if (control.status !== 404) {
    return { on: false, why: `the control path answered ${control.status}, not 404 — the Origin refusal is not specific to /profile, so it proves nothing about the route` }
  }
  return { on: true, why: 'GET /profile answered the vault\'s own origin_forbidden, and an unknown path still 404s — the vault is deployed' }
}

async function askTwice(url) {
  const first = await ask(url)
  if (!first.error) return first
  // One retry for a network error or timeout only; a definite answer is final.
  await new Promise((r) => setTimeout(r, 3000))
  return ask(url)
}

function selfTest() {
  const refusal = JSON.stringify({ ok: false, code: 'origin_forbidden', message: 'this origin is not permitted to call this endpoint' })
  const cases = [
    ['the old Worker', { status: 404, body: 'not found' }, { status: 404, body: 'not found' }, false],
    ['the vault deployed', { status: 403, body: refusal }, { status: 404, body: 'not found' }, true],
    ['a global Origin check, route or not', { status: 403, body: refusal }, { status: 403, body: refusal }, false],
    ['a Cloudflare HTML 403', { status: 403, body: '<!DOCTYPE html><title>Access denied</title>' }, { status: 404, body: 'not found' }, false],
    ['403 JSON with another code', { status: 403, body: JSON.stringify({ ok: false, code: 'turnstile_missing' }) }, { status: 404, body: '' }, false],
    ['a 200', { status: 200, body: '{"ok":true}' }, { status: 404, body: '' }, false],
    ['a 5xx', { status: 503, body: 'error code: 1102' }, { status: 404, body: '' }, false],
    ['a redirect', { status: 302, body: '' }, { status: 404, body: '' }, false],
    ['a network error', { error: 'getaddrinfo ENOTFOUND' }, { status: 404, body: '' }, false],
    ['a timeout', { error: 'timed out after 10000ms' }, { status: 404, body: '' }, false],
    ['the control times out', { status: 403, body: refusal }, { error: 'timed out after 10000ms' }, false],
  ]
  let bad = 0
  for (const [name, p, c, want] of cases) {
    const got = decide(p, c).on
    const ok = got === want
    if (!ok) bad++
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}: ${got ? 'on' : 'off'}`)
  }
  console.log(bad ? `${bad} case(s) FAILED` : `ALL ${cases.length} PROBE CASES PASS — only the vault's own refusal plus a 404 control turns it on`)
  process.exitCode = bad ? 1 : 0
}

if (process.argv[2] === '--self-test') {
  selfTest()
} else {
  const base = (process.argv[2] ?? '').replace(/\/+$/, '')
  if (!base) {
    console.error('usage: node scripts/probe_vault.mjs <worker-base-url> | --self-test')
    console.log('off')
  } else {
    const profile = await askTwice(`${base}/profile`)
    const control = await askTwice(`${base}/no-such-route-${randomBytes(6).toString('hex')}`)
    const { on, why } = decide(profile, control)
    console.error(`vault probe: ${why}`)
    console.log(on ? 'on' : 'off')
  }
}
