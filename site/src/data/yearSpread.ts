/** Package 14, Tier 2 (external audit Finding 2, HIGH) — the reference-year
 *  spread across whichever rows a wage-panel toggle actually shows a bar
 *  for. Split into its own file, with zero imports, specifically so the
 *  >3-year disclosure rule has a REAL unit test: it used to live in
 *  data/explore.ts, which imports store.ts, which reads import.meta.env at
 *  module scope — plain Node (no Vite transform) throws on that import
 *  before a test ever runs, so the "unit-tested" claim this file's own
 *  comment used to carry was false (caught by an independent adversarial
 *  review, finding M6). See yearSpread.test.ts, run with `node --test`
 *  (Node 22.6+ strips this file's own type annotations natively — no
 *  transpile step, no new devDependency).
 *
 *  Tier 1's own set-wide crosswalk fix (resolve_set()) already excludes
 *  every country whose vintage gap was the widest (Ireland 2022, Spain
 *  2018) from the live chart's own comparable set, so the live site
 *  currently has nothing wide enough to trigger this on screen; the logic
 *  itself is still real and still runs every time the toggle changes. */
export function computeYearSpread(
  rows: { country: string; year: number }[],
): { spread: number; oldest: { country: string; year: number }; newest: { country: string; year: number } } | null {
  if (rows.length < 2) return null
  const oldest = rows.reduce((a, b) => (b.year < a.year ? b : a))
  const newest = rows.reduce((a, b) => (b.year > a.year ? b : a))
  return { spread: newest.year - oldest.year, oldest, newest }
}
