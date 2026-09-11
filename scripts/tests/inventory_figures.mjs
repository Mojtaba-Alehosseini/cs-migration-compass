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
import { pathToFileURL, fileURLToPath } from 'node:url'

/* Paths are resolved from THIS FILE, not the working directory. CI runs
 * the suite with working-directory: site, so a bare
 * 'site/public/data/core.json' resolved to site/site/... and the whole
 * suite died with ENOENT after every other check had passed — a failure
 * only CI could produce, because every local run happens from the repo
 * root. */
export const REPO = fileURLToPath(new URL('../../', import.meta.url))
import { launch, openPage } from './cdp.mjs'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const OUT = process.env.INVENTORY_OUT ?? null   // resolved against REPO below

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
    let cardText = null, cardLabel = null, cardBare = null, cardLinks = []
    try {
      b.click()
      // Poll for the card instead of assuming 25ms is enough to open one. A
      // card that opened slowly used to be recorded as "no card at all",
      // which C4 reads as a violation -- a timing guess manufacturing a
      // finding. 600ms cap; the loop exits the moment it appears.
      let card = null
      for (let i = 0; i < 60 && !card; i++) {
        card = document.querySelector('[role="dialog"]')
        if (!card) await new Promise((r) => setTimeout(r, 10))
      }
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
        /* The card's own text with its anchors removed, for the same reason
         * the page has one: a file name a reader can only READ is a different
         * thing from one they can open. Cards are shut again before the page
         * snapshot is taken, so without this the card bodies -- which is where
         * this site names most of its files -- were invisible to that check. */
        const clone = card.cloneNode(true)
        for (const a of clone.querySelectorAll('a')) a.remove()
        cardBare = norm(clone.textContent)
        /* Each anchor's text against where it actually points, so "named one
         * file and linked another" is catchable: two cards used to read
         * "NEEDS-DECISION.md →" while navigating to /data. */
        cardLinks = [...card.querySelectorAll('a')].map((a) => ({
          text: norm(a.textContent), href: a.getAttribute('href') || '',
        }))
      }
      b.click()
      // And wait for it to actually be gone, so the next figure's poll cannot
      // read the previous figure's still-closing card as its own.
      for (let i = 0; i < 60 && document.querySelector('[role="dialog"]'); i++) {
        await new Promise((r) => setTimeout(r, 10))
      }
    } catch (e) { cardText = 'ERROR: ' + e.message }
    const cell = b.closest('td,th,li,[class*="wrow-"],div')
    figures.push({
      kind, visible, cardLabel, cardText, cardBare, cardLinks,
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
        // Whether the clipped text is still reachable somewhere in its own
        // row: the accessible label, or a title on an ancestor. A country
        // NAME ellipsised in a fixed column is not the same defect as a
        // refusal SENTENCE cut to 31% with no other route to it -- the row
        // still carries the full name in its screen-reader text, and the
        // flag and ISO code identify it besides. Recorded rather than
        // judged here; the assertion decides what to do with it.
        recoverable: (() => {
          const row = el.closest('[data-cc], tr, li, .panel')
          if (!row) return false
          const full = norm(el.innerText)
          if (!full) return false
          const alt = norm([...row.querySelectorAll('.visually-hidden, .sr-only')]
            .map((n) => n.textContent).join(' ')) + ' ' + norm(row.getAttribute('title') || '')
          return alt.includes(full)
        })(),
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
  // .wrow-vacant is the marker's third state (package 44, #81) — published,
  // but not placed. A mark the instrument cannot see is a mark nothing checks,
  // so it joins the selector the day it is drawn rather than the day someone
  // notices the corpus count never moved.
  const MARK_SEL = '.wrow-track, .wrow-marker, .wrow-vacant, .wrow-quartile, .chip, [class*="pip"], .swarm-mark, .mdot-mark'
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
    // SVG marks have no background-color at all — their paint is the fill property, on
    // the element or its child shape. Reading backgroundColor made every
    // .mdot-mark fall through to its 1px ring while its actual colour was
    // never looked at, so /compare's marks were scored on two colours that
    // are not the mark.
    const isSvg = el instanceof SVGElement
    const svgFill = isSvg
      ? (cs.fill && cs.fill !== 'none' ? cs.fill
         : (el.querySelector('*') ? getComputedStyle(el.querySelector('*')).fill : null))
      : null
    const fillOpaque = isSvg ? opaque(svgFill) : opaque(cs.backgroundColor)
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

    /* A WRAPPER THAT PAINTS NOTHING ITSELF. SwarmField wraps a <Flag> SVG in a
     * span: the span has a transparent background and a 0px border, so every
     * branch below used to fall through to borderTopColor — a colour on
     * a zero-width border, which is never painted. C6 scored rgb(25,24,19)
     * against a backdrop, got 1.00:1, and reported an invisible thing as a
     * contrast failure. Same shape as the .mdot-mark note above (paint living
     * somewhere other than backgroundColor), on an element that is not itself
     * an SVG so the svgFill branch never ran.
     *
     * Two cases, and they are genuinely different:
     *   - selected: the 2.5px box-shadow ring IS the mark's separation from
     *     the page, so that is the colour to measure, against what sits
     *     behind the RING rather than against the ring itself.
     *   - unselected: the mark's paint is a multi-colour flag. There is no
     *     single colour to score, so it is recorded UNMEASURABLE rather than
     *     compared against something it is not — the same discipline as the
     *     below-the-fold marks: excluded, and counted, never assumed passing. */
    const paintsNothingItself = !isChip && !isSvg && !fillOpaque && !hasRing
    const childArt = paintsNothingItself ? el.querySelector('svg, img') : null
    const ringIsMeaning = paintsNothingItself && !!haloColor

    return {
      cls: String(el.className || el.tagName),
      kind: isChip ? 'text-chip' : 'non-text',
      // the colour that carries this mark's meaning
      meaningColor: isChip ? cs.color
        : ringIsMeaning ? haloColor
        : (isSvg && fillOpaque) ? svgFill
        : (hasRing ? cs.borderTopColor : (fillOpaque ? cs.backgroundColor : cs.borderTopColor)),
      meaningFrom: isChip ? 'text'
        : ringIsMeaning ? 'ring'
        : (hasRing ? 'border' : (fillOpaque ? 'fill' : 'border')),
      // A wrapper whose only paint is a child image, with no ring to measure.
      unmeasurable: !!childArt && !ringIsMeaning,
      ownBackground: cs.backgroundColor,
      // When the ring is the meaning, the ring's own colour cannot also be
      // its backdrop; compare it to what is painted behind the mark.
      behind: ringIsMeaning ? behind : (haloColor || behind),
      behindCls: ringIsMeaning ? behindCls : (haloColor ? 'its own halo ring' : behindCls),
      onScreen,
      w: Math.round(r.width), h: Math.round(r.height),
      left: el.style.left || null,
    }
  })

  // Per-row cells, so an assertion can ask what THIS country's own cell says
  // rather than whether a digit string appears somewhere on the page.
  const rows = Object.fromEntries([...document.querySelectorAll('.wrow[data-cc]')].map((r) => [
    r.dataset.cc,
    {
      key: r.dataset.key ?? null,
      openings: norm(r.querySelector('.wrow-opn') ? r.querySelector('.wrow-opn').innerText : ''),
      estimate: norm(r.querySelector('.wrow-est') ? r.querySelector('.wrow-est').innerText : ''),
    },
  ]))

  /* The same page text with every ANCHOR removed, so a check can tell a file
   * name a reader can open from one they can only read (NEEDS-DECISION #70).
   * <noscript> and <title> come out too: the first renders only with scripting
   * off and the second is a tooltip, so neither is prose and neither can carry
   * a link. textContent, not innerText, because a detached clone has no layout
   * and innerText would come back empty. */
  const bare = (() => {
    const clone = document.body.cloneNode(true)
    for (const el of clone.querySelectorAll('a, noscript, title')) el.remove()
    return norm(clone.textContent)
  })()

  const pageLinks = [...document.querySelectorAll('a')].map((a) => ({
    text: norm(a.textContent), href: a.getAttribute('href') || '',
  }))

  return JSON.stringify({
    figures, nodata, clipped, marks, rows,
    text: norm(document.body.innerText),
    unlinkedText: bare,
    pageLinks,
    headings: [...document.querySelectorAll('h1,h2,h3')].map((h) => norm(h.textContent)).filter(Boolean),
  })
})()
`

/* Waits for the route to be READY.
 *
 * The previous version polled `button, .nodata, h1, h2, table, .wrow` until
 * that count was stable and non-zero. It looked like a readiness check and was
 * not one, because the page SHELL supplies those elements before any route
 * data arrives. Measured on `/openings`:
 *
 *     t=208ms   4 elements, 0 rows,     829 chars   <- shell
 *     t=616ms   4 elements, 0 rows,     829 chars   <- declared READY here
 *     t=726ms  16 elements, 100 rows, 14459 chars   <- the route's own content
 *
 * Stable and non-zero, 110ms too early, three runs in four. That is the same
 * defect as the assertions it feeds: satisfied by absence. No stability window
 * fixes it either — the shell count does not move for the whole duration of
 * that 24 MiB fetch, so a longer window is still a race, just a slower one.
 *
 * `waitForReady()` requires the network to be idle as well, which is the fact
 * a DOM count cannot stand in for, and a timeout THROWS — the caller records
 * it as an errored route, and the coverage floors fail the run. Absence is now
 * loud twice over. */
export async function capture(page, id, url, { timeoutMs = 25000, setup = null } = {}) {
  if (setup) {
    /* Bounce through a route that does not exist before navigating to the
     * target. Setting `location.href` to the hash you are already on is a
     * no-op for the router, so a state target that follows its own base route
     * would inherit whatever the previous capture left behind — package 33's
     * classifier chained /openings' no-data marks 7 -> 47 -> 83 -> 61 exactly
     * that way, and every baseline in that run was the previous case's result.
     * NotFound is the cheapest thing to unmount through. */
    await page.hashGo(url.replace(/#.*$/, '#/no-such-route'))
    await page.waitForReady({ quietMs: 300, timeoutMs, label: `${id} — remount` })
  }
  await page.hashGo(url)
  await page.waitForReady({ quietMs: 300, timeoutMs, label: `${id} — ${url}` })
  if (setup) {
    /* Several controls sit in panels behind DeferUntilVisible — the weights
     * tool, the scatter builder, the climate matcher. They do not exist in the
     * DOM until they are scrolled near, so a setup for one of them would fail
     * to find its control on a page that is otherwise perfectly rendered. */
    await page.eval('window.scrollTo(0, document.body.scrollHeight)')
    await page.waitForReady({ quietMs: 300, timeoutMs, label: `${id} — deferred panels` })
    await page.eval(SETUP_HELPERS)
    const applied = await page.eval(setup)
    if (typeof applied === 'string' && applied.startsWith('NO ')) {
      /* The control this state is defined by is not on the page. That is a
       * failure, not a state to capture: it means either the control moved or
       * the page did not finish rendering, and capturing anyway would file the
       * DEFAULT state under the state's name and quietly restore exactly the
       * blindness this whole line of work is closing. */
      throw new Error(`setup for "${id}" did not find its control: ${applied}`)
    }
    await page.waitForReady({ quietMs: 300, timeoutMs, label: `${id} — after setup` })
  }
  const raw = await page.eval(EXTRACT, { awaitPromise: true })
  return { id, url, ...JSON.parse(raw), consoleErrors: page.consoleErrors() }
}

/* Page-side helpers for state setups. Kept here rather than repeated in each
 * setup expression so a selector fix lands in one place.
 *
 * Every one of these exists because package 33's classifier got it wrong once:
 * `sel` matches the WRAPPING label (this site's labels wrap their select, so
 * the label text is not in the select's own textContent); `input` falls back
 * to `input:not([type])` (a type=text selector misses an input with no type
 * attribute); `keys` exists because the base-year control is a draggable
 * handle that answers arrow keys and can never be clicked. */
export const SETUP_HELPERS = String.raw`
window.__h = {
  norm: (s) => (s ?? '').replace(/[\s ]+/g, ' ').trim(),
  btn(re) {
    const b = [...document.querySelectorAll('button')].find((x) => new RegExp(re, 'i').test(window.__h.norm(x.textContent)))
    if (!b) return 'NO BUTTON matching ' + re
    b.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); b.click(); return 'ok'
  },
  sel(labelRe, value) {
    const re = new RegExp(labelRe, 'i')
    const s = [...document.querySelectorAll('select')].find((x) => {
      const lab = x.closest('label')
      return re.test(window.__h.norm(x.getAttribute('aria-label') || ''))
        || (lab && re.test(window.__h.norm((lab.childNodes[0] && lab.childNodes[0].textContent) || '')))
    })
    if (!s) return 'NO SELECT matching ' + labelRe
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(s, value)
    s.dispatchEvent(new Event('change', { bubbles: true })); return 'ok'
  },
  input(v, sel) {
    const el = document.querySelector(sel || 'input[type="text"]') || document.querySelector('input:not([type])')
    if (!el) return 'NO INPUT ' + (sel || 'text')
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v)
    el.dispatchEvent(new Event('input', { bubbles: true })); return 'ok'
  },
  click(sel) {
    const el = document.querySelector(sel)
    if (!el) return 'NO ELEMENT ' + sel
    el.click(); return 'ok'
  },
  keys(sel, key, n) {
    const el = document.querySelector(sel)
    if (!el) return 'NO ELEMENT ' + sel
    el.focus()
    for (let i = 0; i < n; i++) el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
    return 'ok'
  },
}; 'ready'`

export function defaultTargets(base = BASE) {
  const core = JSON.parse(readFileSync(REPO + 'site/public/data/core.json', 'utf8'))
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
      // Added after the package-25 adversarial review: the first target list
      // claimed "every route the site can display" and skipped the eager
      // landing route, the 404, three of Explore's own seven themes, and
      // every state that needs a selection or a non-default occupation --
      // including PayVsCost, which holds the one value this package changed
      // and the one sentence it wrote.
      ['home', base],
      ['not-found', `${base}#/no-such-route`],
      ['explore-visa', `${base}#/explore/visa`],
      ['explore-people', `${base}#/explore/people`],
      ['explore-climate', `${base}#/explore/climate`],
      ['compare-selected', `${base}#/compare?places=oslo,copenhagen,berlin`],
      ['work-payvscost', `${base}#/work?years=8&places=oslo,copenhagen`],
      ['work-occ-2511', `${base}#/work?years=8&occupation=isco08:2511`],
      ...countries.map((cc) => [`country-${cc}`, `${base}#/country/${cc}`]),
      ...cities.map((id) => [`city-${id}`, `${base}#/city/${id}`]),

      /* MATERIAL STATE — the states a visitor can reach that the address
       * cannot. Package 33 exercised every control on every route and found
       * that ALL 28 of them change something these assertions read; nothing
       * was presentational. Until this list existed, every "0 violations"
       * result described the default state of every page.
       *
       * The two that matter most are currency conversions, which is exactly
       * the class C4 exists for: /openings renders 0 figures by default and
       * 93 once a currency is chosen, /work 41 and 109. None of those 161 had
       * ever been examined.
       *
       * One capture per control from a clean baseline, plus the single
       * combination already proven to matter (500 rows with a currency), not
       * a combinatorial sweep. A full sweep of the 28 controls in pairs would
       * be 378 captures and roughly six minutes of extra wall-clock for
       * states nobody has evidence of caring about; this is 25 captures and
       * about 40 seconds. */
      ...STATE_TARGETS(base),
    ].filter(([id]) => !SKIP.has(id)),
  }
}

