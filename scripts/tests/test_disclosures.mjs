/* D1 — no open disclosure hides part of its own content.
 *
 * Package 46, Tier 1. The CV panel on /work opened to `max-height: 600px`
 * over content that wraps to 720px at 390, so the bottom 120px — including
 * the note that tells a reader the form has no submit button — was cut off
 * with no scroll and no sign anything was missing. Package 45 had just put
 * a storage consent inside that same capped box.
 *
 * Built first and run against the unfixed code, which it must fail. Its
 * first draft PASSED there, for two reasons worth keeping in view:
 *
 *   · It clicked and read `aria-expanded` in one synchronous evaluation.
 *     React had not flushed, so the CV panel — the disclosure this check
 *     exists because of — was recorded as "stayed closed" and skipped.
 *   · Its witness asked only that SOMETHING on /work was opened, and the
 *     <details> panels satisfied it while the CV panel went unmeasured.
 *
 * Once it could see, it found a second clip the work order had not listed:
 * at desktop widths every source card in /work's estimate column opened to
 * nothing, cut to 0px by the cell's own `overflow: hidden`.
 *
 * WHAT IT ASKS. For every disclosure it can FIND BY STRUCTURE — a control
 * carrying `aria-expanded` + `aria-controls`, or a `<details>` — it opens it
 * the way a reader would and asks of the region that opened:
 *
 *   1. does the content fit the region's own box, unless the box scrolls?
 *   2. does anything INSIDE the region cut its content off vertically?
 *   3. do points inside the content actually land on the region when
 *      hit-tested — i.e. is what is there on screen?
 *
 * (3) is the one that cannot be fooled by CSS reasoning: it does not model
 * overflow, containing blocks or z-index, it asks the browser what is
 * painted. It is also why the source-card fix can be checked at all — a
 * `position: fixed` card still has the clipping cell as a DOM ancestor, so
 * any check that walks ancestors would report a clip that no longer exists.
 * Points covered by the site's own sticky or fixed chrome are skipped, not
 * failed; the region is scrolled clear of it first.
 *
 * It sweeps the CLASS, not a list: nothing here names a component. Popover
 * cards are sampled one per distinct clipping context, because the question
 * about them is where they live, and a thousand cards in one cell type are
 * one answer.
 *
 *   node scripts/tests/test_disclosures.mjs            (needs the preview on :4173)
 *   D1_ONLY=work node scripts/tests/test_disclosures.mjs
 */
import { launch, openPage } from './cdp.mjs'

const BASE = process.env.BASE ?? 'http://localhost:4173/'
const ONLY = new Set((process.env.D1_ONLY ?? '').split(',').map((s) => s.trim()).filter(Boolean))

let fails = 0
const say = (s = '') => console.log(s)
const check = (ok, label) => { say(`${ok ? 'PASS' : 'FAIL'}  ${label}`); if (!ok) fails++ }

const ROUTES = [
  ['home', '#/'],
  ['work', '#/work'],
  ['openings', '#/openings'],
  ['compare', '#/compare'],
  ['data', '#/data'],
  ['postings-seed', '#/postings-seed'],
  ['city', '#/city/berlin'],
  ['country', '#/country/de'],
  /* All seven themes, not a sample: the held-transform trap lived in the
   * rule every theme's panels share, and a sample of three would have found
   * it — and said nothing about the four it did not load. */
  ['explore-money', '#/explore/money'],
  ['explore-visa', '#/explore/visa'],
  ['explore-jobs', '#/explore/jobs'],
  ['explore-housing', '#/explore/housing'],
  ['explore-people', '#/explore/people'],
  ['explore-life', '#/explore/life'],
  ['explore-climate', '#/explore/climate'],
]
const WIDTHS = [[390, 844, true], [1024, 768, false], [1440, 900, false]]

/* Page-side: discover by structure.
 *
 *   inline   an aria disclosure whose region is in the DOM while closed and
 *            revealed in place (the CV panel). Every one is opened.
 *   popover  an aria disclosure whose region renders only when opened
 *            (<Figure>, <Derived>). One per distinct CLIPPING CONTEXT — the
 *            nearest ancestor that hides overflow, or none — so each kind of
 *            container a card can open inside is exercised at least once.
 *   details  every <details>.
 */
