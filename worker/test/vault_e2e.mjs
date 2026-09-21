/* NEEDS-DECISION #56 — the vault's LIFECYCLE, against a real Workers runtime.
 *
 * The unit tests beside this file cover the gates (vaultKey.ts) and run in
 * `npm test`. This one covers what only the runtime can answer: that the
 * record reads back, that one token cannot reach another's object, that a
 * delete is verifiably gone, that extra fields in the body never reach
 * storage, and that the burst brake engages. It is NOT part of `npm test`
 * (which globs `*.test.ts`) because it needs a server; it is here so the
 * claims made about it are reproducible by anyone rather than a past-tense
 * assertion about a run nobody else can repeat. Adversarial review, L6.
 *
 * Run it:
 *     cd worker
 *     npx wrangler dev --local --port 8793 --var GEMINI_API_KEY:unused --var TURNSTILE_SECRET_KEY:unused
 *     node test/vault_e2e.mjs
 *
 * No Cloudflare credentials are needed — local mode runs the real Durable
 * Object, real SQLite, real alarms and a real rate limiter.
 *
 * Each scenario uses its own CF-Connecting-IP so the per-IP burst brake
 * (5/60s) does not make one scenario's requests fail another's assertions.
 * The last scenario deliberately shares one, to show the brake engaging.
 *
 * To watch the EXPIRY delete something rather than take the date on trust,
 * set RETENTION_DAYS in ../src/vaultKey.ts to `3 / 86400`, restart wrangler,
 * run `node test/vault_expiry.mjs`, and put it back.
 */
const BASE = 'http://127.0.0.1:8793/profile'
const ORIGIN = 'http://localhost:4173'
let pass = 0, fail = 0
const ok = (cond, msg) => { if (cond) { pass++; console.log(`PASS  ${msg}`) } else { fail++; console.log(`FAIL  ${msg}`) } }

function mint() {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  return Buffer.from(bytes).toString('base64url')
}

/* A fresh IP block per run. The burst brake is 5 requests per 60 seconds per
 * IP, so re-running this file inside a minute failed half its assertions on
 * the previous run's leftovers — a red suite that says nothing about the
 * code. Each run now gets its own buckets. */
