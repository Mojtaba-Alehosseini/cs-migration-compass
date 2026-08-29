/* Package 13, Tier 0 — regression tests for the NINE client-side defects in
 * docs/REGRESSION-CATALOGUE.md that live in site/src/**.ts(x): R1, R2, R3
 * (package 6, chart integrity), R8, R9, R10, R11 (package 10, position and
 * estimate), R12, R13 (package 11, the position must answer its own question).
 *
 * These cannot be unit-tested the way the Python ones are: profile.ts's own
 * top-level import chain reaches store.ts, which reads import.meta.env.BASE_URL
 * — a Vite-injected global that does not exist under plain Node (confirmed by
 * trying the direct import first, this package). So the same harness every
 * package since 6 has used for UI gates: real headless Chrome via cdp.mjs
 * (this directory's own tracked copy — a dependency-free CDP driver every
 * prior package's own .status/evidence/ scripts also use, but that directory
 * is gitignored, and this is a PERMANENT suite that has to survive a fresh
 * CI checkout, not a one-off verification script; import from that gitignored
 * path failed exactly this way, ERR_MODULE_NOT_FOUND, the first time this
 * suite actually ran in CI), driving a real production build, reading the
 * actual rendered numbers.
 *
 * Prerequisite — a served production build:
 *     cd site && npm run build && npm run preview      # http://localhost:4173/
 * Override with BASE=... for another origin. In CI, set CHROME_PATH to
 * wherever the runner's own Chrome lives (ubuntu-latest: google-chrome-stable
 * is on PATH) — cdp.mjs's own default is a Windows-only path.
 *
 * Every number asserted below is the catalogue's own before/after pair, not a
 * value read off this run. Where the fix produced a specific figure (SE P37 at
 * 49,673; NO's flat "0-39" band; Milan's 2,314 outside a 150-year domain) the
 * PRE-FIX answer is pinned too, so a regression fails even if some unrelated
 * change happened to leave the primary assertion true by coincidence.
 */

import { readFileSync } from 'node:fs'
import { launch, openPage, sleep } from './cdp.mjs'

const BASE = process.env.BASE ?? 'http://localhost:4173/'

let fails = 0
const say = (s = '') => console.log(s)
const check = (ok, label) => { say(`${ok ? 'PASS' : 'FAIL'}  ${label}`); if (!ok) fails++ }

/* cdp.mjs's launch() attaches to whatever already answers on its port, so a
 * leftover browser from an earlier run silently hijacks the session (it opens a
 * tab in a browser whose profile directory has already been deleted, and hangs).
 * Pick a port nothing is listening on instead. */
async function freeCdpPort(start = 9350) {
  for (let p = start; p < start + 40; p++) {
    try {
      const r = await fetch(`http://127.0.0.1:${p}/json/version`, { signal: AbortSignal.timeout(500) })
      if (r.ok) continue
    } catch { return p }
  }
  throw new Error(`no free CDP port in ${start}..${start + 39}`)
}

const preview = await fetch(BASE).catch(() => null)
if (!preview?.ok) {
  console.error(`No site served at ${BASE}.`)
  console.error('Run:  cd site && npm run build && npm run preview')
  process.exit(2)
}

const SCATTER_PANEL = `[...document.querySelectorAll('h2')]
  .find((h) => h.textContent.includes('Ask your own question')).closest('.panel')`