/* `which` is 'containers' (every <details> and in-place disclosure) or
 * 'popovers' (cards, sampled). The two are discovered in separate passes:
 * containers are opened and LEFT OPEN, and only then are popovers looked
 * for, so a card that lives inside a <details> is reachable when sampled.
 *
 * Reachability is the browser's own answer — `checkVisibility()` — not "has a
 * size". Chrome lays out the content of a CLOSED <details> on request, so a
 * trigger in one reports a 103x20 box while no reader can click it; an
 * earlier draft discovered such a trigger, opened a card nobody could reach,
 * and reported it as clipped. */
const DISCOVER = (which) => `(() => {
  const out = []
  let n = document.querySelectorAll('[data-d1]').length
  const tag = (el) => { if (!el.dataset.d1) el.dataset.d1 = 'd' + (n++); return el.dataset.d1 }
  const reachable = (el) => {
    if (el.closest('[inert]')) return false
    if (typeof el.checkVisibility === 'function'
        && !el.checkVisibility({ contentVisibilityAuto: true, visibilityProperty: true })) return false
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0
  }
  const clipContext = (el) => {
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const cs = getComputedStyle(a)
      if (/hidden|clip/.test(cs.overflowX + ' ' + cs.overflowY)) {
        return a.tagName.toLowerCase() + '.' + String(a.className || '').trim().split(/\\s+/).join('.')
      }
    }
    return 'none'
  }
  /* The nearest ancestor a \`position: fixed\` card would be placed and
   * stacked against instead of the viewport: anything with a transform,
   * filter, perspective, backdrop-filter, paint/layout containment, a
   * will-change that promises one, or a size container. Package 46: /work's
   * percentile cards sat in a span centred with translateX(-50%) — painted
   * under the next rows at 1024, centred on the span, 140px off screen, at
   * 390 — and sampling by clip context alone never opened one. */
  const cbContext = (el) => {
    for (let a = el.parentElement; a && a !== document.documentElement; a = a.parentElement) {
      const cs = getComputedStyle(a)
      if (cs.transform !== 'none' || cs.filter !== 'none' || cs.perspective !== 'none'
          || (cs.backdropFilter && cs.backdropFilter !== 'none') || /paint|layout|strict|content/.test(cs.contain)
          || /transform|filter|perspective/.test(cs.willChange) || (cs.containerType && cs.containerType !== 'normal')) {
        return a.tagName.toLowerCase() + '.' + String(a.getAttribute('class') || '').trim().split(/\\s+/).join('.')
          + ' [' + (cs.transform !== 'none' ? 'transform' : cs.filter !== 'none' ? 'filter' : 'containing block') + ']'
      }
    }
    return 'viewport'
  }
  const seenCtx = new Set()
  for (const c of document.querySelectorAll('[aria-expanded][aria-controls]')) {
    if (!reachable(c)) continue
    const inline = !!document.getElementById(c.getAttribute('aria-controls'))
    if (${JSON.stringify(which)} === 'trapped') {
      /* Every card trigger, not a sample: which ones live inside such a box. */
      const cb = inline ? 'viewport' : cbContext(c)
      if (cb !== 'viewport') out.push({ id: tag(c), cb,
        label: (c.getAttribute('aria-label') || c.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 48) })
      continue
    }
    if ((${JSON.stringify(which)} === 'containers') !== inline) continue
    let ctx = ''
    if (!inline) {
      ctx = clipContext(c) + ' / ' + cbContext(c)
      if (seenCtx.has(ctx)) continue
      seenCtx.add(ctx)
    }
    out.push({ id: tag(c), type: 'aria', kind: inline ? 'inline' : 'popover', ctx,
      label: (c.getAttribute('aria-label') || c.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 48) })
  }
  if (${JSON.stringify(which)} === 'containers') {
    for (const d of document.querySelectorAll('details')) {
      const s = d.querySelector(':scope > summary')
      if (!s || !reachable(s)) continue
      out.push({ id: tag(d), type: 'details', kind: 'details', ctx: '',
        label: (s.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 48) })
    }
  }
  return JSON.stringify(out)
})()`

