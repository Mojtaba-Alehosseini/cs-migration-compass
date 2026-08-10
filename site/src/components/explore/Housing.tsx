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
import type { ChartCfg, ChartHandle } from '../chart/engine'
import { Picker, ChartFoot, ChartTable, Gap, ThemeSkeleton, type HeroStat } from './Controls'
import { useAsync } from './useAsync'
import { loadHousing, type HousingData, type Pair } from '../../data/explore'

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

/** Where a country publishes true city-level history, this is it — never a
 *  country trend wearing a city's name. */
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
        Three countries publish true city-level history. These are the real
        series — never a country trend applied to a city.
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
          <div className="rh"><b>Toronto · Vancouver</b>
            <span>{mult(data.teranet.toronto)} · {mult(data.teranet.vancouver)} since 1998</span></div>
          {spark([
            { pts: data.teranet.toronto, color: cc('CA') },
            { pts: data.teranet.vancouver, color: cc('CA'), dash: true },
          ], 1998, 2026, 'Toronto and Vancouver house price index since 1998')}
          <div className="unit">Teranet–National Bank repeat-sales index</div>
        </div>
        <div className="ribbon">
          <div className="rh"><b>London</b>
            <span>{data.london.length ? `${gbp(data.london[0]![1])} → ${gbp(last(data.london)[1])} since 1968` : 'no data'}</span></div>
          {spark([{ pts: data.london, color: cc('GB') }], 1968, 2026, 'London average sale price since 1968')}
          <div className="unit">HM Land Registry average sale price — in pounds, deliberately</div>
        </div>
      </div>
      <ChartFoot>
        <span className="chip chip-ok">● FHFA · Teranet · HM Land Registry</span>
        <span className="chip chip-quiet">London stays in pounds — one 2026 FX rate across 1968→2026 would lie</span>
      </ChartFoot>
    </div>
  )
}
