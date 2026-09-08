/* Lighthouse over every route, plus throttled mobile for /openings.
 *
 * On the URL, and why this file exists at all: Git Bash rewrites a bare
 * `#/route` argument into a Windows path, and a package 41 Lighthouse run
 * silently audited a 404 because of it — the score was excellent and it was
 * measuring the not-found page. Here the URL is built in Node, quoted, and
 * handed to npx as its own argv entry; and every report is checked for a
 * not-found finalUrl before its score is believed, because the score is not
 * the thing that tells you the run was pointed at the right page.
 *
 * (spawn needs shell:true on Windows — npx is a .cmd and cannot be exec'd
 * directly — hence the quoting rather than a bare argument array.)
 *
 * Reports the score AND the TBT for each route, because a performance number
 * measured on a busy machine is not evidence of anything: TBT is what says
 * whether the machine was quiet while it measured.
 *
 *   node scripts/tests/lighthouse_gate.mjs
 *   LH_ONLY=openings node scripts/tests/lighthouse_gate.mjs
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const ONLY = new Set((process.env.LH_ONLY ?? '').split(',').map((s) => s.trim()).filter(Boolean))
const PERF_MIN = 90
const OTHER_MIN = 95

const ROUTES = [
  ['home', ''],
  ['compare', '#/compare?places=oslo,copenhagen,berlin'],
  ['work', '#/work'],
  ['openings', '#/openings'],
  ['data', '#/data'],
  ['postings-seed', '#/data/postings-seed'],
  ['city', '#/city/berlin'],
  ['country', '#/country/AE'],
  ['explore-money', '#/explore/money'],
  ['explore-visa', '#/explore/visas'],
  ['explore-jobs', '#/explore/jobs'],
  ['explore-housing', '#/explore/housing'],
  ['explore-people', '#/explore/people'],
  ['explore-life', '#/explore/life'],
]

const NPX = process.platform === 'win32' ? 'npx.cmd' : 'npx'
/* A URL containing '#' must survive the shell as ONE argument. Quoting it
 * here is what stops cmd.exe truncating at the fragment — the same class of
 * defect as Git Bash rewriting '#/route' into a path, which made a package 41
 * run audit a 404 and report an excellent score for it. */
const quote = (a) => (/[\s#&^|<>]/.test(a) ? `"${a}"` : a)

const OUT = join(tmpdir(), 'lh-p43')
mkdirSync(OUT, { recursive: true })

const run = (url, file, mobile) => new Promise((resolve, reject) => {
  const args = [
    'lighthouse', url,
    '--output=json', `--output-path=${file}`,
    '--quiet', '--chrome-flags=--headless=new --no-sandbox',
    '--only-categories=performance,accessibility,best-practices,seo',
  ]
  if (!mobile) args.push('--preset=desktop')
  // shell:true on Windows, because npx is a .cmd and spawn() cannot exec one
  // directly (EINVAL). The URL is still passed as its own argv entry and
  // quoted below, so nothing rewrites the '#'.
  const p = spawn(NPX, args.map(quote), { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true, shell: true })
  let err = ''
  p.stderr.on('data', (d) => { err += d })
  p.on('error', reject)
  p.on('close', (code) => {
    /* A non-zero exit is not automatically a failed audit. chrome-launcher
     * deletes its temp profile AFTER writing the report and throws EPERM doing
     * it on Windows often enough to matter — the measurement is finished and
     * on disk by then. So the report file is the evidence: if it exists and
     * parses, the run succeeded and the teardown is noted; if it does not,
     * the run failed and says why. This is the masked-exit-code trap run
     * backwards, and believing the exit code either way is the mistake. */
    if (existsSync(file)) {
      try {
        JSON.parse(readFileSync(file, 'utf8'))
        if (code !== 0) console.log(`        (lighthouse exited ${code} after writing the report: ${err.trim().slice(0, 90)})`)
        return resolve()
      } catch { /* fall through: a half-written report is a failed run */ }
    }
    reject(new Error(`lighthouse exit ${code}, no usable report: ${err.slice(-600)}`))
  })
})

const read = (file) => {
  const r = JSON.parse(readFileSync(file, 'utf8'))
  const s = (k) => Math.round((r.categories[k]?.score ?? 0) * 100)
  return {
    finalUrl: r.finalUrl ?? r.requestedUrl,
    perf: s('performance'),
    a11y: s('accessibility'),
    bp: s('best-practices'),
    seo: s('seo'),
    tbt: Math.round(r.audits['total-blocking-time']?.numericValue ?? -1),
    cls: +(r.audits['cumulative-layout-shift']?.numericValue ?? -1).toFixed(4),
    lcp: Math.round(r.audits['largest-contentful-paint']?.numericValue ?? -1),
  }
}

const rows = []
let fails = 0
for (const [name, route] of ROUTES) {
  if (ONLY.size && !ONLY.has(name)) continue
  const file = join(OUT, `${name}.json`)
  rmSync(file, { force: true })
  /* One retry. Chrome occasionally dies on launch on a machine that has been
   * running headless browsers all session; that is a fact about the runner,
   * not about the page, and a sweep that aborts on it measures nothing. A
   * SECOND failure is reported as a failure, never skipped. */
  try {
    await run(BASE + route, file, false)
  } catch (e) {
    console.log(`  ....  ${name}: ${String(e.message).slice(0, 120)} — retrying once`)
    await run(BASE + route, file, false)
  }
  const m = read(file)
  // The trap this script exists for: a 404 scores beautifully.
  const bad404 = /no-such|not-found/.test(m.finalUrl)
  const pass = m.perf >= PERF_MIN && m.a11y >= OTHER_MIN && m.bp >= OTHER_MIN && m.seo >= OTHER_MIN && !bad404
  if (!pass) fails++
  rows.push({ name, ...m, pass })
  console.log(`  ${pass ? 'PASS' : 'FAIL'}  ${name.padEnd(16)} perf ${String(m.perf).padStart(3)}  a11y ${m.a11y}  bp ${m.bp}  seo ${m.seo}   TBT ${String(m.tbt).padStart(4)}ms  CLS ${m.cls}  LCP ${m.lcp}ms`)
}

if (!ONLY.size || ONLY.has('openings')) {
  const file = join(OUT, 'openings-mobile.json')
  rmSync(file, { force: true })
  await run(`${BASE}#/openings`, file, true)
  const m = read(file)
  const pass = m.perf >= PERF_MIN && m.a11y >= OTHER_MIN && m.bp >= OTHER_MIN && m.seo >= OTHER_MIN
  if (!pass) fails++
  console.log(`\n  ${pass ? 'PASS' : 'FAIL'}  openings (THROTTLED MOBILE) perf ${m.perf}  a11y ${m.a11y}  bp ${m.bp}  seo ${m.seo}   TBT ${m.tbt}ms  CLS ${m.cls}  LCP ${m.lcp}ms`)
}

console.log(`\n${rows.length + (ONLY.size ? 0 : 1)} audits, ${fails} below the floor `
  + `(performance >= ${PERF_MIN}, everything else >= ${OTHER_MIN})`)
console.log(`raw reports in ${OUT}`)
process.exit(fails ? 1 : 0)
