/* Package 43, tier 2 — the objective half of the critique, as measurements.
 *
 * A critique that says "the caption looks small" is an opinion. One that says
 * "this text renders at 10px against a floor of 12" is a defect, and it is the
 * only kind Tier 3 is allowed to fix without a screenshot pair. So the
 * provable classes are measured here, on the rendered page, in both modes and
 * at the two viewports that matter, over every target the inventory reaches:
 *
 *   overflow   the document is wider than the viewport — the page body
 *              scrolls sideways, which DESIGN.md forbids
 *   type       visible text rendered below the 12px floor
 *   target     an interactive element smaller than 24x24 (WCAG 2.5.8)
 *   contrast   visible text under 4.5:1 (3:1 for large) against what is
 *              ACTUALLY painted behind it — resolved by walking up to the
 *              first opaque ancestor, so text on a chip is measured against
 *              the chip and not against the paper two layers down. That is
 *              the adjacent-pair failure package 29 shipped: a track darkened
 *              until the band on top of it measured 1.01:1.
 *
 * Every finding carries a selector and a text snippet so it can be found on
 * the screenshot, and the theme/mode/viewport it was found in so it can be
 * verified in exactly that state after the fix.
 *
 * Run:  node scripts/tests/audit_visual.mjs
 *       AUDIT_ONLY=openings,data node scripts/tests/audit_visual.mjs
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { launch, openPage } from './cdp.mjs'
import { defaultTargets, SETUP_HELPERS, REPO } from './inventory_figures.mjs'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const ONLY = new Set((process.env.AUDIT_ONLY ?? '').split(',').map((s) => s.trim()).filter(Boolean))

const AUDIT = String.raw`
(() => {
  const norm = (s) => (s ?? '').replace(/\s+/g, ' ').trim()
  const vw = window.innerWidth

  const sel = (el) => {
    const parts = []
    let e = el
    for (let i = 0; e && e !== document.body && i < 4; i++) {
      let p = e.tagName.toLowerCase()
      if (e.id) p += '#' + e.id
      else if (typeof e.className === 'string' && e.className.trim()) p += '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.')
      parts.unshift(p)
      e = e.parentElement
    }
    return parts.join(' > ')
  }

  const visible = (el) => {
    if (!(el instanceof Element)) return false
    if (el.closest('.visually-hidden, .sr-only, noscript, title, script, style')) return false
    /* Content inside a CLOSED <details> is skipped for rendering but keeps its
     * last layout box and its last used colour. getComputedStyle returns that
     * stale colour while custom properties resolve to the CURRENT theme — so
     * after a mode flip those elements read light-mode ink on a dark-mode
     * surface, in the same synchronous snapshot, which is impossible for
     * anything actually on the screen. It produced 786 findings on /work
     * alone, intermittently, depending on which mode had been measured last.
     * Nobody can see this text; it is not a contrast defect. */
    if (el.closest('details:not([open])')) return false
    const cs = getComputedStyle(el)
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false
    // Chrome's own answer where it has one — it knows about content-visibility
    // and skipped subtrees, which the property checks above do not cover.
    if (typeof el.checkVisibility === 'function'
      && !el.checkVisibility({ contentVisibilityAuto: true, opacityProperty: true, visibilityProperty: true })) return false
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0
  }

  // ---- colour maths (same formulas as C6) ----
  const parse = (s) => {
    if (!s) return null
    let m = s.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/)
    if (m) return [+m[1], +m[2], +m[3], m[4] == null ? 1 : +m[4]]
    m = s.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?/)
    if (m) return [+m[1] * 255, +m[2] * 255, +m[3] * 255, m[4] == null ? 1 : +m[4]]
    return null
  }
  const lum = (r, g, b) => {
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
  }
  const ratio = (a, b) => {
    const l1 = lum(a[0], a[1], a[2]), l2 = lum(b[0], b[1], b[2])
    const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]
    return (hi + 0.05) / (lo + 0.05)
  }
  const over = (top, under) => {
    const a = top[3]
    return [top[0] * a + under[0] * (1 - a), top[1] * a + under[1] * (1 - a), top[2] * a + under[2] * (1 - a), 1]
  }
  // What is painted behind an element.
  //
  // The DOM parent is NOT the visual backdrop, and this instrument learned it
  // the same way inventory_figures.mjs did. The segmented control's chosen
  // option is --paper text over a .thumb that is an absolutely-positioned
  // SIBLING; walking ancestors finds the track's --surface instead and scores
  // a legible 18.7:1 as 1.11:1 — 96 pages of it, the moment package 43 put
  // that control on every city page.
  //
  // elementsFromPoint gives the real paint stack at the element's own centre:
  // everything actually drawn there, topmost first. Composite from the element
  // downward. The ancestor walk stays as the fallback for anything off-screen,
  // where the browser cannot hit-test at all.
  const paperColor = parse(getComputedStyle(document.body).backgroundColor) || [246, 243, 236, 1]
  // The fallback, for anything the browser cannot hit-test because it is off
  // screen. Walk ancestors, but at each step also look at that ancestor's own
  // positioned children: an absolutely-positioned SIBLING that covers this
  // element's centre is painted behind its text even though it is nowhere on
  // the ancestor chain. That is the segmented control's thumb, and without
  // this the off-screen half of every page scores it at 1.1:1.
  //
  // It cannot resolve z-order the way elementsFromPoint does, so it takes the
  // first opaque covering sibling it finds. Above the fold the hit test is
  // used instead and this never runs.
  const ancestorLayers = (el) => {
    const r = el.getBoundingClientRect()
    const cx = r.left + r.width / 2
    const cy = r.top + r.height / 2
    const covers = (e) => {
      const b = e.getBoundingClientRect()
      return b.left <= cx && b.right >= cx && b.top <= cy && b.bottom >= cy
    }
    const layers = []
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const own = parse(getComputedStyle(e).backgroundColor)
      if (own && own[3] > 0) { layers.push(own); if (own[3] >= 1) break }
      const parent = e.parentElement
      if (!parent) continue
      let stop = false
      for (const sib of parent.children) {
        if (sib === e || sib.contains(el) || el.contains(sib)) continue
        const cs = getComputedStyle(sib)
        if (cs.position === 'static' || cs.display === 'none' || Number(cs.opacity) === 0) continue
        if (!covers(sib)) continue
        const c = parse(cs.backgroundColor)
        if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) { stop = true; break } }
      }
      if (stop) break
    }
    return layers
  }
  const paintedLayers = (el) => {
    const r = el.getBoundingClientRect()
    const cx = r.left + r.width / 2
    const cy = r.top + r.height / 2
    if (cx < 0 || cy < 0 || cx > vw || cy > window.innerHeight) return null
    const stack = document.elementsFromPoint(cx, cy)
    const at = stack.findIndex((e) => e === el || el.contains(e))
    if (at < 0) return null
    const layers = []
    for (let i = at; i < stack.length; i++) {
      const e = stack[i]
      // The element's OWN background counts — text sits on it. Only its
      // descendants are excluded: they are in front of the text, not behind
      // it. Skipping the element itself scored the month bar's
      // white-on-terracotta at 1.03:1, having just measured it at 5.86 on the
      // page. (No backticks in here: String.raw template.)
      if (e !== el && el.contains(e)) continue
      const c = parse(getComputedStyle(e).backgroundColor)
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break }
    }
    return layers.length ? layers : null
  }
  const bgBehind = (el) => {
    const layers = paintedLayers(el) ?? ancestorLayers(el)
    let out = paperColor[3] >= 1 ? paperColor : over(paperColor, [246, 243, 236, 1])
    for (let i = layers.length - 1; i >= 0; i--) out = over(layers[i], out)
    return out
  }

  const findings = { overflow: [], type: [], target: [], contrast: [] }

  // ---- overflow ----
  const sw = document.documentElement.scrollWidth
  if (sw > vw + 1) {
    // Name the widest offenders, not just the fact.
    const wide = [...document.querySelectorAll('body *')]
      .filter((el) => visible(el) && el.getBoundingClientRect().right > vw + 1)
      .sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right)
      .slice(0, 4)
      .map((el) => ({ sel: sel(el), right: Math.round(el.getBoundingClientRect().right), text: norm(el.textContent).slice(0, 50) }))
    findings.overflow.push({ scrollWidth: sw, viewport: vw, widest: wide })
  }

  // ---- type floor and contrast, over every text-bearing leaf ----
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const seen = new Set()
  let n
  while ((n = walker.nextNode())) {
    const t = norm(n.nodeValue)
    if (!t) continue
    const el = n.parentElement
    if (!el || seen.has(el) || !visible(el)) continue
    seen.add(el)
    const cs = getComputedStyle(el)
    const size = parseFloat(cs.fontSize)
    const weight = parseInt(cs.fontWeight, 10) || 400
    if (size < 12) findings.type.push({ sel: sel(el), size: +size.toFixed(1), text: t.slice(0, 40) })

    const fg = parse(cs.color)
    if (!fg) continue
    const bg = bgBehind(el)
    const fgc = fg[3] < 1 ? over(fg, bg) : fg
    const r = ratio(fgc, bg)
    const large = size >= 24 || (size >= 18.66 && weight >= 700)
    const need = large ? 3 : 4.5
    if (r < need) {
      findings.contrast.push({ sel: sel(el), ratio: +r.toFixed(2), need, size: +size.toFixed(1),
        fg: cs.color, bg: 'rgb(' + bg.slice(0, 3).map(Math.round).join(',') + ')', text: t.slice(0, 40) })
    }
  }

  // ---- copy weight: data for a judgement, not a defect ----
  // The work order's line is that a 425-character caption is a design failure
  // wearing prose. Whether a given one IS that is a judgement, so this only
  // records the longest captions and sub-lines per page, with their length,
  // so the judgement in tier 2 is made against a number and a screenshot.
  findings.copy = [...document.querySelectorAll('.sub, .oneline, figcaption, p.mapfoot, .insight, small')]
    .filter((el) => visible(el) && !el.closest('[role="dialog"]'))
    .map((el) => ({ sel: sel(el), chars: norm(el.textContent).length, text: norm(el.textContent).slice(0, 90) }))
    .filter((c) => c.chars >= 180)
    .sort((a, b) => b.chars - a.chars)
    .slice(0, 5)

  // ---- hit targets (WCAG 2.5.8, 24x24) ----
  // THREE of that criterion's own exceptions are applied, so the bucket holds
  // defects rather than noise:
  //
  //   label     a control INSIDE a <label> is operable across the whole label,
  //             so the label's box is the target.
  //   inline    a link sitting in a line of text — a <Figure> trigger inside a
  //             sentence, a breadcrumb — is exempt, because enlarging it would
  //             break the line it lives in.
  //   spacing   the criterion's OWN principal exception, and the one whose
  //             absence made the first run of this audit useless: an
  //             undersized target is exempt if a 24px-diameter circle centred
  //             on it touches no other target and no other undersized target's
  //             circle. A 137x19 link alone in a table row 34px tall cannot be
  //             mis-tapped; a 10px map dot in a cloud of map dots can. Without
  //             this the audit reported 993 "defects", nearly all of them rows
  //             of a table.
  //
  // A target nested inside another target is skipped as a pair: the outer box
  // always intersects the inner one, and the risk 2.5.8 is about — hitting the
  // WRONG control — does not arise when hitting either lands you in the same
  // place.
  const inline = (el) => {
    const p = el.parentElement
    if (!p) return false
    const ownText = [...p.childNodes].some((c) => c.nodeType === 3 && norm(c.nodeValue))
    return ownText && getComputedStyle(el).display.startsWith('inline')
  }
  // A sticky header floats OVER the page. Once the page is scrolled, a card
  // that has slid underneath it is 8px away in rect space and unreachable in
  // tap space, so pairing the two reports a collision that cannot happen.
  // Compare targets only within their own layer.
  const layerOf = (el) => {
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const p = getComputedStyle(e).position
      if (p === 'fixed' || p === 'sticky') return sel(e)
    }
    return ''
  }
  const targets = []
  for (const el of document.querySelectorAll('a[href], button, input, select, textarea, summary, [role="button"], [role="tab"]')) {
    if (!visible(el)) continue
    if (el.matches('input[type="range"]')) continue // the thumb is the target, and it is native
    if (el.matches('a, button') && inline(el)) continue
    const box = el.matches('input, select') && el.closest('label') ? el.closest('label') : el
    const r = box.getBoundingClientRect()
    targets.push({ el, box, r, small: r.width < 24 || r.height < 24, layer: layerOf(el) })
  }
  const gap = (cx, cy, r) => Math.hypot(
    Math.max(r.left - cx, 0, cx - r.right),
    Math.max(r.top - cy, 0, cy - r.bottom),
  )
  // Is the element actually the thing you would hit at its own centre? The
  // browser's hit test answers what my geometry cannot: an expanded picker
  // panel floating over the rows behind it makes those rows unreachable, so
  // pairing them with the panel's own controls reports a collision that no
  // finger can produce. Let the page decide, rather than special-casing
  // every way one box can end up over another.
  //
  // It runs on BOTH sides of the pair. A neighbour's bounding rect can cover
  // ground the neighbour does not paint -- a <label> wrapping a control
  // reports the union of its parts -- and pairing a button with empty space
  // inside somebody else's box reports a collision that is not on the screen.
  // Ask the page what is actually at each element's own centre.
  const reachable = (el) => {
    const r = el.getBoundingClientRect()
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2
    if (cx < 0 || cy < 0 || cx > vw || cy > window.innerHeight) return true // off-screen: cannot hit-test, keep it
    const top = document.elementFromPoint(cx, cy)
    return !!top && (top === el || el.contains(top) || top.contains(el))
  }
  // 2.5.8's EQUIVALENT exception, asserted by the page and checked here as far
  // as a machine can check it.
  //
  // The named selector must resolve to visible controls that are themselves
  // >= 24x24, that live OUTSIDE the exempting container, and that are at least
  // as numerous as the undersized targets inside it. Without those three, a
  // data-target-equivalent of "body" exempted everything — the adversarial
  // review demonstrated exactly that on /compare, at both widths, against a
  // comment claiming nobody could rubber stamp this.
  //
  // (No backticks in this comment: it lives inside a String.raw template, and
  // one would close it. That trap has cost this project eight sessions.)
  //
  // What it still cannot check, and what the comment must therefore not claim:
  // that the alternatives DO THE SAME THING. A page that names a same-sized,
  // equally numerous, outside set of controls that happen to do something else
  // will be believed. That is an author's assertion, and this narrows it
  // rather than verifying it.
  const equivalentHolds = (el) => {
    const host = el.closest('[data-target-equivalent]')
    if (!host) return false
    const sel2 = host.getAttribute('data-target-equivalent')
    if (!sel2 || !sel2.trim()) return false
    const alt = [...document.querySelectorAll(sel2)]
      .filter((a) => visible(a) && !host.contains(a) && !a.contains(host))
    if (!alt.length) return false
    if (!alt.every((a) => {
      const r = a.getBoundingClientRect()
      return r.width >= 24 && r.height >= 24
    })) return false
    const inside = [...host.querySelectorAll('a[href], button, input, select, textarea, summary, [role="button"], [role="tab"]')]
      .filter((t) => visible(t))
    return alt.length >= inside.length
  }
  for (const t of targets) {
    if (!t.small) continue
    const cx = t.r.left + t.r.width / 2
    const cy = t.r.top + t.r.height / 2
    if (!reachable(t.el)) continue
    if (equivalentHolds(t.el)) continue
    // The NEAREST neighbour, not the first one the loop happens to meet:
    // this field is the Tier 3 work list, and "crowded by a control on the
    // other side of the panel" sends the fix to the wrong element. Distance
    // is measured the way 2.5.8 measures it -- circle to circle for two
    // undersized targets, circle to box for an adequate one.
    let crowdedBy = null
    let best = Infinity
    for (const o of targets) {
      if (o === t) continue
      if (o.layer !== t.layer) continue
      if (o.box.contains(t.box) || t.box.contains(o.box)) continue
      if (!reachable(o.el)) continue
      const d = o.small
        ? Math.hypot(cx - (o.r.left + o.r.width / 2), cy - (o.r.top + o.r.height / 2)) - 12
        : gap(cx, cy, o.r)
      if (d < best) { best = d; crowdedBy = o }
    }
    // spacing exception: the 24px circle reaches nothing else
    if (!crowdedBy || best >= 12) continue
    findings.target.push({
      sel: sel(t.el), w: Math.round(t.r.width), h: Math.round(t.r.height),
      text: norm(t.el.textContent || t.el.getAttribute('aria-label') || '').slice(0, 40),
      // The neighbour's own text and box, not just its selector: sel() keeps
      // four ancestors and two classes, so two unrelated controls can print
      // the same string, and a Tier 3 fix aimed at the wrong one fixes
      // nothing. The rect says which element it actually was.
      crowdedBy: sel(crowdedBy.el),
      crowdedText: norm(crowdedBy.el.textContent || crowdedBy.el.getAttribute('aria-label') || '').slice(0, 30),
      crowdedAt: [Math.round(crowdedBy.r.left), Math.round(crowdedBy.r.top), Math.round(crowdedBy.r.width), Math.round(crowdedBy.r.height)],
      crowdedGap: +best.toFixed(1), // how far inside the 12px reach it sits
      at: [Math.round(t.r.left), Math.round(t.r.top)],
    })
  }
  return JSON.stringify(findings)
})()
`

/* Mode OUTSIDE, viewport inside — and the mode is applied by reloading, not by
 * flipping an attribute.
 *
 * Flipping data-mode leaves stale used-values behind in any subtree Chrome is
 * not rendering: a closed <details> keeps its last layout box AND its last
 * used colour, while its custom properties resolve to the new theme. The
 * result reads light-mode ink on a dark-mode surface in one synchronous
 * snapshot — impossible for anything on the screen — and it came and went
 * between identical runs, 786 findings on /work one time and 0 the next.
 * Excluding closed <details> removed most of it and not all.
 *
 * A reload has no stale anything. It costs one extra page load per target and
 * buys a number that does not depend on which mode was measured last. */
const MODES = ['light', 'dark']
const SIZES = [[1440, 900, false], [390, 844, true]]

const { targets } = defaultTargets(BASE)
const list = targets.filter(([id]) => !ONLY.size || ONLY.has(id))
const { port, close } = await launch({ port: 9921 })
const page = await openPage(port)
const results = []

async function land(id, url, setup) {
  if (setup) {
    await page.hashGo(url.replace(/#.*$/, '#/no-such-route'))
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — remount` })
  }
  await page.hashGo(url)
  await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — ${url}` })
  if (setup) {
    await page.eval('window.scrollTo(0, document.body.scrollHeight)')
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — deferred panels` })
    await page.eval(SETUP_HELPERS)
    const applied = await page.eval(setup)
    if (typeof applied === 'string' && applied.startsWith('NO ')) throw new Error(`setup for "${id}" did not find its control: ${applied}`)
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — after setup` })
  }
}

/* Motion off for the whole audit.
 *
 * `body` transitions background-color and color over --dur-base (260ms), and
 * flipping data-mode starts that transition. waitForReady() waits for network
 * idle and a stable DOM — a colour interpolating changes neither, so it can
 * return mid-transition, and then every colour on the page is a blend of the
 * two themes. One run of this audit reported 842 contrast findings on a single
 * target that way: light-mode ink measured against a dark-mode surface, on
 * st-openings-remote alone, because that target's setup toggles a checkbox and
 * shifted the timing. Earlier runs of the same code had got lucky.
 *
 * prefers-reduced-motion zeroes the duration tokens AND trips tokens.css's
 * universal 0.01ms override, so no transition can be sampled part-way. It
 * changes no settled colour, which is the only thing this instrument measures.
 */
await page.emulateReducedMotion(true)

/* Get onto the site's origin BEFORE anything writes localStorage. A fresh tab
 * sits on about:blank, which has no origin, and reading storage there is a
 * SecurityError — the same trap capture_site.mjs documents at the top of its
 * own loader. Reintroducing it here made three consecutive runs report
 * "0 findings" that were 0 because every target had errored. */
await page.goto(BASE)
await page.waitForReady({ quietMs: 250, timeoutMs: 30000, label: 'origin' })

let done = 0
for (const [id, url, setup] of list) {
  done += 1
  process.stdout.write(`  [${String(done).padStart(3)}/${list.length}] ${id}` + String.fromCharCode(10))
  try {
    for (const mode of MODES) {
      await page.viewport(1440, 900)
      // Written to storage and then LOADED, so index.html's own inline script
      // applies it before first paint and nothing on the page is left over.
      await page.eval(`(() => { localStorage.setItem('compass:mode', ${JSON.stringify(mode)}); return 1 })()`)
      await page.goto(BASE)
      await page.waitForReady({ quietMs: 250, timeoutMs: 30000, label: `${id} — ${mode} root` })
      await land(id, url, setup)
      for (const [w, h, mobile] of SIZES) {
      await page.viewport(w, h, mobile)
      await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — ${mode}/${w}` })
      const f = JSON.parse(await page.eval(AUDIT))
      results.push({ id, mode, viewport: w, ...f })
      }
    }
  } catch (e) {
    results.push({ id, error: String((e && e.message) || e) })
  }
}
await page.eval(`document.documentElement.setAttribute('data-mode', 'light')`)

