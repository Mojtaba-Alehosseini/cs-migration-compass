/* The scatter builder — any metric against any other, 73 cities placed by their
 * real numbers.
 *
 * Three rules hold this chart together, and each of them was a bug first:
 *
 *   · Tick labels come from the metric's `tickFormat`, never its display
 *     `format`. A formatter that clamps at "100+ yrs" is right for one city and
 *     makes five of six ticks identical on an axis.
 *   · The domain is computed from STABLE values only. A figure the site itself
 *     has flagged as smaller than its own rounding error is not allowed to
 *     decide where 70 other cities are drawn.
 *   · Flagged points are still shown — in a labelled band at the edge of the
 *     plot, with their real number in the readout and in the CSV. Kept and
 *     named, never dropped, clipped or winsorised.
 *
 * Presets are examples, never a default lens the site pushes.
 */

import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useData } from '../data/store'
import { THEMES, METRICS, METRIC_BY_KEY, AXIS_METRICS, tickFormatFor, type ThemeKey } from '../data/registry'
import { UNSTABLE_METRIC_KEYS, stabilityOf } from '../data/compute'
import { assertInjectiveTicks } from './chart/engine'
import { downloadCsv } from '../lib/export'
import { useUrlPatch } from '../data/urlState'

const SCATTER_PRESETS = [
  { x: 'apt_m2', y: 'years_to_home', label: 'Cheap city or impossible city?' },
  { x: 'total_monthly', y: 'salary_gross', label: 'Salary against what a month costs' },
  { x: 'happiness_rank', y: 'savings', label: 'Money against life' },
  { x: 'summer_high', y: 'winter_low', label: 'Summer heat against winter cold' },
]

/* What the builder opens on, per theme (package 29, the owner's ruling on
 * NEEDS-DECISION #64). It used to open on the same two HOUSING metrics
 * everywhere, so a visitor who reached Weather and scrolled was handed a
 * pre-selected question about apartment prices.
 *
 * Every pair below is drawn from that theme's OWN metrics, so no theme opens
 * on someone else's subject. They are starting points, not recommendations —
 * the sub-line above the presets already says so, and the first thing the
 * visitor changes replaces them for the rest of the session.
 */
const SCATTER_DEFAULTS: Record<ThemeKey, { x: string; y: string }> = {
  // What you earn against what is actually left over.
  money: { x: 'salary_gross', y: 'savings' },
  // The two halves of the legal road: residency, then a passport.
  visa: { x: 'pr_years', y: 'citizenship_years' },
  // Absolute size of the market against how concentrated it is.
  jobs: { x: 'ict_specialists', y: 'ict_share' },
  // Unchanged: this pair was always the housing question, and belongs here.
  housing: { x: 'apt_m2', y: 'years_to_home' },
  // Who already moved, against how many came from one particular country.
  people: { x: 'foreign_born', y: 'iranian_born' },
  // Whether the places that report being happiest also look after you.
  life: { x: 'happiness_rank', y: 'healthcare' },
  // The theme's own framing: the question is February, not the mean.
  climate: { x: 'summer_high', y: 'winter_low' },
}

interface Point {
  name: string
  cc: string
  x: number
  y: number
  /** The site flagged this city's savings-derived figure as unreadable-precision. */
  offX: boolean
  offY: boolean
  [k: string]: unknown
}

/** "lower is better" where that is not obvious from the metric's name. Nothing
 *  is reordered — an axis that silently inverts is its own trap. */
const betterHint = (d: 'higher_better' | 'lower_better' | 'neutral') =>
  d === 'lower_better' ? '  (lower is better)' : d === 'higher_better' ? '  (higher is better)' : ''

/** Round a range outward to something a reader can name, and give it ticks.
 *  `floor` is a hard lower bound for metrics where values below it cannot
 *  exist — there is no rank #0. */
