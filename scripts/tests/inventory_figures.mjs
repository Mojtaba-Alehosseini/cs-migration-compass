/* Package 25, tier 2 — the inventory.
 *
 * Renders every (route x entity) the site can display and records what each
 * figure LITERALLY CONTAINS. Not what the component intends: what the DOM
 * says after React has run.
 *
 * Package 24 shipped a fabricated position on 6 of /work's 16 rows and an
 * em dash standing in for Italy's 28 real openings. Both were invisible to
 * code review and obvious the moment someone rendered all sixteen rows and
 * read them back. That method had never been applied to the other ~90
 * entities this site renders. This file applies it.
 *
 * Output: .status/evidence/p25-inventory.json — machine-readable on purpose.
 * A report a human skims is how six of sixteen rows got missed.
 *
 * Run:  node scripts/tests/inventory_figures.mjs
 * Needs a preview server on :4173 (npm run build && npm run preview).
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { launch, openPage } from './cdp.mjs'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const OUT = process.env.INVENTORY_OUT ?? '.status/evidence/p25-inventory.json'

/* The in-page extractor. Everything this returns is read off the rendered
 * DOM; nothing is inferred from source. Kept as one string so it runs in a
 * single round trip per page — 90+ entities x a round trip per figure would
 * be minutes of latency, and latency is why audits get skipped. */
