/* The chart engine — SVG, no dependencies.
 *
 * It replaced Recharts, which cost 380 KB to download and parse on every
 * Explore and Compare visit. This file is a few hundred lines and does the
 * things this site actually needs, which Recharts could not:
 *
 *   · a forecast grammar that never blends — actual, an institution's
 *     projection, our own naive extrapolation, a benchmark, a range band, each
 *     drawn so you can tell them apart without a legend;
 *   · morphs that start from the CURRENT on-screen position, so grabbing a
 *     moving chart never makes it jump;
 *   · direct manipulation at 1:1 with pointer capture, for the rebase handle.
 *
 * React owns the host element; this owns its contents. That division is what
 * lets a morph run at 60 fps without a re-render per frame.
 *
 * Motion durations are read from the CSS duration tokens on every animation, so
 * `prefers-reduced-motion` — which zeroes those tokens in tokens.css — puts
 * every chart into its final state without this file testing for it.
 */

/** [x, y, thinSample?, extra?] — y is null where the series has no value. */
export type Pt = [number, number | null, boolean?, unknown?]

export type SeriesMode =
  | 'actual' /** observed data — solid, full weight */
  | 'projection' /** an institution's forecast — paler solid, carries a chip */
  | 'naive' /** ours — dashed, labelled "not a forecast" */
  | 'benchmark' /** a reference line, never a member — grey dashed */
  | 'lo' /** the lower edge of a band */
  /** Package 12: what employers ADVERTISE while hiring — a different
   *  quantity from every mode above, all five of which are some form of
   *  what people ARE paid (measured, forecast, extrapolated, or a reference
   *  point drawn from the same kind of survey). Advertised ranges are wide,
   *  usually exclude equity/bonus, and are selected toward roles currently
   *  hard to fill — never a restyle of 'actual', never blended with it.
   *  Drawn as a dotted, thicker, lower-opacity line specifically so it
   *  reads as "a different KIND of line" at a glance, not just a different
   *  colour of the same kind (see strokeFor's own comment). */
  | 'advertised'

export interface Series {
  key: string
  /** Drawn at the end of the line. Omit to keep a series unlabelled. */
  label?: string
  /** Shown in the scrub readout when it differs from the end label. */
  hoverLabel?: string
  /** Any CSS colour — `var(--c-DE)` keeps it theme-reactive for free. */
  color: string
  mode?: SeriesMode
  markers?: boolean
  /** Kept out of the scrub readout (a duplicate of another row). */
  noRead?: boolean
  pts: Pt[]
}

export interface Axis {
  min: number
  max: number
  /** [value, label] — the label is drawn verbatim, in the field's tick language. */
  ticks: [number, string][]
}

export interface ChartCfg {
  /** The sentence a screen reader gets for the whole figure. */
  aria: string
  w?: number
  h?: number
  padL?: number
  padR?: number
  padT?: number
  x: Axis
  y: Axis
  series: Series[]
  /** Filled area between two series keys. */
  bands?: { hi: string; lo: string; color: string }[]
  /** A stronger rule at this y value (0 on a change chart). */
  zero?: number | null
  /** A dashed vertical rule labelled "today". */
  today?: number | null
  /** Everything right of this x is tinted as the future. */
  future?: number | null
  /** Event rules: [x, label]. */
  ann?: [number, string][]
  fmtX?: (v: number) => string
  fmtV?: (p: Pt, s: Series) => string
}

type Screen = [number, number, boolean | undefined, unknown][]

const esc = (s: unknown) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;')

/** Read a duration token in ms. Reduced motion zeroes these, which is how the
 *  whole kit inherits the fallback rather than testing for it. */
function dur(name: string, fallback: number): number {
  if (typeof getComputedStyle !== 'function') return fallback
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  if (!raw) return fallback
  const n = parseFloat(raw)
  return Number.isFinite(n) ? (raw.endsWith('ms') ? n : n * 1000) : fallback
}

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)

const warned = new Set<string>()

/** An axis whose labels are not injective describes nothing: two positions that
 *  say the same thing cannot both be read. This is how a clamping formatter —
 *  right for a single figure, wrong for a scale — got onto an axis and rendered
 *  five of six ticks as "100+ yrs".
 *
 *  Loud in development, once and quiet in production: a visitor should still get
 *  their chart, but nobody should be able to ship this again. */
