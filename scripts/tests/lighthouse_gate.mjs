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
 * What is enforced (#86, ruled in package 47 — the full reasoning is above the
 * throttled-mobile block below):
 *   desktop, every route    performance >= 90, TBT <= 150ms, the rest >= 95
 *   throttled mobile,       median LCP <= 2500ms and median CLS <= 0.1 over
 *   /openings               five runs, the rest >= 95; its performance score
 *                           and TBT are printed, NOT enforced
 *
 *   node scripts/tests/lighthouse_gate.mjs
 *   LH_ONLY=openings node scripts/tests/lighthouse_gate.mjs
 *   LH_MOBILE_RUNS=9 LH_ONLY=openings node scripts/tests/lighthouse_gate.mjs
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const ONLY = new Set((process.env.LH_ONLY ?? '').split(',').map((s) => s.trim()).filter(Boolean))
const PERF_MIN = 90
const OTHER_MIN = 95
/* Lighthouse 13's own "good" control points (each metric's p10: where its
 * score drops below 0.9), read from the reports' scoringOptions rather than
 * remembered. The measured distributions they are set against are in the
 * comment above the throttled-mobile block. */
const DESKTOP_TBT_MAX = 150
const MOBILE_LCP_MAX = 2500
const MOBILE_CLS_MAX = 0.1

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
  /* 'visa', not 'visas' (package 46). The theme key is `visa`, and Explore
   * answers an unknown key with Money — so this row audited Money a second
   * time for as long as it has existed, with a clean score and a real-looking
   * URL that the not-found check below cannot catch. Weather ('climate') was
   * not in the list at all. */
  ['explore-visa', '#/explore/visa'],
  ['explore-jobs', '#/explore/jobs'],
  ['explore-housing', '#/explore/housing'],
  ['explore-people', '#/explore/people'],
  ['explore-life', '#/explore/life'],
  ['explore-climate', '#/explore/climate'],
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
    /* A report can exist, parse, and have measured nothing: Chrome showing an
     * interstitial because the server is down writes a report with a
     * runtimeError and -1 for every metric. -1 passes "LCP <= 2500", so both
     * rules below fail any such run by name rather than trusting a category
     * score to happen to catch it (package 47 found this by running the new
     * mobile rule against a dead server). */
    error: r.runtimeError?.code ?? null,
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
  /* TBT has its own ceiling here, not only its 30% share of the composite
   * (#86): with every other metric perfect, a route at about 270ms still
   * rounded to 90 and passed. This line is what lets the mobile gate stop
   * enforcing its composite — see the comment above that block. */
  const why = [
    (m.error || m.tbt < 0) && `measured nothing (${m.error ?? 'no TBT'})`,
    m.perf < PERF_MIN && `performance < ${PERF_MIN}`,
    m.tbt > DESKTOP_TBT_MAX && `TBT > ${DESKTOP_TBT_MAX}ms`,
    (m.a11y < OTHER_MIN || m.bp < OTHER_MIN || m.seo < OTHER_MIN) && `a category < ${OTHER_MIN}`,
    bad404 && `audited a not-found page (${m.finalUrl})`,
  ].filter(Boolean)
  const pass = why.length === 0
  if (!pass) fails++
  rows.push({ name, ...m, pass })
  console.log(`  ${pass ? 'PASS' : 'FAIL'}  ${name.padEnd(16)} perf ${String(m.perf).padStart(3)}  a11y ${m.a11y}  bp ${m.bp}  seo ${m.seo}   TBT ${String(m.tbt).padStart(4)}ms  CLS ${m.cls}  LCP ${m.lcp}ms${pass ? '' : `   <- ${why.join('; ')}`}`)
}