export const EXTRACT = String.raw`
(async () => {
  const CARD_HINTS = /show where this number comes from|show how this number was calculated/i
  const norm = (s) => (s ?? '').replace(/\s+/g, ' ').trim()

  // A <Figure>/<Derived> trigger, its visible value, and what its own card
  // names as source or method. The card is opened and read, then closed —
  // its content only exists in the DOM while open.
  const figures = []
  const triggers = [...document.querySelectorAll('button')].filter((b) => CARD_HINTS.test(b.textContent || ''))
  for (const b of triggers) {
    const raw = norm(b.textContent)
    const kind = /calculated/i.test(raw) ? 'Derived' : 'Figure'
    const visible = norm(raw.replace(/[-—]?\s*show (where this number comes from|how this number was calculated)/i, ''))
    let cardText = null, cardLabel = null
    try {
      b.click()
      await new Promise((r) => setTimeout(r, 25))
      const card = document.querySelector('[role="dialog"]')
      // textContent, not innerText, as the fallback: innerText needs layout
      // and came back EMPTY for every <Derived> card on /explore while the
      // card was demonstrably open (its aria-label read back fine). Trusting
      // innerText alone would have recorded five real, richly-cited cards as
      // "no card at all" — an assertion firing for a reason other than the
      // property it names, which is the failure mode this whole package is
      // about.
      if (card) {
        cardText = norm(card.innerText) || norm(card.textContent)
        cardLabel = card.getAttribute('aria-label')
      }
      b.click()
      await new Promise((r) => setTimeout(r, 10))
    } catch (e) { cardText = 'ERROR: ' + e.message }
    const cell = b.closest('td,th,li,[class*="wrow-"],div')
    figures.push({
      kind, visible, cardLabel, cardText,
      hasCard: cardText != null && cardText.length > 0,
      container: cell ? String(cell.className || cell.tagName) : null,
      srText: norm([...b.querySelectorAll('.visually-hidden,.sr-only')].map((s) => s.textContent).join(' ')),
    })
  }

  // Every "no data" mark, with whatever text alternative it carries. This is
  // the class Italy's openings fell into: an em dash that meant "nothing
  // here" while the payload held 28.
  const nodata = [...document.querySelectorAll('.nodata, [data-nodata]')].map((el) => ({
    text: norm(el.innerText || el.textContent),
    title: el.getAttribute('title'),
    ariaHidden: el.getAttribute('aria-hidden'),
    container: el.parentElement ? String(el.parentElement.className || el.parentElement.tagName) : null,
    siblingSr: norm([...(el.parentElement ? el.parentElement.querySelectorAll('.visually-hidden,.sr-only') : [])]
      .map((s) => s.textContent).join(' ')),
  }))

  // Anything clipped by its own box. Package 24 found refusal reasons cut to
  // 31% of themselves, readable only by hovering.
  const clipped = []
  for (const el of document.querySelectorAll('*')) {
    if (!(el instanceof HTMLElement)) continue
    if (!el.innerText || el.children.length > 2) continue
    // Screen-reader-only text is clipped to a 1x1 box ON PURPOSE — that is
    // the technique, not a defect. Excluded explicitly rather than by
    // accident: without this the check reported 52 'truncations' that were
    // every visually-hidden label on the site.
    if (el.closest('.visually-hidden, .sr-only')) continue
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
      const cs = getComputedStyle(el)
      if (cs.overflow === 'visible' && cs.overflowX === 'visible') continue
      clipped.push({
        text: norm(el.innerText).slice(0, 120),
        cls: String(el.className || el.tagName),
        scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
        shownPct: Math.round((el.clientWidth / el.scrollWidth) * 100),
        title: el.getAttribute('title'),
        // A real tap target, not merely SOME focusable ancestor. This read
        // closest of button/a/[tabindex], and #main carries tabindex=-1
        // so the skip link can focus it — which made EVERY element on every
        // page 'interactive' and left the truncation check unable to fire at
        // all. Found by reproducing package 24's own clipped-refusal defect
        // and watching the check pass anyway.
        interactive: !!el.closest('button, a[href], [tabindex]:not([tabindex="-1"])'),
      })
    }
  }

  // Marks whose meaning is carried by colour/shape, with the colour of what
  // sits behind them, so contrast can be checked pair-by-pair rather than
  // every element against the page background.
  const MARK_SEL = '.wrow-track, .wrow-marker, .wrow-quartile, .chip, [class*="pip"], .swarm-mark, .mdot-mark'
  const HALO_RE = /(rgba?\([^)]*\)|color\(srgb[^)]*\))/
  const opaque = (c) => { const m = (c || '').match(/rgba?\([^)]*?(?:,\s*([\d.]+))?\)$/); return c && c !== 'transparent' && !(m && m[1] !== undefined && +m[1] === 0) }

  // What is ACTUALLY painted behind this mark, and which of its own colours
  // actually carries its meaning. Both matter, and the naive answers are
  // wrong in ways that make a contrast check lie:
  //
  //   * the DOM parent is not the visual backdrop. A quartile tick's parent
  //     is .wrow-track-wrap (light), but it is drawn ON .wrow-track (dark),
  //     an absolutely-positioned SIBLING. Comparing against the parent
  //     scored a legible 4.6:1 tick as 1.06:1.
  //   * a hollow marker's fill is deliberately the page surface; its meaning
  //     is the 2px ring around it. Comparing the fill scores the ring's own
  //     job as invisible.
  //   * a chip is text on a wash. Its meaning is the LABEL, which is a
  //     1.4.3 text-contrast question, not a 1.4.11 non-text one.
  //
  // elementsFromPoint gives the real paint stack at the mark's own centre.
  const marks = [...document.querySelectorAll(MARK_SEL)].slice(0, 400).map((el) => {
    const cs = getComputedStyle(el)
    const r = el.getBoundingClientRect()
    // Clamped inside the offsetParent: a quartile tick at left:100% has its
    // own centre HALF OFF the track it marks, so sampling the raw centre
    // read the page panel and scored a 4.6:1 tick as 1.11:1.
    const host = el.offsetParent ? el.offsetParent.getBoundingClientRect() : null
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))
    const cx = Math.round(host ? clamp(r.left + r.width / 2, host.left + 1, host.right - 1)
                               : r.left + r.width / 2)
    const cy = Math.round(host ? clamp(r.top + r.height / 2, host.top + 1, host.bottom - 1)
                               : r.top + r.height / 2)
    // A mark below the fold cannot be measured this way: elementsFromPoint
    // reads VIEWPORT coordinates, so an off-screen mark returns whatever
    // happens to sit at that point on screen. Recorded as unmeasurable
    // rather than silently compared against the wrong thing.
    const onScreen = !!(r.width && r.height && cx >= 0 && cy >= 0 && cx < innerWidth && cy < innerHeight)
    let behind = null, behindCls = null
    if (onScreen) {
      const stack = document.elementsFromPoint(cx, cy)
      const from = stack.indexOf(el)
      for (const cand of stack.slice(from < 0 ? 0 : from + 1)) {
        const bg = getComputedStyle(cand).backgroundColor
        if (opaque(bg)) { behind = bg; behindCls = String(cand.className || cand.tagName); break }
      }
    }
    const isChip = /(^|\s)chip(\s|-|$)/.test(String(el.className))
    const fillOpaque = opaque(cs.backgroundColor)
    // A ring drawn with box-shadow IS the separation between this mark and
    // whatever it sits on: .wrow-marker puts a 2px surface-coloured halo
    // around itself precisely so a filled dot reads against a same-hue
    // track. Comparing the dot to the track directly scores a separation
    // that exists as though it did not.
    // A marker with a visible ring carries its meaning in the RING, whether
    // or not it also has a fill: .wrow-marker.hollow fills itself with the
    // page surface on purpose, and comparing that fill to its own
    // surface-coloured halo scored the hollow state at 1.00:1 while the
    // ring that actually distinguishes it measures 4.5:1.
    const hasRing = parseFloat(cs.borderTopWidth) > 0 && opaque(cs.borderTopColor)
    const haloMatch = (cs.boxShadow || '').match(HALO_RE)
    const haloColor = haloMatch ? haloMatch[1] : null
    return {
      cls: String(el.className || el.tagName),
      kind: isChip ? 'text-chip' : 'non-text',
      // the colour that carries this mark's meaning
      meaningColor: isChip ? cs.color : (hasRing ? cs.borderTopColor
        : (fillOpaque ? cs.backgroundColor : cs.borderTopColor)),
      meaningFrom: isChip ? 'text' : (hasRing ? 'border' : (fillOpaque ? 'fill' : 'border')),
      ownBackground: cs.backgroundColor,
      behind: haloColor || behind,
      behindCls: haloColor ? 'its own halo ring' : behindCls,
      onScreen,
      w: Math.round(r.width), h: Math.round(r.height),
      left: el.style.left || null,
    }
  })

  return JSON.stringify({
    figures, nodata, clipped, marks,
    text: norm(document.body.innerText),
    headings: [...document.querySelectorAll('h1,h2,h3')].map((h) => norm(h.textContent)).filter(Boolean),
  })
})()
`