/* Scroll a control into the middle of the viewport before opening it, so a
 * card that opens beneath it has somewhere to be seen. */
const CENTER = (id) => `(() => {
  const el = document.querySelector('[data-d1="${id}"]')
  if (el) el.scrollIntoView({ block: 'center' })
  return 1
})()`

/* Click; wait for the state to be true; then resolve the region. Three
 * separate evaluations, because React does not flush a click inside the
 * evaluation that dispatched it. */
const CLICK = (id, type) => `(() => {
  const el = document.querySelector('[data-d1="${id}"]')
  if (!el) return 0
  if (${JSON.stringify(type)} === 'details') { if (!el.open) el.querySelector(':scope > summary').click() }
  else if (el.getAttribute('aria-expanded') !== 'true') el.click()
  return 1
})()`
const IS_OPEN = (id, type) => type === 'details'
  ? `document.querySelector('[data-d1="${id}"]')?.open === true`
  : `(() => { const el = document.querySelector('[data-d1="${id}"]'); if (!el) return false;
       const rg = document.getElementById(el.getAttribute('aria-controls'));
       return el.getAttribute('aria-expanded') === 'true' && !!rg && !rg.closest('[inert]') })()`
const REGION = (id, type) => `(() => {
  const el = document.querySelector('[data-d1="${id}"]')
  if (!el) return ''
  if (${JSON.stringify(type)} === 'details') return '${id}'
  const rg = document.getElementById(el.getAttribute('aria-controls'))
  if (!rg) return ''
  if (!rg.dataset.d1) rg.dataset.d1 = '${id}-region'
  return rg.dataset.d1
})()`

/* An in-place region is scrolled so its top sits clear of sticky chrome; a
 * popover is left where it opened (moving the page would move its trigger
 * and prove nothing). */
const REGION_TOP = (rid) => `(() => {
  const r = document.querySelector('[data-d1="${rid}"]')
  if (!r) return 1
  window.scrollBy(0, r.getBoundingClientRect().top - 140)
  return 1
})()`

/* The measurement of whatever part of the region is in the viewport now.
 * `popover`: a card is `position: fixed` — no scroll brings an off-screen
 * part of it back — so its points past the viewport's side edges count as
 * missed, not skipped (package 46: /work's percentile card at 390 ran from
 * x = -140 to 218, and every point left of 0 was being skipped). */