/* Test-only: drop targets by id, so "what happens when a state stops being
 * captured?" is a command anyone can run rather than a temporary edit someone
 * has to remember to undo.
 *
 *     INVENTORY_SKIP=st-openings-currency node scripts/tests/test_figure_inventory.mjs
 *
 * The coverage floors are recorded per target id, so a skipped target has a
 * floor and no capture — which is exactly the "route silently stopped
 * contributing" case, and it fails. */
const SKIP = new Set((process.env.INVENTORY_SKIP ?? '').split(',').map((s) => s.trim()).filter(Boolean))

/** [id, url, setup] — the setup runs after readiness, before extraction. */
function STATE_TARGETS(base) {
  return [
    ['st-home-question', `${base}#/`, `window.__h.btn('Where can you actually buy a home')`],
    ['st-home-search', `${base}#/`, `window.__h.input('osl')`],
    ['st-home-place', `${base}#/`, `window.__h.btn('^Stockholm$')`],

    ['st-openings-country', `${base}#/openings`, `window.__h.sel('Country', 'DE')`],
    ['st-openings-level', `${base}#/openings`, `window.__h.sel('Level', 'senior')`],
    ['st-openings-remote', `${base}#/openings`, `window.__h.click('input[type="checkbox"]')`],
    ['st-openings-query', `${base}#/openings`, `window.__h.input('engineer')`],
    ['st-openings-currency', `${base}#/openings`, `window.__h.sel('Show pay in', 'AUD')`],
    ['st-openings-map', `${base}#/openings`, `window.__h.btn('^Map$')`],
    ['st-openings-500', `${base}#/openings`, `window.__h.btn('Show 400 more')`],
    // The proven combination: 176 figures, 324 no-data marks.
    ['st-openings-500-aud', `${base}#/openings`,
      `(() => { const a = window.__h.sel('Show pay in', 'AUD'); if (a !== 'ok') return a; return window.__h.btn('Show 400 more') })()`],

    ['st-compare-hidemap', `${base}#/compare`, `window.__h.btn('hide map')`],
    ['st-work-currency', `${base}#/work?years=8`, `window.__h.sel('Show pay in', 'AUD')`],
    ['st-city-alljobs', `${base}#/city/berlin`, `window.__h.btn('All jobs')`],
    ['st-country-origin', `${base}#/country/DE`, `window.__h.input('iran')`],
    ['st-data-details', `${base}#/data`, `(() => { const d = document.querySelector('details'); if (!d) return 'NO ELEMENT details'; d.open = true; return 'ok' })()`],
    ['st-seed-provider', `${base}#/data/postings-seed`, `window.__h.sel('Filter companies by provider', 'ashby')`],

    ['st-money-lens', `${base}#/explore/money`, `window.__h.btn('indexed to 1990')`],
    ['st-money-picks', `${base}#/explore/money`, `window.__h.btn('^AE$')`],
    ['st-money-scatter', `${base}#/explore/money`, `window.__h.sel('across', 'net_pct')`],
    // A draggable handle, not a button: it answers arrow keys and a click does nothing.
    ['st-housing-base', `${base}#/explore/housing`, `window.__h.keys('.baser', 'ArrowRight', 8)`],
    ['st-jobs-onebyone', `${base}#/explore/jobs`, `window.__h.btn('one by one')`],
    ['st-jobs-window', `${base}#/explore/jobs`, `window.__h.btn('2004')`],
    ['st-people-weights', `${base}#/explore/people`, `window.__h.btn('Open the weights tool')`],
    ['st-climate-slider', `${base}#/explore/climate`, `window.__h.input('-5', 'input[type="range"]')`],
    ['st-climate-check', `${base}#/explore/climate`, `window.__h.click('input[type="checkbox"]')`],
  ]
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
    mkdirSync(REPO + '.status/evidence', { recursive: true })
    const out = OUT ?? (REPO + '.status/evidence/p25-inventory.json')
    writeFileSync(out, JSON.stringify({ generated_at: started, base: BASE, totals, pages }, null, 1), 'utf8')
    console.log(JSON.stringify(totals, null, 1))
    console.log('wrote', out)
    page.close()
  } finally { close() }
}