export function assertInjectiveTicks(axis: 'x' | 'y', ticks: [number, string][], aria: string) {
  const labels = ticks.map(([, l]) => l)
  if (new Set(labels).size === labels.length) return
  const dupes = labels.filter((l, i) => labels.indexOf(l) !== i)
  const msg = `Chart "${aria}": the ${axis} axis has ${labels.length} ticks but `
    + `${new Set(labels).size} distinct labels — ${JSON.stringify([...new Set(dupes)])} repeats. `
    + 'A tick formatter must be injective over its tick set; use the metric\'s tickFormat, '
    + 'not its display format.'
  if (import.meta.env.DEV) throw new Error(msg)
  const key = `${aria}:${axis}`
  if (!warned.has(key)) { warned.add(key); console.error(msg) }
}

export function makeChart(host: HTMLElement) {
  const st: {
    cfg: ChartCfg | null
    S: ReturnType<typeof scales> | null
    pts: Record<string, Screen>
    raf: number
  } = { cfg: null, S: null, pts: {}, raf: 0 }

  function scales(c: ChartCfg) {
    const W = c.w ?? 940
    const H = c.h ?? 270
    const PL = c.padL ?? 52
    const PR = c.padR ?? 86
    const PT = c.padT ?? 24
    const PB = 28
    return {
      W, H, PL, PR, PT, PB,
      X: (v: number) => PL + ((v - c.x.min) / (c.x.max - c.x.min)) * (W - PL - PR),
      Y: (v: number) => H - PB - ((v - c.y.min) / (c.y.max - c.y.min)) * (H - PT - PB),
    }
  }

  function toScreen(c: ChartCfg, S: ReturnType<typeof scales>): Record<string, Screen> {
    const out: Record<string, Screen> = {}
    for (const sr of c.series) {
      out[sr.key] = sr.pts
        .filter((p) => p[1] != null)
        .map((p) => [S.X(p[0]), S.Y(p[1] as number), p[2], p[3]] as Screen[number])
    }
    return out
  }

  const d = (pp: Screen) =>
    pp.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('')

  /** How each series mode reads at a glance. The grammar is the point: these
   *  are never blended, and never averaged into one another. */
  function strokeFor(mode: SeriesMode) {
    switch (mode) {
      case 'naive': return 'stroke-dasharray="4 4" opacity=".55" stroke-width="1.6"'
      case 'benchmark': return 'stroke-dasharray="2 4" opacity=".8" stroke-width="1.5"'
      case 'projection': return 'opacity=".72" stroke-width="2.2"'
      case 'lo': return 'stroke-dasharray="3 3" opacity=".75" stroke-width="1.6"'
      // A dotted (not dashed) 1:2 pattern — every other mode above uses a
      // dash, so a dot is the one pattern that can't be mistaken for
      // "actual, but degraded" the way another dashed mode could.
      case 'advertised': return 'stroke-dasharray="1 3" stroke-linecap="round" opacity=".65" stroke-width="2.4"'
      default: return 'stroke-width="2.2"'
    }
  }

  function build(c: ChartCfg, noDraw?: boolean) {
    st.cfg = c
    assertInjectiveTicks('x', c.x.ticks, c.aria)
    assertInjectiveTicks('y', c.y.ticks, c.aria)
    const S = scales(c)
    st.S = S
    st.pts = toScreen(c, S)
    let s = `<svg viewBox="0 0 ${S.W} ${S.H}" role="img" aria-label="${esc(c.aria)}">`

    if (c.future != null) {
      s += `<rect x="${S.X(c.future)}" y="${S.PT}" width="${S.W - S.PR - S.X(c.future)}"`
        + ` height="${S.H - S.PT - S.PB}" fill="var(--ink-1)" opacity=".03"/>`
        + `<text x="${S.W - S.PR - 5}" y="${S.PT + 11}" font-size="9.5" fill="var(--ink-3)"`
        + ` text-anchor="end">projection →</text>`
    }

    s += '<g class="ticks">'
    for (const [v] of c.y.ticks) {
      s += `<line x1="${S.PL}" x2="${S.W - S.PR}" y1="${S.Y(v)}" y2="${S.Y(v)}" class="gridline"/>`
    }
    for (const [v] of c.x.ticks) {
      s += `<line y1="${S.PT}" y2="${S.H - S.PB}" x1="${S.X(v)}" x2="${S.X(v)}" class="gridline"/>`
    }
    if (c.zero != null) {
      s += `<line x1="${S.PL}" x2="${S.W - S.PR}" y1="${S.Y(c.zero)}" y2="${S.Y(c.zero)}" class="zeroline"/>`
    }
    for (const [v, l] of c.y.ticks) {
      s += `<text x="${S.PL - 7}" y="${S.Y(v) + 3}" font-size="10" fill="var(--ink-3)" text-anchor="end">${esc(l)}</text>`
    }
    for (const [v, l] of c.x.ticks) {
      s += `<text x="${S.X(v)}" y="${S.H - S.PB + 15}" font-size="10" fill="var(--ink-3)" text-anchor="middle">${esc(l)}</text>`
    }
    s += '</g>'

    if (c.today != null) {
      const tx = S.X(c.today)
      s += `<line x1="${tx}" x2="${tx}" y1="${S.PT}" y2="${S.H - S.PB}" class="zeroline" stroke-dasharray="3 4"/>`
        + `<text x="${tx - 4}" y="${S.PT + 10}" font-size="9.5" fill="var(--ink-3)" text-anchor="end">today</text>`
    }
    for (const [ax0, label] of c.ann ?? []) {
      const ax = S.X(ax0)
      s += `<line x1="${ax}" x2="${ax}" y1="${S.PT}" y2="${S.H - S.PB}" stroke="var(--warn)" stroke-dasharray="2 4" opacity=".5"/>`
        + `<text x="${ax + 4}" y="${S.PT + 10}" font-size="9.5" fill="var(--warn)" opacity=".85">${esc(label)}</text>`
    }

    s += '<g class="plot">'
    for (const b of c.bands ?? []) {
      const hi = st.pts[b.hi]
      const lo = st.pts[b.lo]
      if (hi?.length && lo?.length) {
        s += `<path class="band" d="${d(hi)}${lo.slice().reverse().map((p) => 'L' + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('')}Z"`
          + ` fill="${b.color}" opacity=".14"/>`
      }
    }
    for (const sr of c.series) {
      const pp = st.pts[sr.key]
      if (!pp?.length) continue
      s += `<path class="ser" data-k="${esc(sr.key)}" d="${d(pp)}" fill="none" stroke="${sr.color}"`
        + ` ${strokeFor(sr.mode ?? 'actual')} stroke-linejoin="round" stroke-linecap="round"/>`
      if (sr.markers) {
        // A hollow marker means a thin sample: the point is real, the number
        // behind it is a handful of answers.
        s += pp.map((p) => `<circle class="mk" data-k="${esc(sr.key)}" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2.6" `
          + (p[2] === true
            ? `fill="var(--surface)" stroke="${sr.color}" stroke-width="1.4"`
            : `fill="${sr.color}"`) + '/>').join('')
      }
    }
    s += '</g>'

    // End labels, pushed apart just enough to stay readable.
    const ends: { y: number; label: string; color: string; key: string }[] = []
    for (const sr of c.series) {
      const pp = st.pts[sr.key]
      if (!pp?.length || sr.mode === 'naive' || sr.mode === 'projection' || !sr.label) continue
      ends.push({
        y: pp[pp.length - 1]![1],
        label: sr.label,
        color: sr.mode === 'benchmark' ? 'var(--ink-3)' : sr.color,
        key: sr.key,
      })
    }
    ends.sort((a, b) => a.y - b.y)
    for (let i = 1; i < ends.length; i++) {
      if (ends[i]!.y - ends[i - 1]!.y < 11) ends[i]!.y = ends[i - 1]!.y + 11
    }
    s += ends.map((e) => `<text class="el" data-k="${esc(e.key)}" x="${S.W - S.PR + 6}"`
      + ` y="${Math.max(S.PT + 6, Math.min(S.H - S.PB, e.y)) + 3}" font-size="10" fill="${e.color}">${esc(e.label)}</text>`).join('')

    s += `<line class="xh" y1="${S.PT}" y2="${S.H - S.PB}" stroke="var(--ink-1)" opacity="0"/>`
    s += '</svg><div class="readout" role="status" aria-live="off"></div>'
    host.innerHTML = s
    if (!noDraw) drawIn()
    attachScrub(S)
  }

  /** Once per chart, on first visibility. Never on a re-render. */
  function drawIn() {
    const D = dur('--dur-draw', 700)
    const stagger = dur('--dur-draw-stagger', 80)
    if (!D) return
    host.querySelectorAll<SVGPathElement>('path.ser').forEach((p, i) => {
      if (p.getAttribute('stroke-dasharray')) return // dashed by design; leave it
      if (typeof p.getTotalLength !== 'function') return
      const L = p.getTotalLength()
      p.style.strokeDasharray = String(L)
      p.style.strokeDashoffset = String(L)
      p.getBoundingClientRect()
      p.style.transition = `stroke-dashoffset ${D + i * stagger}ms var(--ease-out)`
      p.style.strokeDashoffset = '0'
    })
    host.querySelectorAll<SVGCircleElement>('.mk').forEach((m, i) => {
      m.style.transformOrigin = `${m.getAttribute('cx')}px ${m.getAttribute('cy')}px`
      m.style.transform = 'scale(0)'
      m.getBoundingClientRect()
      m.style.transition = `transform ${D * 0.49}ms var(--ease-out) ${D * 0.43 + i * 10}ms`
      m.style.transform = 'scale(1)'
    })
  }

  /** Value change. Interpolates SCREEN coordinates from wherever each series is
   *  RIGHT NOW, so interrupting a morph continues from the visible position
   *  instead of snapping to the last target. */
  function morph(cB: ChartCfg) {
    cancelAnimationFrame(st.raf)
    const S = scales(cB)
    const to = toScreen(cB, S)
    const from = st.pts
    const keys = cB.series
      .map((s) => s.key)
      .filter((k) => from[k] && to[k] && from[k]!.length === to[k]!.length)

    const nodes: Record<string, SVGPathElement> = {}
    host.querySelectorAll<SVGPathElement>('path.ser').forEach((p) => { nodes[p.dataset.k!] = p })
    const mks: Record<string, SVGCircleElement[]> = {}
    host.querySelectorAll<SVGCircleElement>('.mk').forEach((m) => {
      (mks[m.dataset.k!] ??= []).push(m)
    })
    const els: Record<string, SVGTextElement> = {}
    host.querySelectorAll<SVGTextElement>('.el').forEach((e) => { els[e.dataset.k!] = e })

    const tickG = host.querySelector<SVGGElement>('.ticks')
    if (tickG) {
      tickG.style.transition = `opacity ${dur('--dur-crossfade', 180) * 0.83}ms`
      tickG.style.opacity = '0'
    }
    // A series that does not survive into the target fades rather than vanishing.
    const target = new Set(cB.series.map((s) => s.key))
    host.querySelectorAll<SVGPathElement>('path.ser').forEach((p) => {
      if (!target.has(p.dataset.k!)) p.style.opacity = '0'
    })

    const D = dur('--dur-morph', 380)
    if (!D || !keys.length) { build(cB, true); return }

    const t0 = performance.now()
    const step = (t: number) => {
      const k0 = easeInOut(Math.min(1, (t - t0) / D))
      for (const k of keys) {
        const f = from[k]!
        const tgt = to[k]!
        const cur: Screen = f.map((p, i) => [
          p[0] + (tgt[i]![0] - p[0]) * k0,
          p[1] + (tgt[i]![1] - p[1]) * k0,
          tgt[i]![2],
          tgt[i]![3],
        ])
        nodes[k]?.setAttribute('d', d(cur))
        ;(mks[k] ?? []).forEach((m, i) => {
          if (!cur[i]) return
          m.setAttribute('cx', cur[i]![0].toFixed(1))
          m.setAttribute('cy', cur[i]![1].toFixed(1))
        })
        const e = els[k]
        if (e && cur.length) {
          e.setAttribute('y', (Math.max(S.PT + 6, Math.min(S.H - S.PB, cur[cur.length - 1]![1])) + 3).toFixed(1))
        }
        st.pts[k] = cur
      }
      if (k0 < 1) st.raf = requestAnimationFrame(step)
      else build(cB, true)
    }
    st.raf = requestAnimationFrame(step)
  }

  /** Geometry change — line to slope, overlay to grid. Nothing to interpolate
   *  between, so it crossfades instead of pretending to be continuous. */
  function fade(cB: ChartCfg) {
    const D = dur('--dur-crossfade', 180)
    if (!D) { build(cB, true); return }
    host.style.transition = `opacity ${D * 0.83}ms`
    host.style.opacity = '0'
    window.setTimeout(() => {
      build(cB, true)
      host.style.opacity = '1'
    }, D * 0.89)
  }

  /** Direct manipulation: same scales, same nodes, no teardown — so a captured
   *  pointer keeps its element for the whole drag and the update is 1:1. */
  function updateSeries(cB: ChartCfg) {
    const S = st.S
    if (!S) { build(cB, true); return }
    st.cfg = cB
    st.pts = toScreen(cB, S)
    const els: Record<string, SVGTextElement> = {}
    host.querySelectorAll<SVGTextElement>('.el').forEach((e) => { els[e.dataset.k!] = e })
    host.querySelectorAll<SVGPathElement>('path.ser').forEach((p) => {
      const pp = st.pts[p.dataset.k!]
      if (pp) p.setAttribute('d', d(pp))
    })
    for (const k in st.pts) {
      const e = els[k]
      const pp = st.pts[k]!
      if (e && pp.length) {
        e.setAttribute('y', (Math.max(S.PT + 6, Math.min(S.H - S.PB, pp[pp.length - 1]![1])) + 3).toFixed(1))
      }
    }
  }

  function attachScrub(S: ReturnType<typeof scales>) {
    const svg = host.querySelector<SVGSVGElement>('svg')
    const ro = host.querySelector<HTMLDivElement>('.readout')
    const xh = host.querySelector<SVGLineElement>('.xh')
    if (!svg || !ro || !xh || !st.cfg?.fmtX) return

    const hide = () => { ro.style.opacity = '0'; xh.setAttribute('opacity', '0') }
    const show = (ev: PointerEvent) => {
      // Always the LIVE cfg: the rebase handle rewrites it under us mid-drag.
      const c = st.cfg
      if (!c?.fmtX || !c.fmtV) return
      const xs = [...new Set(c.series.flatMap((s) => s.pts.map((p) => p[0])))].sort((a, b) => a - b)
      const r = svg.getBoundingClientRect()
      const mx = ((ev.clientX - r.left) / r.width) * S.W
      if (mx < S.PL - 4 || mx > S.W - S.PR + 4) { hide(); return }
      const xv = c.x.min + ((mx - S.PL) / (S.W - S.PL - S.PR)) * (c.x.max - c.x.min)
      let best = xs[0]!
      for (const x of xs) if (Math.abs(x - xv) < Math.abs(best - xv)) best = x

      let rows = ''
      for (const sr of c.series) {
        if (sr.mode === 'naive' || sr.noRead) continue
        const p = sr.pts.find((q) => q[0] === best && q[1] != null)
        if (!p) continue
        rows += `<div class="r"><span><i style="background:${sr.mode === 'benchmark' ? 'var(--ink-3)' : sr.color}"></i>`
          + `${esc(sr.hoverLabel ?? sr.label ?? '')}</span><b>${esc(c.fmtV(p, sr))}</b></div>`
      }
      if (!rows) { hide(); return }
      ro.innerHTML = `<b>${esc(c.fmtX(best))}</b>${rows}`
      ro.style.opacity = '1'
      const px = (S.X(best) / S.W) * r.width
      ro.style.left = `${Math.min(r.width - 190, Math.max(2, px))}px`
      xh.setAttribute('x1', String(S.X(best)))
      xh.setAttribute('x2', String(S.X(best)))
      xh.setAttribute('opacity', '.25')
    }

    svg.addEventListener('pointermove', show)
    svg.addEventListener('pointerdown', (e) => { svg.setPointerCapture(e.pointerId); show(e) })
    svg.addEventListener('pointerleave', hide)
  }

  return {
    build,
    morph,
    fade,
    updateSeries,
    host,
    get scaleState() { return st.S },
    destroy() { cancelAnimationFrame(st.raf) },
  }
}

export type ChartHandle = ReturnType<typeof makeChart>
