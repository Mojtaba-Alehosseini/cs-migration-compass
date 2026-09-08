/* Throttled-mobile /openings, N times, reported as a distribution.
 *
 * One local Lighthouse score is not evidence. This route in particular moves:
 * two full sweeps in one session returned 89 (TBT 356ms, LCP 2424ms) and 81
 * (TBT 136ms, LCP 4859ms) — the QUIETER machine scored WORSE, which is not how
 * a CPU-bound regression behaves and is the signal that something other than
 * the page is moving.
 *
 * So this reports every run's simulated LCP alongside its OBSERVED LCP. The
 * gap between those two numbers is the whole story: Lantern projects the
 * observed dependency graph onto a throttled link, and on localhost a 460KB
 * fetch that lands in 72ms lands BEFORE the paint — which makes it a parent of
 * the LCP node, which on a simulated 1.5Mbps link costs 2.5 seconds.
 *
 * LH_METHOD=devtools swaps Lantern for APPLIED throttling, which really does
 * delay the network instead of modelling it. That is the control: it resolves
 * the race the way a phone on a slow link resolves it, rather than the way
 * localhost resolves it and Lantern then extrapolates.
 *
 *   node scripts/tests/lighthouse_mobile_spread.mjs            # 3 runs
 *   LH_RUNS=5 BASE_URL=http://localhost:4173/ node scripts/tests/lighthouse_mobile_spread.mjs
 *   LH_TAG=p42 node scripts/tests/lighthouse_mobile_spread.mjs # label the reports
 *   LH_METHOD=devtools LH_TAG=applied node scripts/tests/lighthouse_mobile_spread.mjs
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const RUNS = Number(process.env.LH_RUNS ?? 3)
const TAG = process.env.LH_TAG ?? 'cur'
const OUT = join(tmpdir(), 'lh-p43-spread')
mkdirSync(OUT, { recursive: true })

const NPX = process.platform === 'win32' ? 'npx.cmd' : 'npx'
// The '#' must survive the shell as one argument — see lighthouse_gate.mjs.
const quote = (a) => (/[\s#&^|<>]/.test(a) ? `"${a}"` : a)

const run = (url, file) => new Promise((resolve, reject) => {
  const args = [
    'lighthouse', url,
    '--output=json', `--output-path=${file}`,
    '--quiet', '--chrome-flags=--headless=new --no-sandbox',
    '--only-categories=performance',
  ]
  if (process.env.LH_METHOD) args.push(`--throttling-method=${process.env.LH_METHOD}`)
  const p = spawn(NPX, args.map(quote), { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true, shell: true })
  let err = ''
  p.stderr.on('data', (d) => { err += d })
  p.on('error', reject)
  p.on('close', (code) => {
    // The report file is the evidence, not the exit code: chrome-launcher
    // throws EPERM deleting its temp profile AFTER the report is written.
    if (existsSync(file)) {
      try { JSON.parse(readFileSync(file, 'utf8')); return resolve() } catch { /* half-written */ }
    }
    reject(new Error(`lighthouse exit ${code}: ${err.slice(-400)}`))
  })
})

const rows = []
for (let i = 1; i <= RUNS; i++) {
  const file = join(OUT, `${TAG}-${i}.json`)
  rmSync(file, { force: true })
  await run(`${BASE}#/openings`, file)
  const r = JSON.parse(readFileSync(file, 'utf8'))
  const a = r.audits
  const metrics = a.metrics?.details?.items?.[0] ?? {}
  const row = {
    perf: Math.round(r.categories.performance.score * 100),
    fcp: Math.round(a['first-contentful-paint'].numericValue),
    lcp: Math.round(a['largest-contentful-paint'].numericValue),
    obsLcp: Math.round(metrics.observedLargestContentfulPaint ?? -1),
    si: Math.round(a['speed-index'].numericValue),
    tbt: Math.round(a['total-blocking-time'].numericValue),
    cls: +a['cumulative-layout-shift'].numericValue.toFixed(4),
    url: r.finalDisplayedUrl ?? r.finalUrl,
  }
  rows.push(row)
  console.log(`  ${TAG} run ${i}  perf ${String(row.perf).padStart(3)}  FCP ${String(row.fcp).padStart(4)}  LCP ${String(row.lcp).padStart(5)} (observed ${row.obsLcp})  SI ${String(row.si).padStart(4)}  TBT ${String(row.tbt).padStart(4)}  CLS ${row.cls}`)
  if (/no-such|not-found/.test(row.url)) console.log(`        !! finalUrl looks like a 404: ${row.url}`)
}

const perfs = rows.map((r) => r.perf).sort((x, y) => x - y)
const lcps = rows.map((r) => r.lcp).sort((x, y) => x - y)
const mid = (xs) => xs[Math.floor(xs.length / 2)]
console.log(`\n  ${TAG}: perf min ${perfs[0]} median ${mid(perfs)} max ${perfs[perfs.length - 1]}   simulated LCP min ${lcps[0]} median ${mid(lcps)} max ${lcps[lcps.length - 1]}ms`)
console.log(`  reports in ${OUT}`)