const { port, close } = await launch({ port: await freeCdpPort() })
try {
  const page = await openPage(port)
  await page.viewport(1280, 2000)

  /* One real load; everything after it is hash routing (cdp.mjs's own goto()
   * waits for a load event a hash change never fires). That also keeps the
   * console.error hook installed below alive for the whole run. */
  await page.goto(`${BASE}#/explore/housing`, { waitMs: 3000 })

  /* assertInjectiveTicks() throws in dev but only console.error()s in a
   * production build, which is what this suite runs against — so R2 reads the
   * guard's real shipped output rather than an exception. Hooked here, not read
   * from CDP's Log domain, so the deliberate trigger in R2 can be told apart
   * from an incidental error. */
  await page.eval(`(() => {
    window.__errs = []
    const orig = console.error
    console.error = (...a) => { window.__errs.push(a.map(String).join(' ')); orig.apply(console, a) }
  })()`)

  /* --- shared helpers ------------------------------------------------- */

  /** A country's own row in the position table, by the key it renders
   *  (`SE`, `CA-21231`, ...). Package 24 gave each row a stable
   *  `data-key` attribute (Canada's two NOC rows share `data-cc="CA"` but
   *  not `data-key`) specifically so this suite would not have to infer a
   *  row from its own DOM shape — the previous version matched on "a div
   *  with exactly 3 children", which was CountryRow's own old grid and
   *  broke silently (every check here returning null/0, not a loud
   *  failure) the moment package 24's CountryStripRow gave a row 4
   *  children instead. */
  const rowText = (code) => page.eval(`document.querySelector('[data-key=${JSON.stringify(code)}]')?.textContent ?? null`)
  const rowCount = (code) => page.eval(`document.querySelectorAll('[data-key=${JSON.stringify(code)}]').length`)
  const pct = (text) => { const m = text?.match(/P(\d+)/); return m ? Number(m[1]) : null }

  /** How many WAGE method-card triggers a row renders — the position
   *  <Figure> (.wrow-strip) and the estimate <Derived> (.wrow-est). Package
   *  24 gave every row with postings data a THIRD, independent trigger
   *  (.wrow-opn's own openings <Figure>) that fires regardless of wage
   *  comparability — counting every <button> in the row would let that
   *  unrelated cell contaminate what R8 actually tests (whether a
   *  comparability refusal suppresses the WAGE triggers specifically), so
   *  .wrow-opn is deliberately excluded here. */
  const rowTriggers = (code) => page.eval(`(() => {
    const row = document.querySelector('[data-key=${JSON.stringify(code)}]')
    return row ? row.querySelectorAll('.wrow-strip button, .wrow-est button').length : null
  })()`)

  /** Open one row's method card and read it back. `which` is 0 for the
   *  position's <Figure>, 1 for the estimate's <Derived> — the SAME order
   *  CountryStripRow renders them in (position's trigger sits above the
   *  strip, the estimate's own trigger to its right), matching the old
   *  CountryRow's own order this suite was originally written against. */
  async function openCard(code, which) {
    const opened = await page.eval(`(() => {
      const row = document.querySelector('[data-key=${JSON.stringify(code)}]')
      const btns = [...(row?.querySelectorAll('button') ?? [])]
      if (!btns[${which}]) return false
      btns[${which}].click()
      return true
    })()`)
    await sleep(350)
    const text = await page.eval(`(() => {
      const d = [...document.querySelectorAll('[role="dialog"]')].pop()
      return d ? d.textContent : null
    })()`)
    await page.eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`)
    await sleep(250)
    return opened ? text : null
  }

  /** Scroll the scatter into view — Explore defers it until it is near the
   *  viewport, so it does not exist in the DOM before this. */
  async function showScatter() {
    await page.eval('window.scrollTo(0, document.body.scrollHeight)')
    await sleep(2200)
  }

  /** The scatter's own rendered y axis: each tick's label and the exact y its
   *  gridline sits on (the same Y() the points are placed with). The axis
   *  titles are excluded by their arrow glyphs and by not living in a tick <g>. */
  const scatterYAxis = () => page.eval(`(() => {
    const svg = ${SCATTER_PANEL}.querySelector('svg')
    return [...svg.querySelectorAll('g')]
      .map((g) => ({
        label: g.querySelector('text')?.textContent ?? null,
        anchor: g.querySelector('text')?.getAttribute('text-anchor') ?? null,
        y: Number(g.querySelector('line')?.getAttribute('y1')),
      }))
      .filter((t) => t.anchor === 'end' && t.label != null)
      .map((t) => ({ label: t.label, y: t.y }))
  })()`)

  const scatterPoint = (city) => page.eval(`(() => {
    const c = ${SCATTER_PANEL}.querySelector('circle[data-city=' + JSON.stringify(${JSON.stringify(city)}) + ']')
    if (!c) return null
    return {
      cy: Number(c.getAttribute('cy')),
      title: c.querySelector('title')?.textContent ?? '',
      offscale: c.hasAttribute('data-offscale'),
    }
  })()`)

  /** Value ↔ pixel from the axis the reader can actually see. */
  const tickValue = (label) => Number(label.replace(/[^\d.]/g, ''))
  function pixelFor(axis, value) {
    const a = axis[0], b = axis[axis.length - 1]
    return a.y + (value - tickValue(a.label)) * (b.y - a.y) / (tickValue(b.label) - tickValue(a.label))
  }

  /* ==================================================================== */
  say('=== R1: years-to-home reported past its own precision (Milan, Valencia) ===')

  await page.hashGo(`${BASE}#/city/milan`, { waitMs: 2200 })
  const milan = await page.eval(`(() => {
    const panel = [...document.querySelectorAll('h2')]
      .find((h) => h.textContent.includes('The path to owning a home')).closest('.panel')
    const mark = panel.querySelector('.unstable-mark')
    return {
      big: panel.querySelector('.big')?.textContent ?? null,
      mark: mark?.textContent ?? null,
      markLabel: mark?.getAttribute('aria-label') ?? null,
      note: panel.querySelector('.unstable-note')?.textContent ?? null,
    }
  })()`)
  say(`  Milan: ${milan.big} · mark=${JSON.stringify(milan.mark)}`)
  check(milan.mark === '≈', 'R1: Milan years-to-home carries the instability mark (.unstable-mark = "≈")')
  check(!!milan.big?.startsWith('≈'), `R1: the ≈ prefixes the figure itself, not a footnote (${milan.big})`)
  check(!!milan.note?.includes('$210'),
    'R1: Milan\'s note names the real savings figure the rounding swamps ($210/yr)')

  // Rome also reads "100+ yrs" and is NOT flagged: the mark tracks the
  // inputs' own precision, not the size of the number.
  await page.hashGo(`${BASE}#/city/rome`, { waitMs: 2000 })
  const rome = await page.eval(`(() => {
    const panel = [...document.querySelectorAll('h2')]
      .find((h) => h.textContent.includes('The path to owning a home')).closest('.panel')
    return { big: panel.querySelector('.big')?.textContent ?? null, mark: !!panel.querySelector('.unstable-mark') }
  })()`)
  say(`  Rome:  ${rome.big} · marked=${rome.mark}`)
  check(rome.mark === false,
    `R1: Rome reads "${rome.big}" too and is NOT marked — the flag is precision, not magnitude`)

  await page.hashGo(`${BASE}#/explore/housing`, { waitMs: 2500 })
  await showScatter()
  const axis1 = await scatterYAxis()
  const milanPt = await scatterPoint('Milan')
  await page.eval(`(() => {
    const c = ${SCATTER_PANEL}.querySelector('circle[data-city="Milan"]')
    c.dispatchEvent(new PointerEvent('pointerover', { bubbles: true }))
  })()`)
  await sleep(350)
  const readout = await page.eval(`${SCATTER_PANEL}.querySelector('.readout')?.textContent ?? null`)
  await page.eval(`(() => {
    const c = ${SCATTER_PANEL}.querySelector('circle[data-city="Milan"]')
    c.dispatchEvent(new PointerEvent('pointerout', { bubbles: true }))
  })()`)
  await sleep(200)
  const milanReal = Number(readout?.match(/exactly ([\d,]+) yrs/)?.[1].replace(/,/g, ''))
  const domainTop = tickValue(axis1[axis1.length - 1].label)
  say(`  scatter readout: ${readout}`)
  check(milanPt?.offscale === true, 'R1: Milan draws in the off-scale band, not at a real y position')
  check(milanReal > 2000, `R1: Milan's real figure is still kept and shown (${milanReal} yrs — never suppressed)`)
  check(milanReal > domainTop,
    `R1: that figure is excluded from the scatter's own y-domain (top tick ${domainTop} yrs < Milan's ${milanReal})`)

  // The consequence the catalogue names: a STABLE city's exact pixel would
  // move if the unstable extreme were back in the domain computation.
  const sydney = await scatterPoint('Sydney')
  // Package 16 — the tooltip reads "~23 yrs", not "23.4 yrs":
  // docs/DATA-FITNESS.md §2 rules a one-decimal years-to-home unsupportable on
  // inputs rounded to $10/month and $100/m². The `~` is now part of every
  // years-to-home figure, so this pattern accepts it.
  const sydneyReal = Number(sydney.title.match(/:\s*~?([\d.]+)\s*yrs/)[1])
  const sydneyExpected = pixelFor(axis1, sydneyReal)
  // ...and because the DISPLAYED value is now rounded to a whole year, the
  // predicted pixel inherits up to half a year of uncertainty. That is derived
  // here rather than absorbed into a fixed pixel budget that happens to be big
  // enough: the drawing tolerance stays 1.5px and the rounding term is added on
  // top, so this assertion keeps meaning "plotted where its value puts it"
  // instead of quietly becoming "plotted roughly nearby".
  const halfYearPx = Math.abs(pixelFor(axis1, sydneyReal + 0.5) - pixelFor(axis1, sydneyReal))
  const tol = 1.5 + halfYearPx
  say(`  Sydney: ~${sydneyReal} yrs at cy=${sydney.cy.toFixed(2)} `
    + `(axis predicts ${sydneyExpected.toFixed(2)}, tolerance ±${tol.toFixed(2)}px `
    + `= 1.5 drawing + ${halfYearPx.toFixed(2)} from rounding)`)
  // Both halves matter and neither is enough alone: the pixel agreeing with
  // the axis is true whatever the domain is (it is drawn from that same
  // axis), so the domain bound is what makes this a statement about Milan
  // being kept out of it.
  check(domainTop < 200 && Math.abs(sydney.cy - sydneyExpected) < tol,
    `R1: a known-stable city plots where its own real value puts it, on a domain that tops out at ${domainTop} yrs (±${tol.toFixed(2)}px)`)

  /* ==================================================================== */
  say('')
  say('=== R2: tick labels that collide ===')

  /* No production build exposes engine.ts's assertInjectiveTicks by name, so
   * this reaches the real shipped formatters instead: the ExploreCharts chunk
   * re-exports METRICS unmangled, and an import() of an already-loaded chunk
   * URL returns the SAME module instance the app is running. Nothing here is
   * reimplemented — d.format and d.tickFormat are the live functions. */
  const metricsChunk = await page.eval(`(async () => {
    const urls = performance.getEntriesByType('resource').map((r) => r.name).filter((n) => n.endsWith('.js'))
    for (const u of urls) {
      try { const m = await import(u); if (m.METRICS) { window.__METRICS = m.METRICS; return u.split('/').pop() } } catch {}
    }
    return null
  })()`, { awaitPromise: true })
  check(metricsChunk != null, `R2: reached the shipped metric registry from the production bundle (${metricsChunk})`)

  // The exact failing axis from the bug report: years_to_home over a 0-2,500
  // domain, labelled by the CLAMPING display formatter it used to use.
  const collide = await page.eval(`(() => {
    const d = window.__METRICS.find((m) => m.key === 'years_to_home')
    const ticks = [0, 500, 1000, 1500, 2000, 2500]
    return { display: ticks.map((v) => d.format(v)), tick: ticks.map((v) => d.tickFormat(v, 500)) }
  })()`)
  say(`  0-2,500 via display format(): ${JSON.stringify(collide.display)}`)
  say(`  0-2,500 via tickFormat():     ${JSON.stringify(collide.tick)}`)
  check(collide.display.length === 6 && new Set(collide.display).size === 2,
    `R2: the bug report's axis really is non-injective — 6 ticks, ${new Set(collide.display).size} distinct labels`)
  check(collide.display.filter((l) => l === '100+ yrs').length === 5,
    'R2: and "100+ yrs" is the label that repeats, five times over')
  check(new Set(collide.tick).size === 6,
    'R2: the shipped step-aware tickFormat is injective over that same domain (6 distinct labels)')

  // The real, currently-shipped axis.
  const shippedLabels = axis1.map((t) => t.label)
  say(`  shipped years_to_home axis: ${JSON.stringify(shippedLabels)}`)
  check(shippedLabels.length === 7 && new Set(shippedLabels).size === 7,
    `R2: the shipped years_to_home axis renders 7 ticks with 7 distinct labels`)
  check(shippedLabels[0] === '0 yrs' && shippedLabels[6] === '150 yrs',
    'R2: and they run 0 yrs … 150 yrs, not the clamped set')
  check(!shippedLabels.includes('100+ yrs'), 'R2: no clamped "100+ yrs" label survives onto an axis')

  /* The guard itself, exercised rather than assumed: put the pre-fix
   * formatter back on the real shipped metric object, make the real
   * ScatterBuilder re-render, and read what assertInjectiveTicks actually
   * does about it in a production build. */
  const setY = (key) => page.eval(`(() => {
    const sel = [...${SCATTER_PANEL}.querySelectorAll('select')][1]
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(sel, ${JSON.stringify(key)})
    sel.dispatchEvent(new Event('change', { bubbles: true }))
  })()`)
  await page.eval(`(() => {
    const d = window.__METRICS.find((m) => m.key === 'years_to_home')
    window.__realTickFormat = d.tickFormat
    d.tickFormat = (v) => d.format(v)
  })()`)
  await setY('m2_per_year'); await sleep(400)
  await setY('years_to_home'); await sleep(600)
  const guardErrs = await page.eval('window.__errs.slice()')
  const brokenLabels = (await scatterYAxis()).map((t) => t.label)
  say(`  with the pre-fix formatter: ${JSON.stringify(brokenLabels)}`)
  say(`  guard said: ${guardErrs[0] ?? '(nothing)'}`)
  // Counts come out of the guard's own message rather than being pinned to a
  // literal: how many ticks that axis has is R3's business (the domain), and
  // hardcoding them here would make this check fail for R3's reasons instead
  // of its own.
  const counted = guardErrs[0]?.match(/has (\d+) ticks but (\d+) distinct labels/)
  check(guardErrs.length === 1 && counted != null && Number(counted[2]) < Number(counted[1]),
    `R2: assertInjectiveTicks is live on the shipped render path and reports the collision (${counted?.[1]} ticks, ${counted?.[2]} labels)`)
  check(!!guardErrs[0]?.includes('"100+ yrs"'), 'R2: and its message names the repeated label')
  check(new Set(brokenLabels).size < brokenLabels.length,
    'R2: the axis it reported on really did render duplicate labels')

  await page.eval(`(() => {
    window.__METRICS.find((m) => m.key === 'years_to_home').tickFormat = window.__realTickFormat
  })()`)
  await setY('m2_per_year'); await sleep(400)
  await setY('years_to_home'); await sleep(600)
  const restored = (await scatterYAxis()).map((t) => t.label)
  check(JSON.stringify(restored) === JSON.stringify(shippedLabels),
    'R2: restoring the shipped tickFormat restores the seven distinct labels')

  /* ==================================================================== */
  say('')
  say('=== R3: a domain set by an outlier ===')

  const scatter = await page.eval(`(() => {
    const panel = ${SCATTER_PANEL}
    const svg = panel.querySelector('svg')
    const circles = [...svg.querySelectorAll('circle')]
    return {
      selects: [...panel.querySelectorAll('select')].map((s) => s.value),
      plotted: circles.length,
      offscale: circles.filter((c) => c.hasAttribute('data-offscale')).map((c) => c.getAttribute('data-city')).sort(),
      aria: svg.getAttribute('aria-label'),
    }
  })()`)
  const axis3 = await scatterYAxis()
  const yMax = tickValue(axis3[axis3.length - 1].label)
  say(`  preset: ${scatter.selects.join(' x ')} · ${scatter.plotted} points · off-scale: ${scatter.offscale.join(', ')}`)
  check(scatter.selects[0] === 'apt_m2' && scatter.selects[1] === 'years_to_home',
    'R3: the years_to_home x apt_m2 preset is the one under test')
  check(scatter.plotted === 72, `R3: 72 cities have both values and are placed (got ${scatter.plotted})`)
  check(JSON.stringify(scatter.offscale) === JSON.stringify(['Milan', 'Valencia']),
    'R3: exactly Milan and Valencia sit in the overflow band')
  check(scatter.plotted - scatter.offscale.length === 70,
    'R3: 70 of 72 cities plot inside the main field')
  check(yMax < 200, `R3: the y-domain's upper bound is ${yMax}, not the ~2,314 an unguarded Math.max would give`)

  /* ==================================================================== */
  say('')
  say('=== R8: a comparability check never consulted (Netherlands) ===')

  await page.hashGo(`${BASE}#/position?years=8`, { waitMs: 2800 })
  const nl = await rowText('NL')
  const nlTriggers = await rowTriggers('NL')
  const seTriggers = await rowTriggers('SE')
  say(`  NL: ${nl}`)
  check(nlTriggers === 0, `R8: the Netherlands renders NO method-card trigger (got ${nlTriggers})`)
  check(!!nl?.includes('NL has no ISCO-08 correspondence at all for this occupation'),
    'R8: it renders the crosswalk\'s own refusal reason instead')
  check(nl != null && !/P\d/.test(nl), 'R8: and no position percentile at all')
  check(seTriggers === 2,
    `R8: a genuinely comparable country (SE) still renders its Figure and Derived triggers in the same run (${seTriggers})`)

  /* ==================================================================== */
  say('')
  say('=== R9: <Derived>\'s displayed arithmetic reproducible by hand ===')

  // The pre-fix failure was displaying a 3-decimal multiplier beside a result
  // computed from the full-precision premium. Tolerance is the display's own
  // rounding (2 decimals -> half a cent), nothing looser.
  for (const [code, y] of [['SE', 8], ['SE', 20], ['NO', 8]]) {
    await page.hashGo(`${BASE}#/position?years=${y}`, { waitMs: 1800 })
    const card = await openCard(code, 1)
    const m = card?.match(/([\d,]+(?:\.\d+)?) x ([\d.]+) = ([\d,]+(?:\.\d+)?)/)
    if (!m) { check(false, `R9: ${code} @ ${y}y — no "A x B = C" line found in the Derived card`); continue }
    const a = Number(m[1].replace(/,/g, ''))
    const b = Number(m[2])
    const c = Number(m[3].replace(/,/g, ''))
    check(Math.abs(a * b - c) <= 0.005,
      `R9: ${code} @ ${y}y — ${m[1]} x ${m[2]} = ${(a * b).toFixed(2)}, card shows ${m[3]}`)
  }

  /* ==================================================================== */
  say('')
  say('=== R10: "?years=" empty string must not become 0 ===')

  const yearsInput = () => page.eval(`document.querySelector('input[type=number]')?.value ?? null`)
  await page.hashGo(`${BASE}#/position?years=`, { waitMs: 1800 })
  const empty = await yearsInput()
  const href = await page.eval('location.href')
  say(`  ${href} -> years input reads ${JSON.stringify(empty)}`)
  check(href.endsWith('?years='), 'R10: the param really is present-but-empty, not dropped by the router')
  check(empty === '5', `R10: an empty years param falls through to DEFAULT_YEARS (5), got ${JSON.stringify(empty)}`)
  check(empty !== '0' && empty !== '', 'R10: and is neither Number("")\'s 0 nor blank')

  // Controls: a real 0 is still honoured, and a real value still wins — the
  // fix is a null/empty test, not a floor on small numbers.
  await page.hashGo(`${BASE}#/position?years=0`, { waitMs: 1600 })
  check((await yearsInput()) === '0', 'R10: an explicit years=0 is still read as zero experience')
  await page.hashGo(`${BASE}#/position?years=12`, { waitMs: 1600 })
  check((await yearsInput()) === '12', 'R10: an ordinary years=12 is still read as itself')

  /* ==================================================================== */
  say('')
  say('=== R11: Canada\'s two NOC rows ===')

  await page.hashGo(`${BASE}#/position?years=8`, { waitMs: 2000 })
  const ca1 = await rowText('CA-21231')
  const ca2 = await rowText('CA-21232')
  say(`  ${ca1}`)
  say(`  ${ca2}`)
  check(ca1 != null && ca2 != null, 'R11: both CA-21231 and CA-21232 render — not zero, not one')
  check((await rowCount('CA-21231')) === 1 && (await rowCount('CA-21232')) === 1,
    'R11: exactly one row each, not a duplicate standing in for the pair')
  check(pct(ca1) != null && pct(ca2) != null, 'R11: and both rows carry a real position, not a refusal')

  /* ==================================================================== */
  say('')
  say('=== R12: Sweden\'s premium computed against the mean, applied to the median ===')

  await page.hashGo(`${BASE}#/position?years=8`, { waitMs: 2000 })
  const se8 = await rowText('SE')
  say(`  SE @ 8y: ${se8}`)
  check(pct(se8) === 37, `R12: Sweden at 8 years ranks P37 (got P${pct(se8)})`)
  check(pct(se8) !== 31, 'R12: not P31 — the pre-fix answer from shifting the median by a mean-relative premium')
  check(!!se8?.includes('49,673'), 'R12: the estimate reads 49,673 SEK/month (55,500 mean x 0.895)')
  check(se8 != null && !se8.includes('47,883'), 'R12: and not 47,883 (53,500 median x 0.895)')
  const seCard = await openCard('SE', 0)
  check(!!seCard?.includes("publishes each band's own MEAN"),
    'R12: the card states which basis is being shifted, so the two can\'t silently disagree')
  check(!!seCard?.includes('55,500'), 'R12: and the figure it shifts is the mean (55,500), named in the chain')

  /* ==================================================================== */
  say('')
  say('=== R13: Norway\'s youngest age band anchored below any reachable age ===')

  await page.hashGo(`${BASE}#/position?years=2`, { waitMs: 2000 })
  const no2 = await rowText('NO')
  await page.hashGo(`${BASE}#/position?years=8`, { waitMs: 1800 })
  const no8 = await rowText('NO')
  await page.hashGo(`${BASE}#/position?years=30`, { waitMs: 1800 })
  const no30 = await rowText('NO')
  say(`  NO @ 2y : ${no2}`)
  say(`  NO @ 8y : ${no8}`)
  say(`  NO @ 30y: ${no30}`)
  check(no2 != null && no2 === no8,
    'R13: 2 and 8 years read byte-identically — both inside SSB\'s own flat "0-39" band')
  check(no2 !== no30,
    `R13: and 30 years does NOT (P${pct(no2)} vs P${pct(no30)}) — the identity above is a flat band, not a dead feature`)

  await page.hashGo(`${BASE}#/position?years=17`, { waitMs: 1800 })
  const no17 = await openCard('NO', 0)
  const premium = Number(no17?.match(/assumed age ~39[\s\S]*?age ~39 -> ([-+]?[\d.]+)%/)?.[1])
  say(`  NO @ 17y premium: ${premium}%`)
  check(Number.isFinite(premium) && premium < 0,
    `R13: 17 years (assumed age 39, still "under 40") reads a NEGATIVE premium (${premium}%)`)
  check(premium === -8.3,
    'R13: specifically SSB\'s own published -8.31% for that band, not the pre-fix +6.99% interpolation')

  /* ==================================================================== */
  say('')
  say('=== R21: crosswalk comparability checked pairwise, never across the displayed set ===')

  const WAGE_PANEL = `[...document.querySelectorAll('h2')]
    .find((h) => h.textContent.includes('What the same job actually pays')).closest('.panel')`

  /** A wage-panel row's own SVG <text> label, by country code — null if that
   *  country renders no row at all (package 14's own fix: excluded by
   *  chart_comparable, not just absent from the data). */
  const wageRow = (code) => page.eval(`(() => {
    const svg = ${WAGE_PANEL}.querySelector('svg')
    const t = [...svg.querySelectorAll('text')].find((t) => t.textContent.trim().startsWith(${JSON.stringify(code)}))
    return t ? t.textContent.trim() : null
  })()`)

  const wageGapText = () => page.eval(`(() => {
    const h = [...document.querySelectorAll('h3, summary, div')]
      .find((el) => el.textContent.includes("countries don't appear in this chart"))
    return h ? h.closest('.panel, section, div')?.textContent ?? h.textContent : null
  })()`)

  await page.hashGo(`${BASE}#/explore/money`, { waitMs: 2500 })

  // Ireland, Spain, Germany: each below the resolved 4-digit depth (own
  // depth 1, 2, 2 respectively) -- pre-fix, all three rendered a bar right
  // next to Sweden's, each just carrying a small "1-digit match"/"2-digit
  // match" note easy to miss. Post-fix: no row at all.
  for (const code of ['IE', 'ES', 'DE']) {
    check((await wageRow(code)) === null, `R21: ${code} renders NO row in the comparison chart (below the resolved depth)`)
  }

  const gap = await wageGapText()
  say(`  gap text: ${gap?.slice(0, 200)}...`)
  check(!!gap?.includes("IE's own occupation mapping reaches only 1-digit"),
    "R21: Ireland's own specific reason (1-digit, not software-specific) renders on screen")
  check(!!gap?.includes("ES's own occupation mapping reaches only 2-digit"),
    "R21: Spain's own specific reason renders on screen")
  check(!!gap?.includes('NL has no ISCO-08 correspondence'),
    'R21: the Netherlands (zero correspondence, the pre-existing case) still renders its own reason too')

  // A country that DOES meet the resolved depth still renders — the fix
  // excludes by name, it does not empty the chart.
  const se = await wageRow('SE')
  say(`  SE row: ${se}`)
  check(se !== null, 'R21: a genuinely comparable country (SE) still renders a row')
  check(/'\d\d/.test(se ?? ''), `R21: and its own reference year renders on the row itself, not only in a collapsed card (${se})`)

  const resolvedDepthText = await page.eval(`${WAGE_PANEL}.textContent`)
  check(resolvedDepthText.includes('currently') && resolvedDepthText.includes('4-digit') && resolvedDepthText.includes('isco08:2512'),
    'R21: the resolved depth and shared key render as visible prose above the chart, not just in a tooltip')

  /* ==================================================================== */
  say('')
  say('=== R22: the merged /work and the new /openings (package 17) ===')

  // Until package 17's adversarial review this suite never loaded either of
  // these routes -- it navigated to /position and relied on the redirect. That
  // is why all fifteen coverage-matrix links shipped pointing at the 404 page,
  // and why a fabricated pay figure for an unsupported occupation shipped
  // beside a panel saying no data resolved for it.

  await page.hashGo(`${BASE}#/work`, { waitMs: 3000 })

  // Package 24 — the coverage-matrix-plus-separate-per-country-sections
  // structure this block used to check is gone by design: CountryStripRow
  // shows a country's full answer in ONE row, so there is no summary row
  // to click and no separate detail section to scroll to (the scroll-to-
  // fragment mechanism, its bare-fragment-anchor bug, and the "#c-DK deep
  // link" checks that used to guard it are removed below, not silently
  // left to bit-rot against a mechanism that no longer exists). What
  // still needs guarding — every country renders, Canada's two NOC codes
  // each get their own row, no internal sentinel leaks to visible text —
  // is checked against the new `data-key` a row carries instead.
  const keys = JSON.parse(await page.eval(
    `JSON.stringify([...document.querySelectorAll('.wrow[data-key]')].map((r) => r.dataset.key))`))
  check(keys.length >= 15, `R22: /work renders every country's own row (${keys.length})`)
  check(new Set(keys).size === keys.length,
    `R22: every row's data-key is unique — Canada's two NOC rows would collide on data-cc="CA" alone `
    + `(${keys.length - new Set(keys).size} duplicate(s))`)
  check(keys.includes('CA-21231') && keys.includes('CA-21232'),
    'R22: both Canadian NOC codes get their own row, keyed by the real code')
  const rowsText = await page.eval(`document.querySelector('.panel')?.textContent ?? ''`)
  check(!/-first/.test(rowsText), 'R22: no internal "-first" render sentinel reaches visible text')
  check(keys.indexOf('CA-21231') < keys.indexOf('CA-21232'),
    'R22: and Canada\'s own two rows keep a stable order (CA-21231 before CA-21232)')

  // Every publishable country accounts for its own median, not just the first.
  //
  // The expected count is DERIVED from the payload, not written down. It was
  // `>= 5`, which was true of the corpus the test was written against and false
  // the first time the weekly refresh actually ran: DE and FR came back with 29
  // software rows each, one short of the 30-row floor, so three countries
  // publish rather than five. That is the floor working, and a test that reads
  // it as a regression is pinned to a snapshot — the same defect as a label
  // keyed to array position. Package 18.
  await page.hashGo(`${BASE}#/work`, { waitMs: 2600 })
  // Read the payload the built site serves, in Node — page.eval() does not
  // await, so an async fetch inside it returns a Promise, not JSON.
  const payload = JSON.parse(readFileSync(
    new URL('../../site/dist/data/history/openings.json', import.meta.url), 'utf8'))
  const publishable = payload.data.pay_summary_by_country.filter((x) => x.publishable)
  const compData = {
    publishable: publishable.map((x) => x.country),
    withComposition: publishable.filter((x) => x.composition).map((x) => x.country),
    rendered: JSON.parse(await page.eval(
      `JSON.stringify([...document.querySelectorAll('p.sub')].map((p) => p.textContent.trim())`
      + `.filter((t) => t.startsWith('What the ')).map((t) => t.slice(9, 11)))`)),
  }
  check(compData.publishable.length > 0,
    `R22: the payload publishes at least one country (${compData.publishable.join(',') || 'none'})`)
  check(JSON.stringify(compData.rendered) === JSON.stringify(compData.withComposition),
    `R22: every publishable country renders its own composition paragraph — `
    + `payload ${compData.withComposition.join(',')} vs rendered ${compData.rendered.join(',')}`)
  const compText = JSON.parse(await page.eval(
    `JSON.stringify([...document.querySelectorAll('p.sub')].map((p) => p.textContent.trim())`
    + `.filter((t) => t.startsWith('What the ')))`))
  check(!compText.some((t) => !t.startsWith('What the US') && /USAJOBS supplies \d+ US /.test(t)),
    'R22: and no country carries the US federal-listings sentence as if it were its own')

  // A fabricated figure for an occupation the site has just said it cannot answer.
  await page.hashGo(`${BASE}#/work?occupation=isco08%3A2511&years=8`, { waitMs: 2600 })
  const unsupported = await page.eval('document.body.innerText')
  check(/No wage data resolved for this occupation yet/.test(unsupported),
    'R22: an unsupported occupation says so')
  check(!/Your estimate/.test(unsupported),
    'R22: and renders NO "Your estimate" — computeEstimate never reads profile.occupation, so this gate is the only thing stopping a software-developer figure being labelled as another job')
  check(!/Pay against cost/.test(unsupported),
    'R22: and no pay-against-cost panel built on that estimate')

  // /openings: the USD -> display leg is year-matched like the first leg.
  await page.hashGo(`${BASE}#/openings`, { waitMs: 6000 })
  const fx = JSON.parse(await page.eval(`(async () => {
    const setV = (el, v, proto) => { Object.getOwnPropertyDescriptor(proto.prototype, 'value').set.call(el, v); el.dispatchEvent(new Event(proto === HTMLSelectElement ? 'change' : 'input', { bubbles: true })) }
    const findEls = () => ({
      search: document.querySelector('input[type="text"], input:not([type])'),
      cur: [...document.querySelectorAll('select')].find((s) => [...s.options].some((o) => /Australian dollars/.test(o.textContent))),
    })
    // Found live: this page's own ~48k-row dataset can still be rendering
    // its filter controls at the fixed 6000ms mark above under real-world
    // load, at which point search/cur are null and the native value
    // setter below throws the opaque "Illegal invocation" (calling it with
    // a null receiver) rather than a message that says what's actually
    // wrong. Poll a further 6s for both controls to exist before touching
    // them; a genuine regression still fails, just with a legible reason.
    let els = findEls()
    for (let i = 0; i < 24 && (!els.search || !els.cur); i++) {
      await new Promise((r) => setTimeout(r, 250))
      els = findEls()
    }
    if (!els.search || !els.cur) {
      return JSON.stringify({ ok: false,
        reason: 'search=' + !!els.search + ' cur=' + !!els.cur + ' never both appeared' })
    }
    setV(els.search, 'supervisory', HTMLInputElement)
    setV(els.cur, 'AUD', HTMLSelectElement)
    return JSON.stringify({ ok: true })
  })()`, { awaitPromise: true }))
  check(fx.ok, `R22: /openings accepts a title filter and a display currency${fx.reason ? ` (${fx.reason})` : ''}`)

  const oldRow = JSON.parse(await page.eval(`(() => {
    const tr = [...document.querySelectorAll('.tbl tbody tr')].find((r) => /Census Bureau/.test(r.textContent))
    if (!tr) return JSON.stringify({ found: false })
    const btn = tr.querySelector('button')
    btn.click()
    return JSON.stringify({ found: true, pay: btn.textContent.trim(),
      marked: !!tr.querySelector('.fx-estimate') })
  })()`))
  check(oldRow.found, 'R22: the 2016 US federal listing is reachable in /openings')
  // The method card mounts on click; read it on the NEXT round-trip, not in
  // the same evaluation that opened it.
  await sleep(700)
  oldRow.year = await page.eval(
    `(document.body.innerText.match(/USD → AUD at the (\\d{4}) rate/) || [])[1] || null`)
  check(oldRow.year === '2016',
    `R22: a 2016 posting shown in AUD converts at the 2016 cross-rate, not the series' latest (got ${oldRow.year}) — the latest-rate version put it 15.4% high`)
  check(oldRow.marked === false,
    'R22: and carries NO estimate marker, because 2016 is its own year — the marker means "reached", not "converted"')

  // Clear the title filter first. With "supervisory" still applied every
  // visible row is a 2016-2017 USAJOBS listing, which converts at its OWN
  // year exactly and is therefore correctly unmarked — a zero here would mean
  // the filter, not the marker.
  await page.eval(`(() => {
    const setV = (el, v, proto) => { Object.getOwnPropertyDescriptor(proto.prototype, 'value').set.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })) }
    const search = document.querySelector('input[type="text"], input:not([type])')
    setV(search, '', HTMLInputElement)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  })()`)
  await sleep(900)
  const recent = JSON.parse(await page.eval(`(() => {
    const rows = [...document.querySelectorAll('.tbl tbody tr')]
    const marked = rows.filter((r) => r.querySelector('.fx-estimate'))
    return JSON.stringify({ n: rows.length, marked: marked.length,
      title: marked[0] && marked[0].querySelector('.fx-estimate').getAttribute('title') })
  })()`))
  check(recent.marked > 0,
    `R22: postings whose own year has no published rate DO carry the marker (${recent.marked}/${recent.n})`)
  check(/USD→AUD at the \d{4} rate/.test(recent.title ?? ''),
    `R22: and the marker names the cross-rate leg, which used to state no year at all (${recent.title})`)

  /* ==================================================================== */
  say('')
  const stray = (await page.eval('window.__errs.slice()')).filter((e) => !e.includes('distinct labels'))
  check(stray.length === 0, `no console errors beyond R2's deliberately provoked one (${stray.length})`)
  stray.forEach((e) => say(`    ${e}`))

  page.close()
} finally {
  close()
}

say('')
say('-'.repeat(70))
say(fails === 0 ? 'ALL UI REGRESSION CHECKS PASS (R1, R2, R3, R8, R9, R10, R11, R12, R13, R21, R22)' : `${fails} check(s) FAILED`)
process.exitCode = fails ? 1 : 0
