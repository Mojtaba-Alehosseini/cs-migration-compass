/* Records `coverage_floors.json` — the "what a complete run looks like"
 * baseline that `coverage.mjs` asserts against.
 *
 * Run it deliberately, never automatically:
 *
 *     cd site && npm run build && npm run preview     # in another shell
 *     node scripts/tests/record_coverage_floors.mjs
 *
 * It captures every target the inventory walks, waiting for the DOM to stop
 * changing for a long window rather than for the suite's own readiness signal.
 * That is on purpose: the floors are the yardstick, so they must not be
 * measured with the instrument they are meant to check. If the suite's
 * readiness were ever wrong again in the same direction, floors recorded
 * through it would simply move down to match, and the check would go on
 * passing. Package 30's `/openings` failure is exactly that story.
 *
 * The floors are deliberately slack: 80% of a known-good route contribution,
 * 50% of its text length, 95% of the corpus totals. They exist to catch a
 * route falling to zero or a run losing a chunk of the site, not to pin exact
 * numbers — the data behind this site changes on a schedule, and a check that
 * fails when the pipeline does its job is a check people learn to ignore
 * (package 26's lesson, recorded in docs/REGRESSION-CATALOGUE.md).
 */
import { writeFileSync } from 'node:fs'
import { execSync } from 'node:child_process'
import { launch, openPage } from './cdp.mjs'
import { EXTRACT, REPO, defaultTargets } from './inventory_figures.mjs'
import { contribution, FLOORS_PATH } from './coverage.mjs'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const STABLE_MS = 1500
const MAX_MS = 25000

const ROUTE_FRACTION = 0.8
const TEXT_FRACTION = 0.5
const CORPUS_FRACTION = 0.95

const { targets, cities, countries } = defaultTargets(BASE)
const { port, close } = await launch()
const seen = {}
let unsettled = []

try {
  const page = await openPage(port)
  await page.viewport(1440, 4200)
  process.stderr.write(`recording floors from ${targets.length} targets\n`)
  let n = 0
  for (const [id, url] of targets) {
    await page.eval(`location.href = ${JSON.stringify(url)}`)
    const settled = await page.eval(`(async () => {
      const t0 = performance.now()
      let last = -1, since = performance.now()
      while (performance.now() - t0 < ${MAX_MS}) {
        const c = document.querySelectorAll('*').length
        if (c !== last) { last = c; since = performance.now() }
        else if (performance.now() - since >= ${STABLE_MS} && document.readyState === 'complete') return true
        await new Promise((r) => setTimeout(r, 100))
      }
      return false
    })()`, { awaitPromise: true })
    if (!settled) unsettled.push(id)
    const p = JSON.parse(await page.eval(EXTRACT, { awaitPromise: true }))
    seen[id] = contribution({ ...p, id })
    if (++n % 20 === 0) process.stderr.write(`  ... ${n}/${targets.length}\n`)
  }
} finally {
  close()
}

if (unsettled.length) {
  process.stderr.write(`REFUSING to record: ${unsettled.length} route(s) never settled: ${unsettled.join(', ')}\n`)
  process.exit(1)
}

const floorOf = (v, frac) => (v > 0 ? Math.max(1, Math.floor(v * frac)) : null)
const routes = {}
for (const [id, c] of Object.entries(seen)) {
  routes[id] = {
    figures: floorOf(c.figures, ROUTE_FRACTION),
    marks: floorOf(c.marks, ROUTE_FRACTION),
    nodata: floorOf(c.nodata, ROUTE_FRACTION),
    rows: floorOf(c.rows, ROUTE_FRACTION),
    // textLen is the one that catches a shell: /openings rendered 829
    // characters of chrome before its data arrived and 14,459 after.
    textLen: floorOf(c.textLen, TEXT_FRACTION),
  }
}
const total = (k) => Object.values(seen).reduce((a, c) => a + c[k], 0)
const observed = {
  targets: Object.keys(seen).length,
  figures: total('figures'),
  marks: total('marks'),
  nodata: total('nodata'),
  rows: total('rows'),
}

let commit = 'unknown'
try { commit = execSync('git rev-parse --short HEAD', { cwd: REPO }).toString().trim() } catch { /* not a repo */ }

const out = {
  recorded: {
    at: new Date().toISOString().slice(0, 10),
    commit,
    by: 'scripts/tests/record_coverage_floors.mjs',
    method: `DOM element count unchanged for ${STABLE_MS}ms, readyState complete, ${MAX_MS}ms cap`,
    why: 'measured independently of the suite readiness signal it is the yardstick for',
    observed,
    fractions: { route: ROUTE_FRACTION, text: TEXT_FRACTION, corpus: CORPUS_FRACTION },
  },
  corpus: {
    figures: floorOf(observed.figures, CORPUS_FRACTION),
    marks: floorOf(observed.marks, CORPUS_FRACTION),
    nodata: floorOf(observed.nodata, CORPUS_FRACTION),
    rows: floorOf(observed.rows, CORPUS_FRACTION),
  },
  // What was actually seen, per route, not only the floor derived from it.
  // A floor on its own cannot answer "has this route shrunk by 30%?" — and
  // that question is the whole reason the file exists.
  observed_routes: seen,
  routes,
}
writeFileSync(FLOORS_PATH, JSON.stringify(out, null, 1) + '\n')
process.stderr.write(`wrote ${FLOORS_PATH}\n`)
process.stderr.write(`observed: ${JSON.stringify(observed)}\n`)
