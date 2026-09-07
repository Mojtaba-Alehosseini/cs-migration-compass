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
    const cs = getComputedStyle(el)
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false
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
  // What is painted behind an element: composite every ancestor's background,
  // innermost first, over the paper. A translucent panel over textured paper
  // is a real pair on this site (--surface-raised is rgba .72).
  const paperColor = parse(getComputedStyle(document.body).backgroundColor) || [246, 243, 236, 1]
  const bgBehind = (el) => {
    const layers = []
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const c = parse(getComputedStyle(e).backgroundColor)
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break }
    }
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
  // 2.5.8's EQUIVALENT exception, asserted by the page and CHECKED here: a
  // container may name a selector whose controls do the same job at full size.
  // The exemption applies only if that selector actually resolves to visible
  // controls that are themselves >= 24x24 — an assertion nobody can rubber
  // stamp, because a wrong or stale selector simply fails to exempt anything.
  const equivalentHolds = (el) => {
    const host = el.closest('[data-target-equivalent]')
    if (!host) return false
    const alt = [...document.querySelectorAll(host.getAttribute('data-target-equivalent'))]
      .filter((a) => visible(a))
    return alt.length > 0 && alt.every((a) => {
      const r = a.getBoundingClientRect()
      return r.width >= 24 && r.height >= 24
    })
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

const COMBOS = [
  ['light', 1440, 900, false], ['dark', 1440, 900, false],
  ['light', 390, 844, true], ['dark', 390, 844, true],
]

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

let done = 0
for (const [id, url, setup] of list) {
  done += 1
  process.stdout.write(`  [${String(done).padStart(3)}/${list.length}] ${id}` + String.fromCharCode(10))
  try {
    await page.viewport(1440, 900)
    await page.eval(`document.documentElement.setAttribute('data-mode', 'light')`)
    await land(id, url, setup)
    for (const [mode, w, h, mobile] of COMBOS) {
      await page.viewport(w, h, mobile)
      await page.eval(`document.documentElement.setAttribute('data-mode', ${JSON.stringify(mode)})`)
      await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — ${mode}/${w}` })
      const f = JSON.parse(await page.eval(AUDIT))
      results.push({ id, mode, viewport: w, ...f })
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
