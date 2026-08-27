/* Homes & rent — half a century of prices, and a handle that re-asks the
 * question.
 *
 * The base-year handle is the signature interaction of the whole site. Grab it
 * and every pickable country re-indexes to 100 at the year under your finger,
 * tracking 1:1 with zero added easing, while the sentence above the chart
 * rewrites itself. "How much harder has it got since I was born?" becomes one
 * gesture.
 *
 * That is why the chart updates through `track` rather than `morph`: a captured
 * pointer must keep its element for the whole drag, so nothing is torn down and
 * rebuilt between frames.
 */

import { useCallback, useMemo, useRef, useState } from 'react'
import { Chart } from '../chart/Chart'
import type { ChartCfg, ChartHandle, Series } from '../chart/engine'
import { Derived } from '../Derived'
import { PICK_COLORS } from '../../data/questions'
import { Picker, ChartFoot, ChartTable, Gap, ThemeSkeleton, type HeroStat } from './Controls'
import { useAsync } from './useAsync'
import { loadHousing, TERANET_CITY_IDS, type HousingData, type Pair, type TeranetCityId } from '../../data/explore'

const cc = (c: string) => `var(--c-${c})`
const last = <T,>(a: T[]) => a[a.length - 1]!
const at = (pts: Pair[], year: number) => pts.find((p) => p[0] === year) ?? pts[0]

export function housingHero(d: HousingData): HeroStat[] {
  const ca = d.bis.CA
  const ca90 = ca ? at(ca, 1990) : null
  const det = d.fhfa.detroit
  return [
    { value: ca && ca90 ? last(ca)[1] / ca90[1] : null, format: (v) => `×${v.toFixed(1)}`,
      label: 'Canadian real prices since 1990', source: 'BIS' },
    { value: d.london.length ? last(d.london)[1] : null, format: (v) => `£${Math.round(v / 1000)}k`,
      label: 'an average London sale today — from £4.7k in 1968', source: 'Land Registry' },
    { value: det?.length ? last(det)[1] / det[0]![1] : null, format: (v) => `×${v.toFixed(1)}`,
      label: 'Detroit since 1990 — the affordable outlier', source: 'FHFA' },
  ]
}

export function HousingTheme() {
  const { data, error } = useAsync(loadHousing, 'housing')
  if (error) {
    return <div className="panel s6"><p className="nodata">
      House-price history could not be loaded ({error}). Nothing is drawn rather than something approximate.
    </p></div>
  }
  if (!data) return <ThemeSkeleton panels={[['s6', 528], ['s4', 400], ['s2', 400]]} />
  return (
    <>
      <BisPanel data={data} />
      <TeranetPanel data={data} />
      <CityRibbons data={data} />
      <Gap title="Why no city rent history"
        where={<>Rule §2c of the build brief · <a href="#/data">Data page →</a></>}>
        <p>
          Nobody publishes it freely. Numbeo’s per-city archive renders client-side and its terms
          bar bulk use — verified, recorded. City pages will show <b>country trend × the city’s
          current rent</b>, labelled exactly that.
        </p>
      </Gap>
    </>
  )
}