// ---- summary ----
const cats = ['overflow', 'type', 'target', 'contrast']
const totals = Object.fromEntries(cats.map((c) => [c, results.reduce((a, r) => a + (r[c]?.length ?? 0), 0)]))
const byId = {}
for (const r of results) {
  if (r.error) continue
  for (const c of cats) if (r[c]?.length) (byId[r.id] ??= {})[`${c} ${r.mode}/${r.viewport}`] = r[c].length
}
// Distinct defects — the same selector at the same size counts once per category.
const distinct = {}
for (const c of cats) {
  const keys = new Set()
  for (const r of results) for (const f of r[c] ?? []) keys.add(c === 'overflow' ? `${r.id}@${r.viewport}` : `${f.sel}|${f.text}`)
  distinct[c] = keys.size
}
mkdirSync(REPO + '.status/evidence', { recursive: true })
writeFileSync(REPO + '.status/evidence/p43-audit.json', JSON.stringify({ generated_at: new Date().toISOString(), totals, distinct, results }, null, 1))
console.log('\nfindings (occurrences across 4 mode/viewport combos):', JSON.stringify(totals))
console.log('distinct defects:', JSON.stringify(distinct))
console.log(`errored targets: ${results.filter((r) => r.error).length}`)
console.log('wrote .status/evidence/p43-audit.json')
page.close()
close()
