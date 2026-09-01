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
import { launch, openPage } from './cdp.mjs'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const OUT = process.env.INVENTORY_OUT ?? '.status/evidence/p25-inventory.json'

/* The in-page extractor. Everything this returns is read off the rendered
 * DOM; nothing is inferred from source. Kept as one string so it runs in a
 * single round trip per page — 90+ entities x a round trip per figure would
 * be minutes of latency, and latency is why audits get skipped. */
const EXTRACT = String.raw`
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
      if (card) { cardText = norm(card.innerText); cardLabel = card.getAttribute('aria-label') }
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
    if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0) {
      const cs = getComputedStyle(el)
      if (cs.overflow === 'visible' && cs.overflowX === 'visible') continue
      clipped.push({
        text: norm(el.innerText).slice(0, 120),
        cls: String(el.className || el.tagName),
        scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
        shownPct: Math.round((el.clientWidth / el.scrollWidth) * 100),
        title: el.getAttribute('title'),
        interactive: !!el.closest('button,a,[tabindex]'),
      })
    }
  }

  // Marks whose meaning is carried by colour/shape, with the colour of what
  // sits behind them, so contrast can be checked pair-by-pair rather than
  // every element against the page background.
  const MARK_SEL = '.wrow-track, .wrow-marker, .wrow-quartile, .chip, [class*="pip"], .swarm-mark, .mdot-mark'
  const marks = [...document.querySelectorAll(MARK_SEL)].slice(0, 400).map((el) => {
    const cs = getComputedStyle(el)
    const parent = el.parentElement ? getComputedStyle(el.parentElement) : null
    const r = el.getBoundingClientRect()
    return {
      cls: String(el.className || el.tagName),
      color: cs.backgroundColor, borderColor: cs.borderTopColor, textColor: cs.color,
      behind: parent ? parent.backgroundColor : null,
      behindCls: el.parentElement ? String(el.parentElement.className || el.parentElement.tagName) : null,
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

async function capture(page, id, url, waitMs = 2600) {
  await page.hashGo(url, { waitMs })
  const raw = await page.eval(EXTRACT, { awaitPromise: true })
  return { id, url, ...JSON.parse(raw), consoleErrors: page.consoleErrors() }
}

const core = JSON.parse(readFileSync('site/public/data/core.json', 'utf8'))
const coreData = core.data ?? core
const cities = (coreData.cities ?? []).map((c) => c.id)
const countries = (coreData.countries ?? []).map((c) => c.iso2 ?? c.code ?? c.id).filter(Boolean)

const targets = [
  ['work', `${BASE}#/work?years=8`],
  ['work-y20', `${BASE}#/work?years=20`],
  ['work-country-DK', `${BASE}#/work?years=8&country=DK`],
  ['openings', `${BASE}#/openings`],
  ['compare', `${BASE}#/compare`],
  ['explore', `${BASE}#/explore`],
  ['explore-money', `${BASE}#/explore/money`],
  ['explore-housing', `${BASE}#/explore/housing`],
  ['explore-jobs', `${BASE}#/explore/jobs`],
  ['explore-life', `${BASE}#/explore/life`],
  ['data', `${BASE}#/data`],
  ['postings-seed', `${BASE}#/data/postings-seed`],
  ...countries.map((cc) => [`country-${cc}`, `${BASE}#/country/${cc}`]),
  ...cities.map((id) => [`city-${id}`, `${BASE}#/city/${id}`]),
]

const { port, close } = await launch()
const started = new Date().toISOString()
try {
  const page = await openPage(port)
  await page.viewport(1440, 900)
  const pages = []
  let n = 0
  for (const [id, url] of targets) {
    n += 1
    process.stdout.write(`  [${String(n).padStart(3)}/${targets.length}] ${id}\n`)
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
  console.log('\n' + JSON.stringify(totals, null, 1))
  console.log('wrote', OUT)
  page.close()
} finally { close() }