const MEASURE = (rid, popover = false) => `(() => {
  const r = document.querySelector('[data-d1="${rid}"]')
  if (!r) return JSON.stringify({ gone: true })
  const cs = getComputedStyle(r)
  if (cs.display === 'contents') {
    return JSON.stringify({ scrolls: false, own: 0, innerClip: 0, innerBy: null, tested: 0, missed: 0, chrome: 0,
      firstMiss: null, top: 0, extent: 0, vh: window.innerHeight, scrollHeight: 0, clientHeight: 0,
      maxHeight: 'none', inlineRegion: true })
  }
  /* An INLINE region (51 of them on /data) has no box of its own to cap, but
   * it can still be covered or cut by something around it. Its bounding box
   * spans whole lines it does not occupy, so hit-test the centre of each of
   * its own line boxes instead. An earlier draft skipped inline regions
   * entirely, and reported /data's 51 as opened with 0 points tested. */
  if (cs.display === 'inline') {
    let tested = 0, missed = 0, chrome = 0, firstMiss = null
    const vh0 = window.innerHeight, vw0 = window.innerWidth

    /* A point outside the visible area of a scrolling ancestor is REACHABLE —
     * the reader scrolls that box — so it is skipped, not failed. /data's
     * source table sits in an overflow-x:auto wrapper; at 390 half of its
     * text is to the right of the wrapper's edge, and an earlier draft
     * reported those glyphs as clipped. Only boxes that actually scroll count:
     * overflow auto/scroll AND content larger than the box on that axis. */
    let sL = -Infinity, sT = -Infinity, sR = Infinity, sB = Infinity
    for (let a = r.parentElement; a && a !== document.documentElement; a = a.parentElement) {
      const as = getComputedStyle(a)
      const sx = /auto|scroll/.test(as.overflowX) && a.scrollWidth > a.clientWidth + 1
      const sy = /auto|scroll/.test(as.overflowY) && a.scrollHeight > a.clientHeight + 1
      if (!sx && !sy) continue
      const q = a.getBoundingClientRect()
      if (sx) { sL = Math.max(sL, q.left); sR = Math.min(sR, q.right) }
      if (sy) { sT = Math.max(sT, q.top); sB = Math.min(sB, q.bottom) }
    }
    const inScrollView = (x, y) => x >= sL && x <= sR && y >= sT && y <= sB
    /* Hit-test the GLYPHS, not the element's line boxes: a line box can be a
     * whitespace fragment whose centre lands on the page behind it, which is
     * how an earlier draft reported a clip in /data's "+3 more steps". */
    const rects = []
    const walker = document.createTreeWalker(r, NodeFilter.SHOW_TEXT)
    for (let tn = walker.nextNode(); tn; tn = walker.nextNode()) {
      if (!tn.textContent.trim()) continue
      const rg = document.createRange()
      rg.selectNodeContents(tn)
      for (const q of rg.getClientRects()) rects.push(q)
    }
    for (const lr of rects) {
      const x = lr.left + lr.width / 2, y = lr.top + lr.height / 2
      if (lr.width < 2 || lr.height < 2 || y < 1 || y >= vh0 - 1 || x < 1 || x >= vw0 - 1) continue
      if (!inScrollView(x, y)) continue
      const hit = document.elementFromPoint(x, y)
      if (!hit) continue
      if (hit === r || r.contains(hit)) { tested++; continue }
      let a = hit, isChrome = false
      while (a && a !== document.body) {
        const p = getComputedStyle(a).position
        if ((p === 'sticky' || p === 'fixed') && !a.contains(r) && !r.contains(a)) { isChrome = true; break }
        a = a.parentElement
      }
      if (isChrome) { chrome++; continue }
      tested++; missed++
      if (!firstMiss) firstMiss = { y: Math.round(y), hit: hit.tagName.toLowerCase() + '.' + String(hit.getAttribute('class') || '').split(' ')[0] }
    }
    return JSON.stringify({ scrolls: false, own: 0, innerClip: 0, innerBy: null, tested, missed, chrome, firstMiss,
      top: 0, extent: 0, vh: vh0, scrollHeight: 0, clientHeight: 0, maxHeight: 'none', inlineRegion: true })
  }
  const scrolls = /auto|scroll/.test(cs.overflowY)
  const box = r.getBoundingClientRect()

  // 2 · anything inside the region cutting its content off vertically.
  // Screen-reader-only text is clipped to a pixel on purpose; skip it.
  let innerClip = 0, innerBy = null
  for (const d of r.querySelectorAll('*')) {
    const dc = getComputedStyle(d)
    if (!/hidden|clip/.test(dc.overflowY)) continue
    const db = d.getBoundingClientRect()
    if (db.width <= 2 || db.height <= 2) continue
    if (dc.clip && dc.clip !== 'auto') continue
    const over = d.scrollHeight - d.clientHeight
    if (over > innerClip) { innerClip = over; innerBy = d.tagName.toLowerCase() + '.' + String(d.getAttribute('class') || '').split(' ')[0] }
  }

  // 3 · hit-test. The extent tested is the CONTENT, not the box: a region
  // capped by max-height has content below its own bottom edge, and that
  // is exactly where a clip hides things.
  const vh = window.innerHeight, vw = window.innerWidth
  const extent = scrolls ? box.height : Math.max(box.height, r.scrollHeight)
  const yTop = Math.max(box.top, 0), yBottom = Math.min(box.top + extent, vh)
  const inset = Math.min(24, box.width / 2)
  const xs = [box.left + inset, box.right - inset]

  /* A point outside the visible area of a scrolling ancestor is REACHABLE —
   * the reader scrolls that box — so it is skipped, not failed. /data's
   * source table sits in an overflow-x:auto wrapper; at 390 half of its
   * text is to the right of the wrapper's edge, and an earlier draft
   * reported those glyphs as clipped. Only boxes that actually scroll count:
   * overflow auto/scroll AND content larger than the box on that axis. */
  let sL = -Infinity, sT = -Infinity, sR = Infinity, sB = Infinity
  for (let a = r.parentElement; a && a !== document.documentElement; a = a.parentElement) {
    const as = getComputedStyle(a)
    const sx = /auto|scroll/.test(as.overflowX) && a.scrollWidth > a.clientWidth + 1
    const sy = /auto|scroll/.test(as.overflowY) && a.scrollHeight > a.clientHeight + 1
    if (!sx && !sy) continue
    const q = a.getBoundingClientRect()
    if (sx) { sL = Math.max(sL, q.left); sR = Math.min(sR, q.right) }
    if (sy) { sT = Math.max(sT, q.top); sB = Math.min(sB, q.bottom) }
  }
  const inScrollView = (x, y) => x >= sL && x <= sR && y >= sT && y <= sB
  let tested = 0, missed = 0, chrome = 0, firstMiss = null
  for (let y = yTop + 6; y < yBottom - 4; y += 24) {
    for (const x of xs) {
      if (x < 1 || x >= vw - 1) {
        if (${popover}) { tested++; missed++; if (!firstMiss) firstMiss = { y: Math.round(y - box.top), hit: 'off screen at x=' + Math.round(x) } }
        continue
      }
      if (!inScrollView(x, y)) continue
      const hit = document.elementFromPoint(x, y)
      if (!hit) continue
      if (hit === r || r.contains(hit)) { tested++; continue }
      let a = hit, isChrome = false
      while (a && a !== document.body) {
        const p = getComputedStyle(a).position
        if ((p === 'sticky' || p === 'fixed') && !a.contains(r) && !r.contains(a)) { isChrome = true; break }
        a = a.parentElement
      }
      if (isChrome) { chrome++; continue }
      tested++; missed++
      if (!firstMiss) firstMiss = { y: Math.round(y - box.top), hit: hit.tagName.toLowerCase() + '.' + String(hit.getAttribute('class') || '').split(' ')[0] }
    }
  }
  return JSON.stringify({
    scrolls, own: Math.round(r.scrollHeight - r.clientHeight), innerClip: Math.round(innerClip), innerBy,
    tested, missed, chrome, firstMiss,
    top: box.top, extent, vh,
    scrollHeight: Math.round(r.scrollHeight), clientHeight: Math.round(r.clientHeight), maxHeight: cs.maxHeight,
  })
})()`