/* THE THROTTLED-MOBILE RUN IS A DISTRIBUTION, NOT A SAMPLE (#83, ruled in
 * package 44: fix the gate, not the page).
 *
 * Package 43 measured this route nine times and found the scores sit in two
 * clusters with nothing between them — 95-96 and 81-82 — and that the
 * discriminator is not load but the OBSERVED LCP: ~240ms lands in one cluster,
 * ~530ms in the other. The cause is the instrument. Lighthouse's mobile preset
 * SIMULATES throttling: it takes the dependency graph observed on the real
 * machine and projects it onto a 1.5Mbps link. On localhost the 460KB postings
 * index arrives in 72ms, a dead heat with a paint at ~250ms, and whichever side
 * of that coin flip the paint falls on decides whether Lantern treats the fetch
 * as a parent of the LCP node. The gap between the clusters is 2442ms; 460,147
 * bytes at the preset's own 1474.56 Kbps is 2496ms. Applied throttling — the
 * control — puts the index at 8101ms against a 5072ms paint, three seconds too
 * late to gate it, and package 42's own site/src reproduces the same two
 * clusters, so it is not a regression either.
 *
 * A single sample of a bimodal distribution is a coin flip reported as a
 * measurement. So the gate takes the MEDIAN and prints every run: a real
 * regression moves the median, while the coin flip moves one run. What it
 * must not do is make the coin land the same way every time by moving the fetch
 * a tick later — that buys a number and helps no reader.
 *
 * AND ON MOBILE IT JUDGES WHAT THE READER SEES, NOT THE COMPOSITE (#86, ruled
 * in package 47: option B). The median fixed one bad run; it could not fix a
 * distribution that moved. Package 45 ran five throttled-mobile audits of one
 * unchanged build: performance 73-87 while TBT ran 414-1291ms, and the commit
 * before it scored LOWER (61-80, one run at TBT 10.5s). The composite was
 * measuring Lighthouse's simulated main thread — observed task times multiplied
 * by the preset's 4x CPU slowdown — which moves with whatever else the machine
 * is doing, not with the page.
 *
 * So on throttled mobile the gate ENFORCES the two metrics a reader sees, on
 * the median of five runs: LCP <= 2500ms and CLS <= 0.1, each the point where
 * Lighthouse's own scoring for that metric drops below 0.9 (the Core Web Vitals
 * "good" boundary). Measured against the 25 runs on record — four builds
 * (packages 42-45), five sets of runs: every set's median LCP is 2414-2436ms,
 * and no CLS recorded is above 0.044. Single runs are not that tidy: three sat
 * at 4858-4859ms (the index race above) and two, on a loaded machine, at 2542
 * and 3205ms — Lantern scales observed task times by the preset's 4x CPU
 * slowdown, on the critical path as well. Five runs judged by their median
 * absorb two such runs. The LCP margin is thin on purpose: about 70ms, some
 * 13KB more on the critical path as transferred at the preset's link, which is
 * exactly where a reader's first paint leaves "good".
 *
 * It PRINTS, and does not enforce, the performance score and the TBT spread,
 * so a real main-thread regression is still in front of whoever reads this.
 * What makes it acceptable to stop enforcing them here is the desktop sweep
 * above: TBT is enforced on every route there, at <= 150ms. Desktop TBT is
 * stable — 0-87ms on every route across packages 43-45 on a quiet machine —
 * and it catches the regression the mobile composite was the only guard
 * against. The accessibility, best-practice and SEO audits are not simulated,
 * so they stay enforced on mobile as well. */
const RUNS = Number(process.env.LH_MOBILE_RUNS ?? 5)
/* LH_MOBILE_RUNS=0 skips the throttled-mobile block — said as SKIPPED and not
 * counted as an audit. It must never PASS: with no runs every enforced
 * comparison below is against undefined, which is false, so an empty block
 * would read as a clean pass (found in package 47 before it was ever run). */
