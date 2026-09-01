/* Package 25, tier 3 — six assertions over the rendered inventory.
 *
 * Each is a defect class package 24 actually shipped, generalised from the
 * one place it was found to every place it could happen. They run against
 * the DOM of all ~100 route-and-entity combinations this site can render,
 * not against source, because every one of these was invisible in source
 * and obvious on screen.
 *
 * Every assertion here has been demonstrated FAILING against deliberately
 * broken code before being kept — see REPORT-P25.md. An assertion never
 * seen to fail is not evidence; package 24 shipped one that read a settled
 * page where the value had already resolved and could not have failed.
 *
 * Run:  node scripts/tests/test_figure_inventory.mjs
 * CI runs it against the build's own preview server, same as
 * test_ui_regressions.mjs.
 */
import { readFileSync } from 'node:fs'
import { launch, openPage } from './cdp.mjs'
import { capture, defaultTargets } from './inventory_figures.mjs'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'

let fails = 0
const say = (m) => console.log(m)
const check = (cond, label) => {
  if (cond) say(`PASS  ${label}`)
  else { fails += 1; say(`FAIL  ${label}`) }
}

const readJson = (p) => JSON.parse(readFileSync(p, 'utf8'))
const dataOf = (o) => o.data ?? o

/* ---------------------------------------------------------------- class 3 */
/* Internal identifiers a reader should never be shown. The site DELIBERATELY
 * names classification codes (isco08:2512, NOC, SOC) — those are real
 * citations on a statistical site, and package 24 already established that
 * exception. What must never happen is an id standing in for a name because
 * a lookup fell through, or a pipeline filename reaching prose. */
const FORBIDDEN_KEYS = [
  { re: /\bsrc_[a-z_]+\.py\b/g, what: 'a pipeline filename' },
  { re: /\bno-series\s*[—-]/g, what: 'the internal no-series prefix' },
  { re: /\b(usd|native)_(regular_pay|total_earnings)\b/g, what: 'a raw combo key' },
]
/* An id used AS a citation — "salary_ca published median" — as opposed to
 * prose that happens to cite a file, which this site does on purpose. */
const ID_AS_CITATION = /\b(salary_[a-z]{2}|bls_oews)\s+(published|publishes)\b/g

/* ---------------------------------------------------------------- class 4 */
const ID_ONLY_LABEL = /^(salary_[a-z]{2}|bls_oews|[a-z]+_[a-z]{2,})$/

/* ---------------------------------------------------------------- class 6 */
function relLum(r, g, b) {
  const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}
function parseColor(s) {
  if (!s) return null
  let m = s.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/)
  if (m) return [+m[1], +m[2], +m[3], m[4] == null ? 1 : +m[4]]
  m = s.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)/)
  if (m) return [+m[1] * 255, +m[2] * 255, +m[3] * 255, 1]
  return null
}
function ratio(a, b) {
  const l1 = relLum(a[0], a[1], a[2]), l2 = relLum(b[0], b[1], b[2])
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]
  return (hi + 0.05) / (lo + 0.05)
}

const { targets, countries, cities } = defaultTargets(BASE)
const { port, close } = await launch()