function BisPanel({ data }: { data: HousingData }) {
  const [picks, setPicks] = useState(['CA', 'DE', 'GB'])
  const [base, setBase] = useState(1990)
  const [ready, setReady] = useState(false)
  const chart = useRef<ChartHandle | null>(null)
  const dragging = useRef(false)

  const cfg = useMemo<ChartCfg>(() => ({
    aria: `Real house prices since 1970, indexed to 100 in ${base}, ${picks.join(', ')}`,
    padT: 30,
    x: { min: 1970, max: 2026, ticks: [[1970, '1970'], [1985, '1985'], [2000, '2000'], [2015, '2015'], [2026, '2026']] },
    y: { min: 0, max: 620, ticks: [[100, '100'], [300, '×3'], [500, '×5']] },
    series: picks.flatMap((c) => {
      const raw = data.bis[c]
      if (!raw?.length) return []
      const b = at(raw, base)!
      return [{ key: c, label: c, color: cc(c), pts: raw.map(([y, v]) => [y, (v / b[1]) * 100] as Pair), hoverLabel: c }]
    }),
    fmtX: (v) => String(v),
    fmtV: (p) => `×${((p[1] ?? 0) / 100).toFixed(2)} vs ${base}`,
  }), [data, picks, base])

  const insight = picks
    .map((c) => {
      const raw = data.bis[c]
      if (!raw?.length) return ''
      return `${c} ×${(last(raw)[1] / at(raw, base)![1]).toFixed(1)}`
    })
    .filter(Boolean)
    .join(' · ')

  /** Pointer → year, 1:1. No easing, no rounding beyond the year itself: the
   *  handle must land exactly where the finger is. */
  const onMove = useCallback((e: React.PointerEvent<HTMLButtonElement>) => {
    if (!dragging.current) return
    const S = chart.current?.scaleState
    const svg = chart.current?.host.querySelector('svg')
    if (!S || !svg) return
    const r = svg.getBoundingClientRect()
    const mx = ((e.clientX - r.left) / r.width) * S.W
    const yr = Math.round(1970 + ((mx - S.PL) / (S.W - S.PL - S.PR)) * (2026 - 1970))
    const clamped = Math.max(1970, Math.min(2020, yr))
    if (clamped !== base) setBase(clamped)
  }, [base])

  // The handle is positioned from the chart's real scales, which only exist
  // once the engine has built. `ready` is what re-renders this at that moment.
  const S = ready ? chart.current?.scaleState : null
  const handleLeft = S ? `${(S.X(base) / S.W) * 100}%` : `${((base - 1970) / (2026 - 1970)) * 100}%`

  const csv = picks.flatMap((c) => (data.bis[c] ?? []).map(([y, v]) => ({ country: c, year: y, real_index: v })))

  return (
    <div className="panel s6">
      <h2>House prices, half a century of them</h2>
      <div className="sub">
        BIS real (inflation-adjusted) prices. <b>Grab the year handle</b> under the
        axis and drag: everything re-indexes to 100 at the year you hold — “how much harder has it
        got since I was born?” is one gesture. The answer rewrites itself above the chart.
      </div>
      <div className="crail">
        <span className="lbl">countries</span>
        <Picker label="Countries"
          items={Object.keys(data.bis).sort().map((c) => ({ k: c, cc: c, label: c }))}
          active={picks} onChange={setPicks} />
      </div>
      <p className="insight">
        Real prices since <b>{base}</b>: <b>{insight}</b> — grab the handle to move the start line.
      </p>
      <div style={{ position: 'relative', marginBottom: 18 }}>
        <Chart id="ex-bis" cfg={cfg} transition="track" handleRef={chart} onReady={() => setReady(true)} />
        <button
          className="baser"
          style={{ left: handleLeft }}
          // The accessible name has to start with the visible text ("since
          // 1990"), or a voice-control user saying what they can see cannot
          // address this control.
          aria-label={`since ${base} — base year. Drag, or use the arrow keys, to re-index every line to this year.`}
          onPointerDown={(e) => {
            dragging.current = true
            e.currentTarget.setPointerCapture(e.pointerId)
            e.preventDefault()
          }}
          onPointerMove={onMove}
          onPointerUp={() => { dragging.current = false }}
          onPointerCancel={() => { dragging.current = false }}
          onKeyDown={(e) => {
            const step = e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1
              : e.key === 'PageDown' ? -10 : e.key === 'PageUp' ? 10 : 0
            if (!step) return
            e.preventDefault()
            setBase((b) => Math.max(1970, Math.min(2020, b + step)))
          }}
        >
          {/* The space is markup, not styling: the accessible name has to
              contain the visible text, and "since1990" is not "since 1990". */}
          <small>since</small>{' '}<span>{base}</span>
        </button>
      </div>
      <ChartFoot csv={{ name: 'compass-bis-house-prices.csv', rows: csv }}>
        <span className="chip chip-ok">● Official · BIS residential property prices, 1970 →</span>
        <span className="chip chip-risk">no institutional housing forecast is live — IMF blocked, WB GEP unparseable</span>
      </ChartFoot>
      <ChartTable caption={`Real house prices, indexed to 100 in ${base} — the numbers behind this chart`}
        head={['Country', 'Year', `Index (${base} = 100)`]}
        rows={picks.flatMap((c) => {
          const raw = data.bis[c]
          if (!raw?.length) return []
          const b = at(raw, base)!
          return raw.filter((p) => p[0] % 10 === 0).map((p) => [c, p[0], ((p[1] / b[1]) * 100).toFixed(0)])
        })} />
    </div>
  )
}

