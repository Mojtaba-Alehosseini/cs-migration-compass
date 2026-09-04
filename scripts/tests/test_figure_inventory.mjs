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
import { capture, defaultTargets, REPO } from './inventory_figures.mjs'

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
  // The token itself, with or without the dash that usually follows it.
  // The first version required a trailing dash, and WagePanel renders
  // a.reason.split(' -- ')[0], which keeps the token and throws the
  // sentence away -- so the one place it printed bare was the one place
  // this pattern could not see.
  { re: /no-series/g, what: 'the internal no-series token' },
  { re: /\b(usd|native)_(regular_pay|total_earnings)\b/g, what: 'a raw combo key' },
]
/* An id used AS a citation — "salary_ca published median" — as opposed to
 * prose that happens to cite a file, which this site does on purpose. */
const ID_AS_CITATION = /\b(salary_[a-z]{2}|bls_oews)\s+(published|publishes)\b/g

/* ---------------------------------------------------------------- class 4 */
/* An internal source id anywhere in a card's own title — not only as the
 * whole title. The first version was anchored (`^...$`), so it matched a
 * bare "salary_se" and missed "salary_ca published median", which is the
 * exact string this package was fixing. It caught 13 of the 40 affected
 * cards; the other 27 were found by reading the record by hand, which is
 * not a check. */
