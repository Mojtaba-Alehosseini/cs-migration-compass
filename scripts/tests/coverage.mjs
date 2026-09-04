/* Coverage — the check that fails when a run saw LESS than it should have.
 *
 * Every assertion in this repo is shaped "find violations, expect zero". That
 * shape is satisfied by absence: a route that never rendered has no violations
 * to find, so the suite is at its most confident exactly when it has seen the
 * least. Package 30 established that the figure inventory was dropping
 * `/openings` entirely on roughly three runs in four — 96 of 764 marks, 12.6%
 * of the site — and printing ALL ASSERTIONS PASS while it did.
 *
 * The waits were the mechanism. This file is about the shape. Even with
 * perfect readiness, nothing in the suite would notice a route that quietly
 * stopped contributing; the floors below are what turn that from an invisible
 * shrink into a red build.
 *
 * Floors are recorded in `coverage_floors.json` together with the run they
 * came from, so a future drop is attributable rather than mysterious. They
 * guard ABSENCE, not growth: exceeding a floor is always fine.
 */
import { readFileSync } from 'node:fs'
import { REPO } from './inventory_figures.mjs'

export const FLOORS_PATH = REPO + 'scripts/tests/coverage_floors.json'

export function loadFloors(path = FLOORS_PATH) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

/** What one captured page contributed, in the units the floors are stated in. */
export function contribution(p) {
  return {
    figures: p.figures?.length ?? 0,
    marks: p.marks?.length ?? 0,
    nodata: p.nodata?.length ?? 0,
    rows: Object.keys(p.rows ?? {}).length,
    textLen: (p.text ?? '').length,
  }
}

/**
 * Compare a captured run against the recorded floors.
 *
 * Returns everything a caller needs to assert on AND to print, because a
 * coverage failure is only actionable if it names the route and the number.
 */
export function coverageReport(pages, floors) {
  const byId = new Map(pages.map((p) => [p.id, p]))
  const expected = Object.keys(floors.routes)

  const missing = expected.filter((id) => !byId.has(id))
  const errored = pages.filter((p) => p.error).map((p) => `${p.id}: ${p.error}`)
  const unexpected = pages.map((p) => p.id).filter((id) => !floors.routes[id])

  const below = []
  const contributions = {}
  for (const id of expected) {
    const p = byId.get(id)
    if (!p) continue
    const got = contribution(p)
    contributions[id] = got
    for (const [metric, floor] of Object.entries(floors.routes[id])) {
      if (floor == null) continue
      if (got[metric] < floor) below.push({ id, metric, got: got[metric], floor })
    }
  }

  const corpus = { figures: 0, marks: 0, nodata: 0, rows: 0 }
  for (const p of pages) {
    const c = contribution(p)
    for (const k of Object.keys(corpus)) corpus[k] += c[k]
  }
  const corpusBelow = Object.entries(floors.corpus)
    .filter(([k, floor]) => floor != null && corpus[k] < floor)
    .map(([k, floor]) => ({ metric: k, got: corpus[k], floor }))

  return { missing, errored, unexpected, below, corpus, corpusBelow, contributions }
}

/** Human-readable lines for a failing report. Empty when everything is fine. */
export function explain(r) {
  const out = []
  if (r.missing.length) out.push(`  routes never captured (${r.missing.length}): ${r.missing.join(', ')}`)
  if (r.errored.length) out.push(`  routes that threw (${r.errored.length}):\n    ${r.errored.join('\n    ')}`)
  for (const b of r.below) {
    out.push(`  ${b.id} contributed ${b.metric}=${b.got}, floor is ${b.floor}`
      + (b.got === 0 ? '   <- contributed NOTHING; every check over this route was vacuous' : ''))
  }
  for (const b of r.corpusBelow) {
    out.push(`  corpus ${b.metric}=${b.got}, floor is ${b.floor}`
      + `   <- the run as a whole saw less than a known-good run`)
  }
  return out
}