const TERANET_LABEL: Record<TeranetCityId, string> = {
  toronto: 'Toronto', vancouver: 'Vancouver', montreal: 'Montreal',
  ottawa: 'Ottawa', calgary: 'Calgary', halifax: 'Halifax',
}
const teranetColor = (id: TeranetCityId) => PICK_COLORS[TERANET_CITY_IDS.indexOf(id)] ?? 'var(--pick-rest)'

/** NEEDS-DECISION #43, closed package 21 — the recovered signal, not the
 *  raw-only "direction only" disclosure package 16 shipped.
 *
 *  Toronto's month-over-month lag-1 autocorrelation (-0.43) matches the
 *  theoretical -0.5 signature of a smooth trend plus independent additive
 *  noise once differenced -- meaning the trend is recoverable with a proper
 *  noise model, not just discardable, which is further than package 16's own
 *  "no single value, monthly or annual" conclusion needed to go.
 *  scripts/derive_teranet_smoothed.py fits a Kalman-smoothed local linear
 *  trend per city and validates it against OECD's own independent Canadian
 *  house-price index (quarter-over-quarter CHANGES, not levels -- a levels-
 *  based first version of that validation was proven unsafe by direct
 *  adversarial testing, see that script's own module docstring) before a
 *  city earns a band here at all. All 6 Teranet cities passed this run.
 *
 *  What survives is a MONTHLY trend with an honest 95% band, not a precise
 *  level: even Toronto's best case recovers only 0.07% of month-to-month
 *  RAW variance as genuine signal -- the band you see is wide because the
 *  noise really is that large, and the chart does not pretend otherwise. */