const CLOSE = (id, type) => `(() => {
  const el = document.querySelector('[data-d1="${id}"]')
  if (!el) return 1
  if (${JSON.stringify(type)} === 'details') { if (el.open) el.querySelector(':scope > summary').click() }
  else if (el.getAttribute('aria-expanded') === 'true') el.click()
  return 1
})()`

const { port, close } = await launch({ port: 9831 })
let page
const findings = []
const trapped = []
let opened = 0, measured = 0, scrollers = 0, pointsTested = 0
const perRoute = new Map()
try {
  page = await openPage(port)
  await page.emulateReducedMotion(true)

  for (const [w, h, mobile] of WIDTHS) {
    await page.viewport(w, h, mobile)
    for (const [name, route] of ROUTES) {
      if (ONLY.size && !ONLY.has(name)) continue
      /* A real load per route, then the hash — never hash-to-hash. goto()
       * waits for a load event, and moving between two hash routes of one
       * document never fires one. */
      await page.goto('about:blank')
      await page.goto(BASE)
      await page.hashGo(BASE + route)
      await page.waitForReady({ quietMs: 400, timeoutMs: 60000, label: `${name} @${w}` })

      /* Step down the page so anything behind DeferUntilVisible mounts; a
       * disclosure that never mounted cannot be found, and a check that
       * finds nothing passes. */
      const H = await page.eval('document.body.scrollHeight')
      for (let y = 0; y < H; y += Math.round(h * 0.8)) {
        await page.eval(`(() => { window.scrollTo(0, ${y}); return 1 })()`)
        await page.waitForReady({ quietMs: 150, timeoutMs: 30000, label: 'scroll' })
      }

      const key = `${name}@${w}`
      const tally = { found: 0, opened: 0, inline: 0, points: 0 }
      perRoute.set(key, tally)

      /* Open one disclosure, measure it, and optionally close it again. */
      const exercise = async (d, closeAfter) => {
        await page.eval(CENTER(d.id))
        await page.waitForReady({ quietMs: 150, timeoutMs: 30000, label: 'center' })
        if (!await page.eval(CLICK(d.id, d.type))) return
        try {
          await page.waitFor(IS_OPEN(d.id, d.type), { timeoutMs: 5000, label: `open ${d.label}` })
        } catch {
          findings.push({ key, label: d.label, kind: d.kind, wouldNotOpen: true })
          return
        }
        await page.waitForReady({ quietMs: 250, timeoutMs: 30000, label: `open ${d.label}` })
        const rid = await page.eval(REGION(d.id, d.type))
        opened++; tally.opened++
        if (d.kind === 'inline') tally.inline++

        if (d.kind !== 'popover') {
          await page.eval(REGION_TOP(rid))
          await page.waitForReady({ quietMs: 150, timeoutMs: 30000, label: 'region top' })
        }
        /* Step through a region taller than the viewport, measuring each
         * view, so the bottom of a tall panel is tested rather than assumed. */
        let agg = null
        for (let step = 0; step < 10; step++) {
          const m = JSON.parse(await page.eval(MEASURE(rid, d.kind === 'popover')))
          if (m.gone) { agg = m; break }
          if (!agg) agg = { ...m }
          else {
            agg.tested += m.tested; agg.missed += m.missed; agg.chrome += m.chrome
            agg.firstMiss = agg.firstMiss ?? m.firstMiss
            agg.innerClip = Math.max(agg.innerClip, m.innerClip); agg.innerBy = agg.innerBy ?? m.innerBy
          }
          if (d.kind === 'popover' || m.inlineRegion || m.top + m.extent <= m.vh - 4) break
          await page.eval(`(() => { window.scrollBy(0, ${Math.round(h * 0.5)}); return 1 })()`)
          await page.waitForReady({ quietMs: 150, timeoutMs: 30000, label: 'region step' })
        }
        if (agg && !agg.gone) {
          measured++; pointsTested += agg.tested; tally.points += agg.tested
          if (agg.scrolls) scrollers++
          const ownOver = agg.scrolls ? 0 : agg.own
          /* Did opening it make the PAGE wider than the screen? A table that
           * opened at 320 made /work 486px wide, and every point of it that
           * lay past the edge was skipped as "reachable by scrolling" — by
           * scrolling the whole page sideways, which is the defect (package
           * 46, adversarial review). In the 390 run's mobile emulation an
           * overflowing page widens the layout viewport, so innerWidth shows
           * it; on the desktop runs scrollWidth does. */
          const pageW = await page.eval(`Math.max(innerWidth, document.documentElement.scrollWidth)`)
          const widens = pageW > w + 1 ? pageW : 0
          if (ownOver > 1 || agg.innerClip > 1 || agg.missed > 0 || widens) {
            findings.push({ key, label: d.label, kind: d.kind, ctx: d.ctx, ...agg, ownOver, widens })
          }
        }
        if (closeAfter) {
          await page.eval(CLOSE(d.id, d.type))
          await page.waitForReady({ quietMs: 150, timeoutMs: 30000, label: 'close' })
        }
      }

      /* Phase 1 — containers: every <details> and in-place disclosure,
       * opened and LEFT OPEN, repeating so a disclosure nested inside one
       * that just opened is found on the next pass. */
      const done = new Set()
      for (let pass = 0; pass < 4; pass++) {
        const fresh = JSON.parse(await page.eval(DISCOVER('containers'))).filter((d) => !done.has(d.id))
        if (!fresh.length) break
        tally.found += fresh.length
        for (const d of fresh) { done.add(d.id); await exercise(d, false) }
      }
      /* Phase 2 — cards, sampled one per clipping context AND containing
       * block, now that every container they could live in is open. Each is
       * closed again after: one open card at a time is how a reader meets
       * them. Then, structurally and for EVERY card trigger rather than a
       * sample: none may sit inside a box that a fixed card would be placed
       * and stacked against instead of the viewport. */
      const cards = JSON.parse(await page.eval(DISCOVER('popovers')))
      tally.found += cards.length
      for (const d of cards) await exercise(d, true)
      for (const t of JSON.parse(await page.eval(DISCOVER('trapped')))) trapped.push({ key, ...t })
    }
  }
} finally {
  try { page?.close() } catch { /* already closed */ }
  close()
}