try {
  const page = await openPage(port)
  /* Tall on purpose. Contrast is measured through the real paint stack at
   * each mark's own centre, and elementsFromPoint only answers for points
   * inside the VIEWPORT — at 1440x900 that left 523 of 619 marks below the
   * fold and unmeasurable, which made C6 pass by measuring almost nothing.
   * A tall window is a measurement device here, not a layout claim; the
   * one-screen claims live in Tier 4 and are measured at real sizes. */
  await page.viewport(1440, 4200)

  say(`Inventory: ${targets.length} route/entity combinations `
    + `(${countries.length} countries, ${cities.length} cities)`)
  const pages = []
  for (const [id, url] of targets) {
    try { pages.push(await capture(page, id, url)) }
    catch (e) { pages.push({ id, url, error: String((e && e.message) || e), figures: [], nodata: [], clipped: [], marks: [], text: '' }) }
  }
  const figures = pages.flatMap((p) => (p.figures ?? []).map((f) => ({ page: p.id, ...f })))
  say(`Captured ${figures.length} figures, `
    + `${pages.reduce((a, p) => a + (p.nodata?.length ?? 0), 0)} no-data marks, `
    + `${pages.reduce((a, p) => a + (p.marks?.length ?? 0), 0)} marks\n`)

  check(pages.every((p) => !p.error), `every route rendered without throwing (${pages.filter((p) => p.error).length} errored)`)

  /* ============================================================= class 1 */
  say('\n=== C1: no displayed figure sits on an unset initialiser ===')
  /* /work's `markerLeft = 50` is the template — a default that survived the
   * failure path and was presented as a measurement. Generalised: a
   * positioned mark must never sit at exactly the midpoint UNLESS the value
   * it encodes genuinely lands there. Real percentile positions are
   * irrational-ish; an exact 50% across many rows is the signature of a
   * constant, not of data. */
  const positioned = pages.flatMap((p) => (p.marks ?? []).filter((m) => m.left).map((m) => ({ page: p.id, ...m })))
  const atFifty = positioned.filter((m) => m.left === '50%')
  say(`  ${positioned.length} positioned marks; ${atFifty.length} sit at exactly left:50%`)
  atFifty.slice(0, 5).forEach((m) => say(`    ${m.page} ${m.cls}`))
  check(atFifty.length === 0,
    `C1: no positioned mark sits on the midpoint default (${atFifty.length} found)`)

  /* ============================================================= class 2 */
  say('\n=== C2: nothing reads "no data" while the data is non-empty ===')
  /* Italy's 28 openings rendered as an em dash. Cross-checked against the
   * payload rather than against the component's intent. */
  const openings = dataOf(readJson('site/public/data/history/openings.json')).by_country ?? {}
  const workPage = pages.find((p) => p.id === 'work')
  const workText = workPage?.text ?? ''
  const countriesWithOpenings = Object.entries(openings)
    .filter(([, v]) => (v?.software ?? 0) > 0)
    .map(([cc, v]) => ({ cc, n: v.software }))
  const spine = new Set(countries)
  const onSpine = countriesWithOpenings.filter((c) => spine.has(c.cc))
  const missing = onSpine.filter(({ n }) => !workText.includes(n.toLocaleString('en-US')))
  say(`  ${onSpine.length} spine countries have >0 software openings; checking each count is rendered`)
  missing.slice(0, 6).forEach((m) => say(`    MISSING  ${m.cc} = ${m.n}`))
  check(missing.length === 0,
    `C2: every spine country's own non-zero openings count appears on /work (${missing.length} absent)`)

  /* ============================================================= class 3 */
  say('\n=== C3: no internal key reaches a reader ===')
  const keyHits = []
  for (const p of pages) {
    for (const { re, what } of FORBIDDEN_KEYS) {
      for (const m of (p.text ?? '').match(re) ?? []) keyHits.push({ page: p.id, hit: m, what })
    }
    for (const m of (p.text ?? '').match(ID_AS_CITATION) ?? []) {
      keyHits.push({ page: p.id, hit: m, what: 'a source id used as a citation' })
    }
  }
  keyHits.slice(0, 8).forEach((h) => say(`    ${h.page}: ${JSON.stringify(h.hit)} — ${h.what}`))
  check(keyHits.length === 0, `C3: no pipeline filename, internal prefix, combo key, or id-as-citation is visible (${keyHits.length} found)`)

  /* ============================================================= class 4 */
  say('\n=== C4: every card names a real source or method ===')
  const cardless = figures.filter((f) => !f.hasCard)
  const idLabelled = figures.filter((f) => {
    const l = (f.cardLabel || '').replace(/^(Source|Method):\s*/, '').trim()
    return l && ID_ONLY_LABEL.test(l)
  })
  cardless.slice(0, 5).forEach((f) => say(`    NO CARD  ${f.page} :: ${f.visible}`))
  idLabelled.slice(0, 5).forEach((f) => say(`    ID LABEL ${f.page} :: ${f.cardLabel}`))
  check(cardless.length === 0, `C4: every <Figure>/<Derived> opens a card (${cardless.length} without)`)
  check(idLabelled.length === 0, `C4: no card is titled with a bare source id (${idLabelled.length} found)`)

  /* ============================================================= class 5 */
  say('\n=== C5: nothing is truncated below legibility without a way to read it ===')
  /* Package 24 found refusal reasons cut to 31% and 24% of their own width,
   * recoverable only by hovering — which does not exist on touch. */
  const clipped = pages.flatMap((p) => (p.clipped ?? [])
    // A `title` does NOT excuse truncation: it is a hover affordance, and
    // hover does not exist on touch. Package 24's actual defect — a
    // refusal reason clipped to 31% inside a plain <span title={...}> —
    // would have slipped through the first version of this filter, which
    // excused anything carrying a title. The bar is a real tap target.
    .filter((c) => c.shownPct < 70 && c.text.length > 12 && !c.interactive)
    .map((c) => ({ page: p.id, ...c })))
  clipped.slice(0, 6).forEach((c) => say(`    ${c.shownPct}%  ${c.page} :: ${c.text.slice(0, 60)}`))
  check(clipped.length === 0,
    `C5: nothing is clipped below 70% without a real tap target — a hover title is not one `
    + `(${clipped.length} found)`)

  /* ============================================================= class 6 */
  say('\n=== C6: every mark clears 3:1 against what sits behind it ===')
  /* Including mark-on-mark: package 24's own contrast fix darkened a track
   * until the band drawn ON it measured 1.01:1 — each element passed against
   * the page background while the pair that actually carries the meaning
   * did not. */
  /* Each mark is compared on the pair that CARRIES ITS MEANING, against what
   * is really painted behind it (elementsFromPoint, not the DOM parent):
   * a filled shape on its backdrop, a hollow shape's ring on its backdrop,
   * a chip's label on its own wash. The first version of this check compared
   * every mark's background against its DOM parent and flagged three marks
   * that are demonstrably legible — a 4.6:1 quartile tick scored 1.06:1
   * because its parent is not what it is drawn on. It would have "found"
   * three defects that were not there, which is the same failure as missing
   * three that are. */
  const lowContrast = []
  let offscreen = 0
  for (const p of pages) {
    for (const m of p.marks ?? []) {
      if (!m.w || !m.h) continue
      // Only marks actually on screen can have a measured backdrop.
      if (m.kind !== 'text-chip' && !m.onScreen) { offscreen += 1; continue }
      const fg = parseColor(m.meaningColor)
      const bg = parseColor(m.kind === 'text-chip' ? m.ownBackground : m.behind)
      if (!fg || !bg || fg[3] === 0 || bg[3] === 0) continue
      const floor = m.kind === 'text-chip' ? 4.5 : 3      // 1.4.3 text vs 1.4.11 non-text
      const r = ratio(fg, bg)
      if (r < floor) {
        lowContrast.push({ page: p.id, cls: String(m.cls).slice(0, 30), via: m.meaningFrom,
          behind: String(m.kind === 'text-chip' ? 'own background' : m.behindCls).slice(0, 26),
          r: r.toFixed(2), floor })
      }
    }
  }
  const worst = [...new Map(lowContrast.map((x) => [x.cls + '|' + x.behind, x])).values()]
  say(`  ${offscreen} marks were below the fold and are not measurable by paint-stack; excluded, not assumed passing`)
  worst.slice(0, 8).forEach((x) => say(`    ${x.r}:1 (needs ${x.floor}) ${x.cls} [${x.via}] on ${x.behind}  @${x.page}`))
  check(lowContrast.length === 0,
    `C6: every mark clears its floor on the pair that carries its meaning `
    + `(${lowContrast.length} instances, ${worst.length} distinct)`)

  /* ---- R8, re-derived from the inventory rather than from a proxy ------- */
  say('\n=== R8 (inherited): the Netherlands, asserted from the record ===')
  /* Package 24 changed this from "NL renders zero method-card triggers" to
   * "no <Derived> and no digits", and flagged it as the author editing their
   * own test. Re-derived here from what the inventory RECORDS the cell
   * contains, so it rests on the rendered record rather than on a property
   * chosen by whoever changed the behaviour. */
  const nlFigures = figures.filter((f) => f.page === 'work' && /not comparable/i.test(f.visible))
  const nlDerived = nlFigures.filter((f) => f.kind === 'Derived')
  say(`  NL estimate cell renders: ${nlFigures.map((f) => JSON.stringify(f.visible)).join(', ') || '(nothing)'}`)
  check(nlFigures.length === 1, `R8: the Netherlands renders exactly one estimate-cell mark (${nlFigures.length})`)
  check(nlDerived.length === 0, `R8: and it is not a <Derived> — nothing calculated is presented (${nlDerived.length})`)
  check(nlFigures.every((f) => !/\d/.test(f.visible)), 'R8: and it carries no digits')
  check(nlFigures.every((f) => f.hasCard && /ISCO-08 correspondence/i.test(f.cardText ?? '')),
    "R8: while the crosswalk's own refusal reason is one tap away")

  page.close()
} finally { close() }

say('')
say('-'.repeat(70))
say(fails === 0 ? 'ALL FIGURE-INVENTORY ASSERTIONS PASS (C1-C6, R8)' : `${fails} check(s) FAILED`)
process.exitCode = fails ? 1 : 0