const MOBILE = (!ONLY.size || ONLY.has('openings')) && RUNS >= 1
if ((!ONLY.size || ONLY.has('openings')) && !MOBILE) {
  console.log(`\n  SKIPPED  openings (THROTTLED MOBILE) — LH_MOBILE_RUNS=${process.env.LH_MOBILE_RUNS}; not an audit, not a pass`)
}
if (MOBILE) {
  const runs = []
  for (let i = 1; i <= RUNS; i++) {
    const file = join(OUT, `openings-mobile-${i}.json`)
    rmSync(file, { force: true })
    await run(`${BASE}#/openings`, file, true)
    runs.push(read(file))
  }
  /* The middle run — and, for an EVEN number of runs, the less favourable of
   * the two middle ones: the upper for a ceiling (LCP, CLS, TBT), the lower
   * for a floor (the categories). Taking the upper for both was lenient for
   * the >= 95 floors (adversarial review, package 47). Five runs, the default,
   * have one middle and are unaffected. */
  const sorted = (xs) => [...xs].sort((a, b) => a - b)
  const ceilingMedian = (xs) => sorted(xs)[Math.floor(xs.length / 2)]
  const floorMedian = (xs) => sorted(xs)[Math.ceil(xs.length / 2) - 1]
  const m = {
    perf: floorMedian(runs.map((r) => r.perf)),
    a11y: floorMedian(runs.map((r) => r.a11y)),
    bp: floorMedian(runs.map((r) => r.bp)),
    seo: floorMedian(runs.map((r) => r.seo)),
    tbt: ceilingMedian(runs.map((r) => r.tbt)),
    cls: ceilingMedian(runs.map((r) => r.cls)),
    lcp: ceilingMedian(runs.map((r) => r.lcp)),
  }
  const bad404 = runs.some((r) => /no-such|not-found/.test(r.finalUrl))
  const blind = runs.filter((r) => r.error || r.lcp < 0 || r.cls < 0)
  const why = [
    blind.length && `${blind.length} of ${RUNS} runs measured nothing (${[...new Set(blind.map((r) => r.error ?? 'no LCP or CLS'))].join(', ')})`,
    m.lcp > MOBILE_LCP_MAX && `median LCP > ${MOBILE_LCP_MAX}ms`,
    m.cls > MOBILE_CLS_MAX && `median CLS > ${MOBILE_CLS_MAX}`,
    (m.a11y < OTHER_MIN || m.bp < OTHER_MIN || m.seo < OTHER_MIN) && `a category < ${OTHER_MIN}`,
    bad404 && 'audited a not-found page',
  ].filter(Boolean)
  const pass = why.length === 0
  if (!pass) fails++
  console.log('')
  for (const [i, r] of runs.entries()) {
    console.log(`        run ${i + 1}: perf ${String(r.perf).padStart(3)}  TBT ${String(r.tbt).padStart(4)}ms  CLS ${r.cls}  LCP ${r.lcp}ms`)
  }
  const span = (k) => `${Math.min(...runs.map((r) => r[k]))}-${Math.max(...runs.map((r) => r[k]))}`
  console.log(`  ${pass ? 'PASS' : 'FAIL'}  openings (THROTTLED MOBILE, median of ${RUNS})  LCP ${m.lcp}ms (<= ${MOBILE_LCP_MAX})  CLS ${m.cls} (<= ${MOBILE_CLS_MAX})  a11y ${m.a11y}  bp ${m.bp}  seo ${m.seo}${pass ? '' : `   <- ${why.join('; ')}`}`)
  console.log(`        printed, not enforced (#86): performance median ${m.perf}, spread ${span('perf')}; TBT median ${m.tbt}ms, spread ${span('tbt')}ms`)
}

console.log(`\n${rows.length + (MOBILE ? 1 : 0)} audits, ${fails} below the floor `
  + `(desktop: performance >= ${PERF_MIN}, TBT <= ${DESKTOP_TBT_MAX}ms, the rest >= ${OTHER_MIN}; `
  + `throttled mobile: median LCP <= ${MOBILE_LCP_MAX}ms and CLS <= ${MOBILE_CLS_MAX}, the rest >= ${OTHER_MIN})`)
console.log(`raw reports in ${OUT}`)
process.exit(fails ? 1 : 0)