function TeranetPanel({ data }: { data: HousingData }) {
  const available = TERANET_CITY_IDS.filter((c) => data.teranet[c])
  const [picks, setPicks] = useState<TeranetCityId[]>(
    (['toronto', 'vancouver'] as const).filter((c) => available.includes(c)),
  )

  const cfg = useMemo<ChartCfg>(() => {
    const series: Series[] = []
    const bands: NonNullable<ChartCfg['bands']> = []
    let xMin = Infinity
    let xMax = -Infinity
    let yMin = Infinity
    let yMax = -Infinity
    for (const c of picks) {
      const city = data.teranet[c]
      if (!city) continue
      const color = teranetColor(c)
      series.push({ key: `${c}_mid`, label: TERANET_LABEL[c], color, pts: city.smoothed,
        hoverLabel: `${TERANET_LABEL[c]} (smoothed)` })
      series.push({ key: `${c}_hi`, color, mode: 'lo', pts: city.hi95, noRead: true })
      series.push({ key: `${c}_lo`, color, mode: 'lo', pts: city.lo95, noRead: true })
      bands.push({ hi: `${c}_hi`, lo: `${c}_lo`, color })
      for (const [x, v] of city.hi95) { if (x < xMin) xMin = x; if (x > xMax) xMax = x; if (v! > yMax) yMax = v! }
      for (const [, v] of city.lo95) { if (v! < yMin) yMin = v! }
    }
    if (!Number.isFinite(xMin)) { xMin = 1998; xMax = 2026; yMin = 0; yMax = 400 }
    const x0 = Math.floor(xMin)
    const x1 = Math.ceil(xMax)
    const pad = (yMax - yMin) * 0.05 || 10
    const yTickStep = Math.round((yMax - yMin) / 4 / 25) * 25 || 50
    const yTicks: [number, string][] = []
    for (let v = Math.ceil((yMin - pad) / yTickStep) * yTickStep; v <= yMax + pad; v += yTickStep) {
      yTicks.push([v, String(v)])
    }
    const xTicks: [number, string][] = []
    const xStep = Math.max(4, Math.round((x1 - x0) / 6 / 4) * 4)
    for (let y = Math.ceil(x0 / xStep) * xStep; y <= x1; y += xStep) xTicks.push([y, String(y)])
    return {
      aria: `Kalman-smoothed Teranet house price index with 95% band, ${picks.map((c) => TERANET_LABEL[c]).join(', ')}`,
      padT: 30,
      x: { min: x0, max: x1, ticks: xTicks },
      y: { min: yMin - pad, max: yMax + pad, ticks: yTicks },
      series,
      bands,
      fmtX: (v) => String(Math.round(v)),
      fmtV: (p, s) => `${(p[1] ?? 0).toFixed(1)}${s.key.endsWith('_hi') || s.key.endsWith('_lo') ? ' (95% band edge)' : ''}`,
    }
  }, [data, picks])

  const csv = picks.flatMap((c) => {
    const city = data.teranet[c]
    if (!city) return []
    const rawByX = new Map(city.raw.map(([x, v]) => [x, v]))
    return city.smoothed.map(([x, smoothed], i) => ({
      city: TERANET_LABEL[c],
      year_frac: x.toFixed(4),
      raw_index: rawByX.get(x) ?? '',
      smoothed_index: smoothed.toFixed(2),
      lo95: city.lo95[i]?.[1]?.toFixed(2) ?? '',
      hi95: city.hi95[i]?.[1]?.toFixed(2) ?? '',
    }))
  })

  return (
    <div className="panel s6">
      <h2>Toronto to Halifax, the trend recovered from the noise</h2>
      <div className="sub">
        Teranet's raw monthly index carries noise larger than the trend it describes — package 16's
        own finding. What that finding did not settle is whether the trend is <i>recoverable</i>. A
        state-space model (Kalman smoother) fit per city, then checked against OECD's own
        independent Canadian index, says yes for all six: the smoothed line below is the recovered
        trend, the shaded band its own honest uncertainty — wide, because the underlying noise
        really is that large.
      </div>
      <div className="crail">
        <span className="lbl">cities</span>
        <Picker label="Teranet cities"
          items={TERANET_CITY_IDS.map((c) => ({ k: c, label: TERANET_LABEL[c] }))}
          active={picks} onChange={(update) => setPicks(update(picks) as TeranetCityId[])} />
      </div>
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {picks.map((c) => {
          const city = data.teranet[c]
          if (!city) return null
          const trend = city.trendPctPerYear
          return (
            <p key={c} className="insight" style={{ margin: 0 }}>
              <b style={{ color: teranetColor(c) }}>{TERANET_LABEL[c]}</b>{': '}
              <Derived
                chain={[
                  { op: 'raw', detail: `Teranet's own raw monthly index — noisy: only `
                    + `${city.signalSharePct.toFixed(2)}% of month-to-month movement is genuine trend, `
                    + `the rest is per-observation noise this pipeline does not control.` },
                  { op: 'smooth', detail: 'Kalman-smoothed (state-space local linear trend, '
                    + 'statsmodels.UnobservedComponents) — noise and trend-innovation variances '
                    + 'estimated from the data by MLE, never assumed.' },
                  { op: 'validate', detail: `Validated against OECD's independent Canadian house-price `
                    + `index: quarter-over-quarter CHANGE correlation ${city.validation.corrDiff?.toFixed(3) ?? '—'} `
                    + `over ${city.validation.nQuarters} quarters. A Monte Carlo null test (pure noise, `
                    + `same length and scale, run through the identical pipeline) puts the chance of this `
                    + `happening by noise alone at p=${city.validation.pValue?.toFixed(3) ?? '—'} — clears the `
                    + `5% bar this required to earn a band at all.` },
                ]}
              >
                {trend != null ? `≈${trend >= 0 ? '+' : ''}${trend.toFixed(1)}%/yr` : 'trend unavailable'}, band shown
              </Derived>
            </p>
          )
        })}
      </div>
      <div style={{ marginTop: 10 }}>
        <Chart id="ex-teranet" cfg={cfg} transition="morph" />
      </div>
      <ChartFoot csv={{ name: 'compass-teranet-smoothed.csv', rows: csv }}>
        <span className="chip chip-ok">● Teranet–National Bank, smoothed and OECD-validated</span>
        <span className="chip chip-quiet">Raw monthly values in the CSV — never plotted directly, the noise they carry is the whole reason this exists</span>
      </ChartFoot>
    </div>
  )
}

