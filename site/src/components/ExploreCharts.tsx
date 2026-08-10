/* The scatter builder — any metric against any other, 73 cities placed by their
 * real numbers.
 *
 * Behaviour is unchanged; only the renderer is. It used to draw through
 * Recharts, which cost 380 KB and rode along with Compare for one climate
 * overlay. This is the same picture in plain SVG: dots at real positions, the
 * country palette, a readout on hover, and an honest count of what could not be
 * placed.
 *
 * Presets are examples, never a default lens the site pushes.
 */

import { useMemo, useState } from 'react'
import { useData } from '../data/store'
import { THEMES, METRICS, METRIC_BY_KEY } from '../data/registry'
import { downloadCsv } from '../lib/export'

const SCATTER_PRESETS = [
  { x: 'apt_m2', y: 'years_to_home', label: 'Cheap city or impossible city?' },
  { x: 'total_monthly', y: 'salary_gross', label: 'Salary against what a month costs' },
  { x: 'happiness_rank', y: 'savings', label: 'Money against life' },
  { x: 'summer_high', y: 'winter_low', label: 'Summer heat against winter cold' },
]

interface Point { name: string; cc: string; x: number; y: number; [k: string]: unknown }

/** Round a range outward to something a reader can name, and give it ticks. */
function axis(values: number[]): { min: number; max: number; ticks: number[] } {
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo === hi) {
    return { min: lo - 1, max: hi + 1, ticks: [lo] }
  }
  const span = hi - lo
  const step = Math.pow(10, Math.floor(Math.log10(span / 4)))
  const nice = [1, 2, 2.5, 5, 10].map((m) => m * step).find((s) => span / s <= 5) ?? step * 10
  const min = Math.floor(lo / nice) * nice
  const max = Math.ceil(hi / nice) * nice
  const ticks: number[] = []
  for (let v = min; v <= max + nice / 2; v += nice) ticks.push(Number(v.toFixed(6)))
  return { min, max, ticks }
}

export function ScatterBuilder() {
  const data = useData()
  const [xKey, setXKey] = useState('apt_m2')
  const [yKey, setYKey] = useState('years_to_home')
  const [hover, setHover] = useState<Point | null>(null)

  const xM = METRIC_BY_KEY.get(xKey)
  const yM = METRIC_BY_KEY.get(yKey)

  const points = useMemo<Point[]>(() => {
    if (!xM || !yM) return []
    return data.cities
      .map((c) => {
        const k = data.countryById.get(c.country)
        return { name: c.name, cc: c.country, x: xM.value(c, k, 'mid'), y: yM.value(c, k, 'mid') }
      })
      .filter((p): p is Point => p.x != null && p.y != null)
  }, [data, xM, yM])

  const dropped = data.cities.length - points.length

  const W = 720
  const H = 340
  const PL = 64
  const PR = 18
  const PT = 12
  const PB = 40
  const ax = useMemo(() => axis(points.map((p) => p.x)), [points])
  const ay = useMemo(() => axis(points.map((p) => p.y)), [points])
  const X = (v: number) => PL + ((v - ax.min) / (ax.max - ax.min || 1)) * (W - PL - PR)
  const Y = (v: number) => H - PB - ((v - ay.min) / (ay.max - ay.min || 1)) * (H - PT - PB)

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
            onClick={() => { setXKey(p.x); setYKey(p.y) }}>
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
          aria-label={`${points.length} cities placed by ${xM?.label ?? ''} across and ${yM?.label ?? ''} up`}>
          {ay.ticks.map((v) => (
            <g key={`y${v}`}>
              <line x1={PL} x2={W - PR} y1={Y(v)} y2={Y(v)} className="gridline" />
              <text x={PL - 7} y={Y(v) + 3} fontSize="10" fill="var(--ink-3)" textAnchor="end">
                {yM ? yM.format(v) : v}
              </text>
            </g>
          ))}
          {ax.ticks.map((v) => (
            <g key={`x${v}`}>
              <line y1={PT} y2={H - PB} x1={X(v)} x2={X(v)} className="gridline" />
              <text x={X(v)} y={H - PB + 15} fontSize="10" fill="var(--ink-3)" textAnchor="middle">
                {xM ? xM.format(v) : v}
              </text>
            </g>
          ))}
          <text x={W - PR} y={H - 6} fontSize="10" fill="var(--ink-3)" textAnchor="end">{xM?.label} →</text>
          {points.map((p) => (
            <circle key={p.name} cx={X(p.x)} cy={Y(p.y)} r={5.5}
              fill={`var(--c-${p.cc})`} stroke="var(--surface)" strokeWidth={1.5}
              onPointerEnter={() => setHover(p)} onPointerLeave={() => setHover(null)}>
              <title>{`${p.name} — ${xM?.label}: ${xM?.format(p.x)} · ${yM?.label}: ${yM?.format(p.y)}`}</title>
            </circle>
          ))}
        </svg>
        {hover && (
          <div className="readout" style={{ opacity: 1, left: `${(X(hover.x) / W) * 100}%`, top: 8 }}>
            <b>{hover.name}</b>
            <div className="r"><span>{xM?.label}</span><b>{xM?.format(hover.x)}</b></div>
            <div className="r"><span>{yM?.label}</span><b>{yM?.format(hover.y)}</b></div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: 8, fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
        <span>{points.length} of {data.cities.length} cities plotted.</span>
        {dropped > 0 && (
          <span className="chip chip-quiet">
            {dropped} {dropped === 1 ? 'city has' : 'cities have'} no value for one of these two — they are
            left out of this view, not deleted
          </span>
        )}
        <button className="pill" style={{ marginLeft: 'auto' }}
          onClick={() => downloadCsv('compass-scatter.csv', points)}>⤓ CSV</button>
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
        {THEMES.map((t) => (
          <optgroup key={t.key} label={t.label}>
            {METRICS.filter((m) => m.theme === t.key).map((m) => (
              <option key={m.key} value={m.key}>{m.label}</option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  )
}