say('')
say('=== D1: no open disclosure hides part of its own content ===')
for (const [k, v] of perRoute) {
  say(`  ${k.padEnd(22)} found ${String(v.found).padStart(3)}  opened ${String(v.opened).padStart(3)}  (inline ${v.inline})  points ${v.points}`)
}
say('')
check(opened > 0 && pointsTested > 0,
  `D1: the sweep really opened and hit-tested disclosures (${opened} opened, ${measured} measured, ${pointsTested} points, ${scrollers} scroll containers)`)
/* The witness names the CLASS the defect lives in — an in-place disclosure
 * whose region exists while closed — and requires it to have been reached
 * and hit-tested at every width. "Something on /work opened" is the witness
 * that passed on broken code. */
const workKeys = [...perRoute.keys()].filter((k) => k.startsWith('work@'))
/* Said as SKIP, not PASS, when D1_ONLY leaves /work out: it used to print
 * "PASS … ()" — a witness reported as seen that nobody looked for. */
if (ONLY.size > 0 && !ONLY.has('work')) say('SKIP  D1: the /work witness — /work is not in D1_ONLY')
else check(workKeys.length === WIDTHS.length && workKeys.every((k) => perRoute.get(k).inline > 0 && perRoute.get(k).points > 0),
  `D1: on /work, at every width, an in-place disclosure was opened and hit-tested `
  + `(${workKeys.map((k) => `${k} ${perRoute.get(k).inline}`).join(', ')})`)