/** Where a country publishes true city-level history, this is it — never a
 *  country trend wearing a city's name. Toronto/Vancouver (and the rest of
 *  Teranet's cities) moved out to their own panel, TeranetPanel above —
 *  package 21 recovered a real monthly trend from them, which this file's
 *  own hand-rolled annual sparkline was never built to show. */
function CityRibbons({ data }: { data: HousingData }) {
  const mult = (p: Pair[]) => (p.length ? `×${(last(p)[1] / p[0]![1]).toFixed(1)}` : 'no data')
  const gbp = (v: number) => `£${Math.round(v / 1000)}k`

  const spark = (lines: { pts: Pair[]; color: string; dash?: boolean }[], x0: number, x1: number, title: string) => {
    const all = lines.flatMap((l) => l.pts.map((p) => p[1]))
    if (!all.length) return null
    const mn = Math.min(...all)
    const mx = Math.max(...all)
    const X = (x: number) => 4 + ((x - x0) / (x1 - x0)) * 192
    const Y = (v: number) => 50 - ((v - mn) / (mx - mn || 1)) * 44
    return (
      <svg viewBox="0 0 200 56" role="img" aria-label={title}>
        {lines.map((l, i) => (
          <path key={i} d={l.pts.map((p, j) => (j ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join('')}
            fill="none" stroke={l.color} strokeWidth="1.8"
            {...(l.dash ? { strokeDasharray: '3 3', opacity: 0.8 } : {})} />
        ))}
      </svg>
    )
  }

  return (
    <div className="panel s4">
      <h2>Real city series, where they exist</h2>
      <div className="sub">
        Two more countries publish true city-level history, beside the recovered Teranet trend
        above. These are the real series — never a country trend applied to a city.
      </div>
      <div className="ribbons">
        <div className="ribbon">
          <div className="rh"><b>Detroit · SF Bay</b>
            <span>{mult(data.fhfa.detroit)} · {mult(data.fhfa.sf_bay_area)} since 1990</span></div>
          {spark([
            { pts: data.fhfa.detroit, color: cc('US') },
            { pts: data.fhfa.sf_bay_area, color: cc('US'), dash: true },
          ], 1990, 2026, 'Detroit and SF Bay house price index since 1990')}
          <div className="unit">FHFA all-transactions index · solid Detroit, dashed SF Bay</div>
        </div>
        <div className="ribbon">
          <div className="rh"><b>London</b>
            <span>{data.london.length ? `${gbp(data.london[0]![1])} → ${gbp(last(data.london)[1])} since 1968` : 'no data'}</span></div>
          {spark([{ pts: data.london, color: cc('GB') }], 1968, 2026, 'London average sale price since 1968')}
          <div className="unit">HM Land Registry average sale price — in pounds, deliberately</div>
        </div>
      </div>
      <ChartFoot>
        <span className="chip chip-ok">● FHFA · HM Land Registry</span>
        <span className="chip chip-quiet">London stays in pounds — one 2026 FX rate across 1968→2026 would lie</span>
      </ChartFoot>
    </div>
  )
}