const SOURCE_ID_ANYWHERE = /(salary_[a-z]{2}|bls_oews|numbeo|teranet|oecd_[a-z_]+)/

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

  /* Package 28 — per-route coverage for Explore's seven themes. The six
   * assertions below already run over every route, but they report one
   * aggregate number, so "0 violations" cannot be told apart from "that
   * theme rendered nothing to violate anything". This prints what each
   * theme actually contributed to the sample. It asserts nothing new: it is
   * the evidence that the assertions had something to bite on per theme. */
  const explorePages = pages.filter((p) => p.id === 'explore' || p.id.startsWith('explore-'))
  say('Explore, per theme — what each route contributed to the sample:')
  say('  route              figures  marks  no-data  clipped')
  for (const p of explorePages) {
    say(`  ${p.id.padEnd(18)} ${String(p.figures?.length ?? 0).padEnd(8)} `
      + `${String(p.marks?.length ?? 0).padEnd(6)} ${String(p.nodata?.length ?? 0).padEnd(8)} `
      + `${p.clipped?.length ?? 0}`)
  }
  /* The anti-vacuity assertion is that each theme rendered SOMETHING these
   * checks can inspect — not that it rendered a figure. Five of the seven
   * themes (visa, jobs, people, life, climate) legitimately have no
   * source-card triggers at all: Explore's own design puts confidence,
   * caveat and CSV in a chart footer rather than on a per-figure card
   * (Explore.tsx's header states this), and that was verified against the
   * live DOM rather than inferred from the count being zero. An earlier
   * version of this check demanded one figure per theme and failed on
   * correct code, which is its own kind of wrong. What is worth knowing is
   * printed in the table above: on those five themes C1, C3 and C4 have no
   * figures to bite on, so their "0 violations" is a property of the sample
   * and not of the page. */
  check(explorePages.length >= 8
    && explorePages.every((p) => (p.figures?.length ?? 0) + (p.marks?.length ?? 0) > 0),
    `every Explore theme rendered something the assertions can inspect `
    + `(${explorePages.length} routes, `
    + `${explorePages.reduce((a, p) => a + (p.figures?.length ?? 0), 0)} figures, `
    + `${explorePages.reduce((a, p) => a + (p.marks?.length ?? 0), 0)} marks)`)
  say('')

  /* C6 is a CONTRAST check, and contrast is a property of the palette — so
   * it has to be measured in every palette the site ships, not just the one
   * that happens to be the default. Measured in compass/light alone it
   * passed by 0.067 of margin, and warm/light failed. Four themes x two
   * modes, on the routes that carry the marks. */
  const THEME_PAGES = [
    ['work', `${BASE}#/work?years=8`],
    ['compare-selected', `${BASE}#/compare?places=oslo,copenhagen,berlin`],
    ['country-US', `${BASE}#/country/US`],
  ]
  const themed = []
  for (const theme of ['compass', 'editorial', 'terminal', 'warm']) {
    for (const mode of ['light', 'dark']) {
      for (const [id, url] of THEME_PAGES) {
        await page.hashGo(url, { waitMs: 200 })
        await page.eval(`
          (() => { try {
            localStorage.setItem('compass:theme', ${JSON.stringify(theme)})
            localStorage.setItem('compass:mode', ${JSON.stringify(mode)})
          } catch (e) {}
            document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)})
            document.documentElement.setAttribute('data-mode', ${JSON.stringify(mode)})
          })()`)
        try {
          const cap = await capture(page, `${theme}/${mode} ${id}`, url)
          themed.push(cap)
        } catch { /* recorded as a gap by the count below */ }
      }
    }
  }
  say(`Theme sweep: ${themed.length} captures across 4 themes x 2 modes
`)

  /* ============================================================= class 1 */
  say('\n=== C1: no displayed figure sits on an unset initialiser ===')
  /* /work's `markerLeft = 50` is the template — a default that survived the
   * failure path and was presented as a measurement. Generalised: a
   * positioned mark must never sit at exactly the midpoint UNLESS the value
   * it encodes genuinely lands there. Real percentile positions are
   * irrational-ish; an exact 50% across many rows is the signature of a
   * constant, not of data. */
  /* Any round constant repeated across rows, not the single literal '50%'.
   * A blocklist of one value is a rule tested against the one case it was
   * written from: an initialiser of 0, 32 or 100 reproduces package 24's
   * defect exactly and the first version of this check could not see it.
   * Data-derived positions are effectively never whole numbers, so a whole
   * number appearing on three or more DIFFERENT rows is a constant.
   * Two exemptions, both because the mark carries NO VALUE rather than
   * because it would otherwise fail:
   *   .wrow-quartile  — p25/p75 landing on 0%/100% is exactly what a
   *     quartile-only country's own published range looks like.
   *   .wrow-track.dashed — the abbreviated placeholder drawn for a country
   *     that publishes no spread at all. It is identical on every such row
   *     by construction, encodes no position, and those rows render no
   *     marker whatsoever (package 24's fix), so nothing there is presented
   *     as a measurement. This check flagged it at 32% on 20 marks; that is
   *     the shape doing its job, not an initialiser leaking. */
  const positioned = pages.flatMap((p) => (p.marks ?? [])
    .filter((m) => m.left && !/wrow-quartile|wrow-track dashed/.test(String(m.cls)))
    .map((m) => ({ page: p.id, ...m })))
  const byValue = new Map()
  for (const m of positioned) {
    if (!/^\d+(\.0+)?%$/.test(m.left)) continue          // whole-number percentage
    const k = m.left
    if (!byValue.has(k)) byValue.set(k, [])
    byValue.get(k).push(m)
  }
  const constants = [...byValue.entries()].filter(([, ms]) => ms.length >= 3)
  say(`  ${positioned.length} positioned marks; ${constants.length} whole-number position(s) repeat across 3+ marks`)
  constants.forEach(([v, ms]) => say(`    ${v} on ${ms.length} marks (${[...new Set(ms.map((m) => m.cls))].join(', ')})`))
  check(constants.length === 0,
    `C1: no positioned mark sits on a repeated whole-number constant — the signature of an `
    + `initialiser presented as a measurement (${constants.length} found)`)

  /* ============================================================= class 2 */
  say('\n=== C2: nothing reads "no data" while the data is non-empty ===')
  /* Italy's 28 openings rendered as an em dash. Cross-checked against the
   * payload rather than against the component's intent. */
  /* Read from each country's OWN openings cell, not from the page's text.
   * The first version asked whether the digit string appeared ANYWHERE in
   * /work's innerText, which is unfalsifiable for most of the spine: AE's 24
   * also appears in "ATO Taxation Statistics 2023-24", NO's 14 in "table
   * 11418", QA's 8 in the profile line's "8 yrs". Blank seven of the fifteen
   * openings cells entirely and it still printed PASS. Anchored per row, it
   * asks the question it names. */
  const openings = dataOf(readJson(REPO + 'site/public/data/history/openings.json')).by_country ?? {}
  // Read from the RECORD, not from a live query: the theme sweep above
  // navigates the page away, and a live read here silently returned the
  // wrong route's DOM (15 of 15 "absent").
  const workRows = pages.find((p) => p.id === 'work')?.rows ?? {}
  const cellByCc = Object.fromEntries(Object.entries(workRows).map(([cc, r]) => [cc, r.openings]))
  const spine = new Set(countries)
  const onSpine = Object.entries(openings)
    .filter(([cc, v]) => spine.has(cc) && (v?.software ?? 0) > 0)
    .map(([cc, v]) => ({ cc, n: v.software }))
  const missing = onSpine.filter(({ cc, n }) => {
    const cell = cellByCc[cc]
    if (cell == null) return true
    // The count must be in THIS country's own openings cell, as its own
    // number — not merely a substring of some longer figure in it.
    return !new RegExp(`(^|[^\d,])${n.toLocaleString('en-US').replace(/,/g, ',')}([^\d]|$)`).test(cell)
  })
  say(`  ${onSpine.length} spine countries have >0 software openings; each checked against its own cell`)
  missing.slice(0, 6).forEach((m) => say(`    MISSING  ${m.cc} = ${m.n} (cell reads ${JSON.stringify(cellByCc[m.cc] ?? null)})`))
  check(missing.length === 0,
    `C2: every spine country's own openings count is rendered in that country's own cell (${missing.length} absent)`)

  /* ============================================================= class 3 */
  say('\n=== C3: no internal key reaches a reader ===')
  /* Card titles and bodies are scanned too. p.text is captured with every
   * card CLOSED, so anything a card says was invisible to this check -- and
   * the cards are exactly where citations live. */
  const keyHits = []
  const scan = (page, text, where) => {
    for (const { re, what } of FORBIDDEN_KEYS) {
      for (const m of (text ?? '').match(re) ?? []) keyHits.push({ page, hit: m, what: what + ' (' + where + ')' })
    }
    for (const m of (text ?? '').match(ID_AS_CITATION) ?? []) {
      keyHits.push({ page, hit: m, what: 'a source id used as a citation (' + where + ')' })
    }
  }
  for (const p of pages) {
    scan(p.id, p.text, 'page text')
    for (const f of p.figures ?? []) {
      scan(p.id, f.cardLabel, 'card title')
      scan(p.id, f.cardText, 'card body')
    }
  }
  keyHits.slice(0, 8).forEach((h) => say(`    ${h.page}: ${JSON.stringify(h.hit)} — ${h.what}`))
  check(keyHits.length === 0, `C3: no pipeline filename, internal prefix, combo key, or id-as-citation is visible (${keyHits.length} found)`)

  /* ============================================================= class 4 */
  say('\n=== C4: every card names a real source or method ===')
  const cardless = figures.filter((f) => !f.hasCard)
  const idLabelled = figures.filter((f) => {
    const l = (f.cardLabel || '').replace(/^(Source|Method):\s*/, '').trim()
    return l && SOURCE_ID_ANYWHERE.test(l)
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
    // ...and whose content is not reachable any other way. CI caught the
    // distinction this needs: `.wrow-name` renders "United Arab Emirates"
    // at 68% on the Linux runner's fonts (80% on Windows), and it is a
    // LABEL whose full text is in the row's own accessible name, beside a
    // flag and an ISO code. Package 24's defect was a 100-character
    // refusal SENTENCE at 31% with no other route to it. The rule is
    // "the reader cannot get to this content", not "an ellipsis exists".
    .filter((c) => c.shownPct < 70 && c.text.length > 12 && !c.interactive && !c.recoverable)
    .map((c) => ({ page: p.id, ...c })))
  clipped.slice(0, 6).forEach((c) => say(`    ${c.shownPct}%  ${c.page} :: ${c.text.slice(0, 60)}`))
  check(clipped.length === 0,
    `C5: no clipped text is unreachable — no tap target, and not in the row's accessible name `
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
  for (const p of [...pages, ...themed]) {
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