/* Waits for the route to be READY rather than for a fixed 2.6s. A hundred
 * pages x a worst-case sleep is five minutes, which is the difference
 * between an assertion suite CI runs on every push and one someone
 * remembers to run. Readiness = the route has painted something with a
 * figure, a no-data mark or a heading, and has stopped growing. */
export async function capture(page, id, url, { maxMs = 6000 } = {}) {
  await page.hashGo(url, { waitMs: 150 })
  await page.eval(`
    (async () => {
      const t0 = performance.now()
      let last = -1, stable = 0
      while (performance.now() - t0 < ${maxMs}) {
        const n = document.querySelectorAll('button, .nodata, h1, h2, table, .wrow').length
        if (n === last && n > 0) { if (++stable >= 3) return true } else { stable = 0; last = n }
        await new Promise((r) => setTimeout(r, 60))
      }
      return false
    })()
  `, { awaitPromise: true })
  const raw = await page.eval(EXTRACT, { awaitPromise: true })
  return { id, url, ...JSON.parse(raw), consoleErrors: page.consoleErrors() }
}

export function defaultTargets(base = BASE) {
  const core = JSON.parse(readFileSync('site/public/data/core.json', 'utf8'))
  const coreData = core.data ?? core
  const cities = (coreData.cities ?? []).map((c) => c.id)
  const countries = (coreData.countries ?? []).map((c) => c.iso2 ?? c.code ?? c.id).filter(Boolean)
  return {
    cities,
    countries,
    targets: [
      ['work', `${base}#/work?years=8`],
      ['work-y20', `${base}#/work?years=20`],
      ['work-country-DK', `${base}#/work?years=8&country=DK`],
      ['openings', `${base}#/openings`],
      ['compare', `${base}#/compare`],
      ['explore', `${base}#/explore`],
      ['explore-money', `${base}#/explore/money`],
      ['explore-housing', `${base}#/explore/housing`],
      ['explore-jobs', `${base}#/explore/jobs`],
      ['explore-life', `${base}#/explore/life`],
      ['data', `${base}#/data`],
      ['postings-seed', `${base}#/data/postings-seed`],
      ...countries.map((cc) => [`country-${cc}`, `${base}#/country/${cc}`]),
      ...cities.map((id) => [`city-${id}`, `${base}#/city/${id}`]),
    ],
  }
}


/* Everything below runs ONLY when this file is executed directly.
 * It was top-level, so `import { capture } from './inventory_figures.mjs'`
 * ran the entire 100-page sweep as an import side effect — the assertion
 * suite that imports it was doing the whole inventory twice, once
 * invisibly. Found by importing it from a scratch probe and watching the
 * sweep start on its own. */
/* Everything below runs ONLY when this file is executed directly.
 * It used to be top-level, so `import { capture } from './inventory_figures.mjs'`
 * ran the entire 100-page sweep as an import side effect — the assertion
 * suite that imports it was doing the whole inventory twice, once
 * invisibly. Found by importing it from a scratch probe and watching the
 * sweep start on its own. */
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const { targets, countries, cities } = defaultTargets(BASE)
  const { port, close } = await launch()
  const started = new Date().toISOString()
  try {
    const page = await openPage(port)
    await page.viewport(1440, 900)
    const pages = []
    let n = 0
    for (const [id, url] of targets) {
      n += 1
      process.stdout.write(`  [${String(n).padStart(3)}/${targets.length}] ${id}` + String.fromCharCode(10))
      try {
        pages.push(await capture(page, id, url))
      } catch (e) {
        pages.push({ id, url, error: String((e && e.message) || e), figures: [], nodata: [], clipped: [], marks: [] })
      }
    }
    const totals = {
      routes: targets.length,
      entities: countries.length + cities.length,
      countries: countries.length,
      cities: cities.length,
      figures: pages.reduce((a, p) => a + (p.figures?.length ?? 0), 0),
      nodata: pages.reduce((a, p) => a + (p.nodata?.length ?? 0), 0),
      clipped: pages.reduce((a, p) => a + (p.clipped?.length ?? 0), 0),
      marks: pages.reduce((a, p) => a + (p.marks?.length ?? 0), 0),
      pagesWithError: pages.filter((p) => p.error).length,
    }
    mkdirSync('.status/evidence', { recursive: true })
    writeFileSync(OUT, JSON.stringify({ generated_at: started, base: BASE, totals, pages }, null, 1), 'utf8')
    console.log(JSON.stringify(totals, null, 1))
    console.log('wrote', OUT)
    page.close()
  } finally { close() }
}