const RUN = Math.floor(Math.random() * 250) + 1
const ipOf = (n) => `10.${RUN}.0.${n}`
async function call(method, { token, body, ip = ipOf(1), origin = ORIGIN } = {}) {
  const headers = { 'CF-Connecting-IP': ip }
  if (origin) headers['Origin'] = origin
  if (token) headers['x-compass-vault-key'] = token
  if (body !== undefined) headers['content-type'] = 'application/json'
  const res = await fetch(BASE, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  let json = null
  try { json = await res.json() } catch { /* non-JSON, e.g. a 404 */ }
  return { status: res.status, json }
}

// ---------------------------------------------------------------- lifecycle
{
  const token = mint()
  const ip = ipOf(10)
  const saved = await call('POST', { token, ip, body: { occupation: 'isco08:2512', yearsProfessional: 7 } })
  ok(saved.status === 200 && saved.json?.ok === true, `save returns ok (${saved.status})`)
  ok(saved.json?.retentionDays === 30, `save states the retention period it applied (${saved.json?.retentionDays})`)
  const exp = saved.json?.record?.expiresAt - saved.json?.record?.savedAt
  ok(Math.abs(exp - 30 * 86400000) < 2000, `the record really expires 30 days out (${Math.round(exp / 86400000)} days)`)

  const read = await call('GET', { token, ip })
  ok(read.json?.record?.occupation === 'isco08:2512' && read.json?.record?.yearsProfessional === 7,
    'the record reads back exactly what was saved')
  ok(Object.keys(read.json?.record ?? {}).sort().join(',') === 'expiresAt,occupation,savedAt,yearsProfessional',
    `the record holds ONLY the two values plus its own dates (${Object.keys(read.json?.record ?? {}).sort().join(',')})`)

  const del = await call('DELETE', { token, ip })
  ok(del.json?.had === true && del.json?.gone === true, 'delete reports that something was there and is now gone')

  const after = await call('GET', { token, ip })
  ok(after.status === 200 && after.json?.record === null, 'and a fresh read finds nothing — verifiably gone, not assumed')
}

// ------------------------------------------------- one token cannot reach another
{
  const mine = mint(), theirs = mint()
  const ip = ipOf(11)
  await call('POST', { token: mine, ip, body: { occupation: 'isco08:2512', yearsProfessional: 9 } })
  const peek = await call('GET', { token: theirs, ip })
  ok(peek.json?.record === null, 'a different token reaches a different object, and finds nothing')
  const mineAgain = await call('GET', { token: mine, ip })
  ok(mineAgain.json?.record?.yearsProfessional === 9, 'and the original token still finds its own record')
  await call('DELETE', { token: mine, ip })
}

// ------------------------------------------------------ the closed payload
{
  const token = mint()
  const ip = ipOf(12)
  const r = await call('POST', { token, ip, body: {
    occupation: 'isco08:2512', yearsProfessional: 4,
    cvText: 'Jane Doe, 12 Example Street, jane@example.com',
    evidence: 'three roles titled backend engineer', salary_eur: 400000,
  } })
  ok(r.status === 200, 'a body carrying extra fields is accepted, not rejected')
  const read = await call('GET', { token, ip })
  const blob = JSON.stringify(read.json)
  ok(!blob.includes('Jane Doe') && !blob.includes('example.com') && !blob.includes('400000')
     && !blob.includes('backend engineer'),
    'and NONE of the extra fields survive into the store')
  await call('DELETE', { token, ip })
}

// --------------------------------------------------------------- the gates
{
  const ip = ipOf(13)
  const short = await call('GET', { token: 'a'.repeat(20), ip })
  ok(short.json?.code === 'malformed_input', 'a short token is refused')
  const traversal = await call('GET', { token: '../../global', ip })
  ok(traversal.json?.code === 'malformed_input', 'a token shaped like a path is refused')
  const none = await call('GET', { ip })
  ok(none.json?.code === 'malformed_input', 'no token at all is refused')
  const badOrigin = await call('GET', { token: mint(), ip, origin: 'https://evil.example' })
  ok(badOrigin.json?.code === 'origin_forbidden', 'another origin is refused')
  const noOrigin = await call('GET', { token: mint(), ip, origin: null })
  ok(noOrigin.json?.code === 'origin_forbidden', 'no origin at all is refused')
}

// -------------------------------------------------------- out-of-range save
{
  const token = mint(), ip = ipOf(14)
  const neg = await call('POST', { token, ip, body: { occupation: null, yearsProfessional: -1 } })
  ok(neg.json?.code === 'malformed_input', 'a negative years figure is refused, not clamped')
  const huge = await call('POST', { token, ip, body: { occupation: 'x'.repeat(200), yearsProfessional: 5 } })
  ok(huge.json?.code === 'malformed_input', 'an oversized occupation is refused')
  const empty = await call('GET', { token, ip })
  ok(empty.json?.record === null, 'and neither refusal left anything behind')
}

// ------------------------------- the fixes an adversarial review prompted
{
  const token = mint(), ip = ipOf(15)
  // L3 — the payload is closed by VALUE, not only by field name.
  const freeText = await call('POST', { token, ip, body: { occupation: 'nurse, 12 Example Street', yearsProfessional: 3 } })
  ok(freeText.json?.code === 'malformed_input', 'an occupation that is not a registry key is refused')

  // M3 — a DELETE against a token that never stored anything says so,
  // rather than reporting a success it did not perform.
  const del = await call('DELETE', { token, ip })
  ok(del.json?.had === false && del.json?.gone === true,
    'deleting a token that never stored anything reports had:false, not a phantom success')

  // L5 — a response that varies by a header and says nothing about caching
  // is how a header-borne capability leaks through a shared cache.
  const res = await fetch(BASE, { headers: { Origin: ORIGIN, 'CF-Connecting-IP': ip, 'x-compass-vault-key': token } })
  ok((res.headers.get('cache-control') || '').includes('no-store'),
    `the read is marked no-store (${res.headers.get('cache-control')})`)
  ok((res.headers.get('vary') || '').toLowerCase().includes('x-compass-vault-key'),
    `and varies by the key header (${res.headers.get('vary')})`)
}

// --------------------------------------------------------- the burst brake
{
  const ip = ipOf(99)
  const codes = []
  for (let i = 0; i < 8; i++) codes.push((await call('GET', { token: mint(), ip })).json?.code ?? 'ok')
  ok(codes.includes('rate_limited'), `the burst brake engages on the new endpoint (${codes.join(',')})`)
}

console.log(`\n${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