function axis(values: number[], floor?: number): { min: number; max: number; ticks: number[]; step: number } {
  const lo = floor != null ? Math.max(floor, Math.min(...values)) : Math.min(...values)
  const hi = Math.max(...values)
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo === hi) {
    return { min: lo - 1, max: hi + 1, ticks: [lo], step: 1 }
  }
  const span = hi - lo
  const step = Math.pow(10, Math.floor(Math.log10(span / 4)))
  const nice = [1, 2, 2.5, 5, 10].map((m) => m * step).find((s) => span / s <= 5) ?? step * 10
  let min = Math.floor(lo / nice) * nice
  if (floor != null && min < floor) min = floor
  const max = Math.ceil(hi / nice) * nice
  const ticks: number[] = []
  for (let v = min; v <= max + nice / 2; v += nice) ticks.push(Number(v.toFixed(6)))
  return { min, max, ticks, step: nice }
}

export function ScatterBuilder({ theme }: { theme: ThemeKey }) {
  const data = useData()
  /* #9 — the axes go in the address, and the null state has to survive it.
   * "Not chosen" is not the same as "chose the theme's default": an absent key
   * follows the theme as the visitor switches themes, and a present one keeps
   * what they picked. The theme chips carry sx/sy so the second half of that
   * still holds now the pair lives in the address rather than in state.
   *
   * Each axis is written and read on its OWN. Writing the pair together put
   * the other axis's DEFAULT into the address the moment a reader touched
   * either one — `?sx=happiness_rank&sy=savings` from a single change, with
   * `sy` a value nobody chose — which is the rule in urlState.ts's own header
   * turned inside out. An unknown key falls back to the theme's default for
   * that axis alone, so a link outliving one renamed metric still carries the
   * axis it can still honour. */
  const params = useSearchParams()[0]
  const patch = useUrlPatch()
  const known = (k: string | null): k is string => !!k && METRIC_BY_KEY.has(k)
  const sx = params.get('sx')
  const sy = params.get('sy')
  /* Each axis falls back on its OWN merits. Requiring both to be known threw
   * away a perfectly good axis whenever the other one had been renamed, which
   * is the opposite of degrading gracefully — the link would lose the half it
   * could still honour. */
  const xKey = known(sx) ? sx : SCATTER_DEFAULTS[theme].x
  const yKey = known(sy) ? sy : SCATTER_DEFAULTS[theme].y
  const setXKey = (k: string) => patch({ sx: k })
  const setYKey = (k: string) => patch({ sy: k })
  const [hover, setHover] = useState<Point | null>(null)

  const xM = METRIC_BY_KEY.get(xKey)
  const yM = METRIC_BY_KEY.get(yKey)

  const points = useMemo<Point[]>(() => {
    if (!xM || !yM) return []
    // Instability is a property of the city's savings figure, so it only lands
    // on an axis carrying a savings-derived metric.
    const xRisky = UNSTABLE_METRIC_KEYS.has(xKey)
    const yRisky = UNSTABLE_METRIC_KEYS.has(yKey)
    return data.cities
      .map((c) => {
        const k = data.countryById.get(c.country)
        const shaky = (xRisky || yRisky) && stabilityOf(c, 'mid') === 'unstable'
        return {
          name: c.name, cc: c.country,
          x: xM.value(c, k, 'mid'), y: yM.value(c, k, 'mid'),
          offX: shaky && xRisky, offY: shaky && yRisky,
        }
      })
      .filter((p): p is Point => p.x != null && p.y != null)
  }, [data, xM, yM, xKey, yKey])

  const dropped = data.cities.length - points.length
  const offscale = points.filter((p) => p.offX || p.offY)
  const inScale = points.filter((p) => !p.offX && !p.offY)

  /* How many DISTINCT places the plotted cities occupy, and whether every
   * city of a country lands on one of them.
   *
   * Four themes — visa, jobs, people, life — record every one of their
   * metrics per COUNTRY, not per city (`registry.ts`: their `value` functions
   * ignore the city argument). So any pair drawn from those themes puts all
   * thirty US cities on a single point. The data is real and the placement is
   * honest, but "every city is placed by its real numbers" reads as a cloud
   * of 73, and package 29's adversarial review measured what it actually is:
   * 70 markers at 9 positions on visa, 73 at 15 on life.
   *
   * Borrowing a money metric to spread them would be the very thing this
   * package removed — a theme opening on someone else's subject. So the
   * chart keeps the theme's own figures and says what they are. */
  const distinctPlaces = new Set(inScale.map((p) => `${p.x.toFixed(4)},${p.y.toFixed(4)}`)).size
  const byCountry = new Map<string, Set<string>>()
  for (const p of inScale) {
    const seen = byCountry.get(p.cc) ?? new Set<string>()
    seen.add(`${p.x.toFixed(4)},${p.y.toFixed(4)}`)
    byCountry.set(p.cc, seen)
  }
  const nationalFigures = inScale.length > distinctPlaces
    && [...byCountry.values()].every((places) => places.size === 1)
  // A domain needs at least something to describe; if every point is flagged,
  // fall back to all of them rather than drawing an empty axis.
  const scaleFrom = inScale.length >= 2 ? inScale : points

  const W = 720
  const H = 340
  const PL = 64
  const PR = 18
  const PT = 12
  const PB = 40
  const BAND = 30
  const anyOffY = offscale.some((p) => p.offY)
  const anyOffX = offscale.some((p) => p.offX)
  const plotTop = PT + (anyOffY ? BAND : 0)
  const plotRight = W - PR - (anyOffX ? BAND : 0)

  const ax = useMemo(() => axis(scaleFrom.map((p) => p.x), xM?.axisFloor), [scaleFrom, xM])
  const ay = useMemo(() => axis(scaleFrom.map((p) => p.y), yM?.axisFloor), [scaleFrom, yM])
  const X = (v: number) => PL + ((v - ax.min) / (ax.max - ax.min || 1)) * (plotRight - PL)
  const Y = (v: number) => H - PB - ((v - ay.min) / (ay.max - ay.min || 1)) * (H - plotTop - PB)

  const xFmt = xM ? tickFormatFor(xM) : (v: number) => String(v)
  const yFmt = yM ? tickFormatFor(yM) : (v: number) => String(v)
  const xTick = (v: number) => xFmt(v, ax.step)
  const yTick = (v: number) => yFmt(v, ay.step)

  // The same assertion the chart kit runs, on the one chart that builds its own
  // axes: loud in development, once and quiet in production. This is what
  // catches a formatter whose precision does not survive its own tick spacing.
  assertInjectiveTicks('x', ax.ticks.map((v) => [v, xTick(v)] as [number, string]),
    `scatter: ${xM?.label ?? ''} across`)
  assertInjectiveTicks('y', ay.ticks.map((v) => [v, yTick(v)] as [number, string]),
    `scatter: ${yM?.label ?? ''} up`)

  /** Where a point is drawn: its real position on any axis that can hold it,
   *  and the band on any axis that cannot. */
  const place = (p: Point) => ({
    cx: p.offX ? plotRight + BAND / 2 : X(p.x),
    cy: p.offY ? plotTop - BAND / 2 : Y(p.y),
  })

  const csvRows = points.map((p) => ({
    city: p.name, country: p.cc,
    [xM?.label ?? 'x']: p.x, [yM?.label ?? 'y']: p.y,
    precision_flag: p.offX || p.offY ? 'below the rounding on its own inputs' : '',
  }))

  return (
    <div className="panel">
      <h2>Ask your own question</h2>
      <div className="sub">
        Pick any two things and every city is placed by its real numbers. Presets are examples, not
        recommendations.
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '10px 0 12px' }}>
        {SCATTER_PRESETS.map((p) => (
          <button key={p.label} className="pill"
            aria-pressed={xKey === p.x && yKey === p.y}
            onClick={() => patch({ sx: p.x, sy: p.y })}>
            {p.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
        <MetricSelect label="across" value={xKey} onChange={setXKey} />
        <MetricSelect label="up" value={yKey} onChange={setYKey} />
      </div>

      <div className="chart">
        <svg viewBox={`0 0 ${W} ${H}`} role="img"
          aria-label={`${points.length} cities placed by ${xM?.label ?? ''} across and ${yM?.label ?? ''} up`
            + (offscale.length ? `. ${offscale.length} in an off-scale band: ${offscale.map((p) => p.name).join(', ')}` : '')}>
          {ay.ticks.map((v) => (
            <g key={`y${v}`}>
              <line x1={PL} x2={plotRight} y1={Y(v)} y2={Y(v)} className="gridline" />
              <text x={PL - 7} y={Y(v) + 3} fontSize="10" fill="var(--ink-3)" textAnchor="end">{yTick(v)}</text>
            </g>
          ))}
          {ax.ticks.map((v) => (
            <g key={`x${v}`}>
              <line y1={plotTop} y2={H - PB} x1={X(v)} x2={X(v)} className="gridline" />
              <text x={X(v)} y={H - PB + 15} fontSize="10" fill="var(--ink-3)" textAnchor="middle">{xTick(v)}</text>
            </g>
          ))}
          {/* Which way is better, said out loud. Rank metrics are the reason:
              #1 is best and sits at the axis minimum, so a rising axis reads
              backwards unless it tells you. */}
          <text x={plotRight} y={H - 6} fontSize="10" fill="var(--ink-3)" textAnchor="end">
            {xM?.label} →{xM ? betterHint(xM.direction) : ''}
          </text>
          <text x={12} y={plotTop + 4} fontSize="10" fill="var(--ink-3)"
            transform={`rotate(-90 12 ${plotTop + 4})`} textAnchor="end">
            {yM?.label} ↑{yM ? betterHint(yM.direction) : ''}
          </text>

          {/* The off-scale band: outside the numbers, inside the chart. */}
          {anyOffY && (
            <>
              <line x1={PL} x2={plotRight} y1={plotTop} y2={plotTop}
                stroke="var(--warn)" strokeDasharray="3 3" opacity="0.55" />
              <text x={PL} y={plotTop - BAND + 11} style={{ fontSize: 'var(--text-2xs)' }} fill="var(--warn)">off this scale ↑</text>
            </>
          )}
          {anyOffX && (
            <>
              <line x1={plotRight} x2={plotRight} y1={plotTop} y2={H - PB}
                stroke="var(--warn)" strokeDasharray="3 3" opacity="0.55" />
              {/* At the TOP of its own band, the way "off this scale ↑" sits at
                * the top of the horizontal one. It used to sit on the x-axis
                * tick row at y = H - PB + 15, starting 4 units right of
                * plotRight — where the last tick label is CENTRED on plotRight
                * and therefore printed through it: 291px² of overlap at 1440,
                * measured, before this package touched the size. Raising it to
                * the floor made that worse rather than better, which is the
                * opposite of what #79 is for. */}
              <text x={plotRight + 4} y={plotTop + 11} style={{ fontSize: 'var(--text-2xs)' }} fill="var(--warn)">off →</text>
            </>
          )}

          {/* An off-scale point is a DIAMOND, not a differently-coloured circle
            * (NEEDS-DECISION #82, package 44). It used to be told apart from the
            * 29 country colours by hue alone, and the measured distance from the
            * nearest of them is dE 6.4-8.8 — close enough that "is that dot a
            * warning or is it Portugal?" is a real question, and unanswerable
            * for a reader who cannot separate those hues at all. Shape needs no
            * hue: it survives greyscale, every colour-vision deficiency, and a
            * bad screen. The --warn fill stays; it is now the second channel
            * rather than the only one.
            *
            * Half-diagonal 7 against radius 5.5 so the two carry the same ink:
            * a diamond is 2r², a circle is πr², so equal area puts the diamond
            * at 5.5 x sqrt(pi/2) = 6.9. */}
          {points.map((p) => {
            const { cx, cy } = place(p)
            const off = p.offX || p.offY
            const title = `${p.name} — ${xM?.label}: ${xM?.format(p.x)} · ${yM?.label}: ${yM?.format(p.y)}`
              + (off ? ' — off this scale: smaller than the rounding on its own inputs' : '')
            const shared = {
              'data-city': p.name,
              stroke: 'var(--surface)',
              strokeWidth: 1.5,
              onPointerOver: () => setHover(p),
              onPointerOut: () => setHover(null),
            }
            if (off) {
              const r = 7
              return (
                <polygon key={p.name} data-offscale=""
                  points={`${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`}
                  fill="var(--warn)" {...shared}>
                  <title>{title}</title>
                </polygon>
              )
            }
            return (
              <circle key={p.name} cx={cx} cy={cy} r={5.5} fill={`var(--c-${p.cc})`} {...shared}>
                <title>{title}</title>
              </circle>
            )
          })}
        </svg>
        {hover && (
          <div className="readout" style={{ opacity: 1, left: `${(place(hover).cx / W) * 100}%`, top: 8 }}>
            <b>{hover.name}</b>
            {/* A point in the band is exactly the case where the reader needs
                the real figure, so the clamped reading ("100+ yrs") is given
                the precise value beside it rather than instead of it. */}
            <div className="r">
              <span>{xM?.label}</span>
              <b>{xM?.format(hover.x)}{hover.offX && ` — exactly ${xTick(hover.x)}`}</b>
            </div>
            <div className="r">
              <span>{yM?.label}</span>
              <b>{yM?.format(hover.y)}{hover.offY && ` — exactly ${yTick(hover.y)}`}</b>
            </div>
            {(hover.offX || hover.offY) && (
              <div style={{ marginTop: 5, color: 'var(--warn)', maxWidth: 210, whiteSpace: 'normal' }}>
                Off this scale — what this city saves in a year is smaller than the rounding on its
                own rent figure.
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: 8, fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
        <span>{inScale.length === 0
          ? `No city has both ${xM?.label ?? 'these'} and ${yM?.label ?? 'these'} on record — nothing to place, rather than an empty grid meaning nothing.`
          : `${inScale.length} of ${data.cities.length} cities plotted.`}</span>
        {nationalFigures && (
          <span className="chip chip-note">
            at {distinctPlaces} points — both of these are national figures, so every city in a
            country sits on the same one
          </span>
        )}
        {offscale.length > 0 && (
          <span className="chip chip-risk">
            {offscale.length} {offscale.length === 1 ? 'city is' : 'cities are'} off this scale — what
            they save in a year is smaller than the rounding on their own rent. Their real numbers
            are in the readout and the CSV.
          </span>
        )}
        {dropped > 0 && (
          <span className="chip chip-quiet">
            {dropped} {dropped === 1 ? 'city has' : 'cities have'} no value for one of these two — they are
            left out of this view, not deleted
          </span>
        )}
        <button className="pill" style={{ marginLeft: 'auto' }}
          onClick={() => downloadCsv('compass-scatter.csv', csvRows)}>⤓ CSV</button>
      </div>
    </div>
  )
}

function MetricSelect({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', display: 'flex', gap: 6, alignItems: 'center' }}>
      {label} →
      <select value={value} onChange={(e) => onChange(e.target.value)}
        style={{
          border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink-1)',
          borderRadius: 'var(--radius-sm)', padding: '6px 9px', fontSize: 'var(--text-2xs)',
        }}>
        {THEMES.map((t) => {
          // Categorical metrics are absent by construction, not filtered in the UI.
          const options = AXIS_METRICS.filter((m) => m.theme === t.key)
          if (!options.length) return null
          return (
            <optgroup key={t.key} label={t.label}>
              {options.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
            </optgroup>
          )
        })}
      </select>
    </label>
  )
}

export { METRICS }