for (const f of findings) {
  if (f.wouldNotOpen) { say(`  WOULD NOT OPEN  ${f.key.padEnd(22)} ${f.kind.padEnd(8)} "${f.label}"`); continue }
  const why = []
  if (f.ownOver > 1) why.push(`${f.ownOver}px over its own box (max-height ${f.maxHeight})`)
  if (f.innerClip > 1) why.push(`${f.innerClip}px cut inside by ${f.innerBy}`)
  if (f.missed > 0) why.push(`${f.missed}/${f.tested} points not on screen, first at +${f.firstMiss?.y}px (hit ${f.firstMiss?.hit})`)
  if (f.widens) why.push(`makes the page ${f.widens}px wide`)
  say(`  CLIPPED  ${f.key.padEnd(22)} ${f.kind.padEnd(8)} "${f.label}"${f.ctx ? ` in ${f.ctx}` : ''} — ${why.join('; ')}`)
}
check(findings.filter((f) => f.wouldNotOpen).length === 0,
  `D1: every disclosure found could be opened by a click (${findings.filter((f) => f.wouldNotOpen).length} would not)`)
check(findings.filter((f) => !f.wouldNotOpen).length === 0,
  `D1: no open disclosure hides its content or widens the page at 390, 1024 or 1440 (${findings.filter((f) => !f.wouldNotOpen).length} found)`)
const trappedKinds = [...new Set(trapped.map((t) => t.cb))]
for (const t of trapped.slice(0, 12)) say(`  TRAPPED  ${t.key.padEnd(22)} "${t.label}" inside ${t.cb}`)
if (trapped.length > 12) say(`  … and ${trapped.length - 12} more`)
check(trapped.length === 0,
  `D1: no card trigger sits inside a box a fixed card would be placed against instead of the viewport (${trapped.length} do${trappedKinds.length ? `: ${trappedKinds.join(', ')}` : ''})`)

say('')
say('-'.repeat(70))
say(fails === 0 ? 'ALL DISCLOSURE CHECKS PASS (D1)' : `${fails} check(s) FAILED`)
process.exitCode = fails ? 1 : 0
