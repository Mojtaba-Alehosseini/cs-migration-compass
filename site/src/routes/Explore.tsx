/* Explore — per-theme deep dives.
 *
 * Two things here carry the most weight:
 *   1. History charts overlay a REAL institutional forecast (solid, with an
 *      attribution chip) alongside our naive extrapolation (hatched band,
 *      labelled "not a forecast"). They are never averaged.
 *   2. The scatter builder lets any metric meet any other. Presets exist as
 *      examples, never as a default lens the site pushes. */

import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts'
import { Flag } from '../components/Flag'
import { useData, loadHistory } from '../data/store'
import { THEMES, METRICS, METRIC_BY_KEY, type ThemeKey } from '../data/registry'
import { naiveExtrapolate } from '../data/compute'
import { moneyShort, num } from '../data/format'
import { downloadCsv } from '../lib/export'

const SCATTER_PRESETS = [
  { x: 'apt_m2', y: 'years_to_home', label: 'Cheap city or impossible city?' },
  { x: 'total_monthly', y: 'salary_gross', label: 'Salary against what a month costs' },
  { x: 'happiness_rank', y: 'savings', label: 'Money against life' },
  { x: 'summer_high', y: 'winter_low', label: 'Summer heat against winter cold' },
]

export function Explore() {
  const { theme } = useParams()
  const active = (THEMES.find((t) => t.key === theme)?.key ?? 'money') as ThemeKey

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <div className="kicker">Explore</div>
      <h1 style={{ fontSize: 'var(--text-xl)', marginTop: 4 }}>
        {THEMES.find((t) => t.key === active)?.label}
      </h1>
      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', margin: '6px 0 14px' }}>
        {THEMES.find((t) => t.key === active)?.blurb}
      </p>

      <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginBottom: 16 }}>
        {THEMES.map((t) => (
          <Link key={t.key} to={`/explore/${t.key}`} className="pill"
            aria-current={t.key === active ? 'page' : undefined}
            style={{
              textDecoration: 'none',
              background: t.key === active ? 'var(--ink-1)' : 'var(--surface)',
              color: t.key === active ? 'var(--paper)' : 'var(--ink-2)',
              borderColor: t.key === active ? 'var(--ink-1)' : 'var(--line)',
            }}>
            {t.label}
          </Link>
        ))}
      </div>

      {active === 'money' && <EconomyHistory />}
      <ScatterBuilder />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* History + institutional forecast overlay                            */
/* ------------------------------------------------------------------ */

interface Point { year: number; [k: string]: number | null }

function EconomyHistory() {
  const [series, setSeries] = useState<Point[] | null>(null)
  const [chip, setChip] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const picks = ['DE', 'CA', 'NL']

  useEffect(() => {
    let alive = true
    Promise.all([
      loadHistory<Record<string, Record<string, { year: number; value: number }[]>>>('world_bank'),
      loadHistory<Record<string, Record<string, { year: number; value: number; is_projection: boolean }[]>>>(
        'oecd_economic_outlook',
      ),
    ])
      .then(([wb, eo]) => {
        if (!alive) return
        const byYear = new Map<number, Point>()
        const put = (year: number, key: string, value: number) => {
          const row = byYear.get(year) ?? { year }
          row[key] = value
          byYear.set(year, row)
        }

        for (const cc of picks) {
          const hist = wb.data[cc]?.gdp_per_capita_usd ?? []
          for (const p of hist) put(p.year, `${cc}_actual`, p.value)

          // Our own extrapolation — deliberately naive, drawn hatched.
          const ext = naiveExtrapolate(hist.map((p) => ({ year: p.year, value: p.value })), 2031)
          for (const p of ext) put(p.year, `${cc}_naive`, p.value)

          // The institutional forecast, kept entirely separate.
          const growth = eo.data[cc]?.real_gdp_growth_pct ?? []
          const last = hist[hist.length - 1]
          if (last) {
            let v = last.value
            for (const g of growth.filter((g) => g.is_projection)) {
              v = v * (1 + g.value / 100)
              put(g.year, `${cc}_oecd`, v)
            }
            put(last.year, `${cc}_oecd`, last.value)
          }
        }
        setSeries([...byYear.values()].sort((a, b) => a.year - b.year))
        setChip(String(eo.meta.attribution_chip ?? 'OECD Economic Outlook'))
        setNote(String(eo.meta.projection_rule ?? ''))
      })
      .catch(() => { if (alive) setSeries([]) })
    return () => { alive = false }
  }, [])

  if (!series) return <div className="panel"><span className="kicker">Loading history…</span></div>
  if (series.length === 0) {
    return <div className="panel"><p className="nodata">History could not be loaded.</p></div>
  }

  return (
    <div className="panel" style={{ marginBottom: 12 }}>
      <h3>Income per person, and where two institutions think it goes</h3>
      <div className="sub">
        GDP per person since 1990. The solid extension is a real forecast; the dashed one is ours and
        is not a forecast. They are shown side by side and never averaged.
      </div>

      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={series} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="year" tick={{ fontSize: 11, fill: 'var(--ink-3)' }} stroke="var(--line)" />
            <YAxis tickFormatter={(v) => moneyShort(v)} tick={{ fontSize: 11, fill: 'var(--ink-3)' }} stroke="var(--line)" width={54} />
            <Tooltip
              contentStyle={{
                background: 'var(--ink-1)', border: 'none', borderRadius: 9,
                color: 'var(--paper)', fontSize: 12,
              }}
              formatter={(v, name) => [moneyShort(typeof v === 'number' ? v : null), String(name)]}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {picks.map((cc) => [
              <Line key={`${cc}a`} type="monotone" dataKey={`${cc}_actual`} name={`${cc} — actual`}
                stroke={`var(--c-${cc})`} strokeWidth={2.2} dot={false} connectNulls />,
              <Line key={`${cc}o`} type="monotone" dataKey={`${cc}_oecd`} name={`${cc} — ${chip}`}
                stroke={`var(--c-${cc})`} strokeWidth={2.6} dot={false} connectNulls />,
              <Line key={`${cc}n`} type="monotone" dataKey={`${cc}_naive`} name={`${cc} — naive extrapolation`}
                stroke={`var(--c-${cc})`} strokeWidth={1.6} strokeDasharray="4 4" dot={false}
                opacity={0.55} connectNulls />,
            ])}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginTop: 8 }}>
        <span className="chip chip-ok">{chip}</span>
        <span className="chip chip-quiet">dashed = our naive extrapolation, not a forecast</span>
        <button className="pill" style={{ marginLeft: 'auto' }}
          onClick={() => downloadCsv('compass-income-history.csv', series as unknown as Record<string, unknown>[])}>
          ⤓ CSV
        </button>
      </div>
      {note && (
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 8, lineHeight: 1.6 }}>
          How we tell actual from projected: {note}
        </p>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Scatter builder                                                     */
/* ------------------------------------------------------------------ */

function ScatterBuilder() {
  const data = useData()
  const [xKey, setXKey] = useState('apt_m2')
  const [yKey, setYKey] = useState('years_to_home')

  const xM = METRIC_BY_KEY.get(xKey)
  const yM = METRIC_BY_KEY.get(yKey)

  const points = useMemo(() => {
    if (!xM || !yM) return []
    return data.cities
      .map((c) => {
        const k = data.countryById.get(c.country)
        return { name: c.name, cc: c.country, x: xM.value(c, k, 'mid'), y: yM.value(c, k, 'mid') }
      })
      .filter((p): p is { name: string; cc: string; x: number; y: number } => p.x != null && p.y != null)
  }, [data, xM, yM])

  const dropped = data.cities.length - points.length

  return (
    <div className="panel">
      <h3>Ask your own question</h3>
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
        <Picker label="across" value={xKey} onChange={setXKey} />
        <Picker label="up" value={yKey} onChange={setYKey} />
      </div>

      <div style={{ height: 340 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 20, bottom: 24, left: 8 }}>
            <CartesianGrid stroke="var(--line)" />
            <XAxis type="number" dataKey="x" name={xM?.label}
              tickFormatter={(v) => (xM ? xM.format(v) : String(v))}
              tick={{ fontSize: 11, fill: 'var(--ink-3)' }} stroke="var(--line)" />
            <YAxis type="number" dataKey="y" name={yM?.label}
              tickFormatter={(v) => (yM ? yM.format(v) : String(v))}
              tick={{ fontSize: 11, fill: 'var(--ink-3)' }} stroke="var(--line)" width={64} />
            <ZAxis range={[70, 70]} />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              content={({ payload }) => {
                const p = payload?.[0]?.payload as { name: string; x: number; y: number } | undefined
                if (!p) return null
                return (
                  <div style={{ background: 'var(--ink-1)', color: 'var(--paper)', padding: '8px 11px', borderRadius: 9, fontSize: 12 }}>
                    <b>{p.name}</b>
                    <div>{xM?.label}: {xM?.format(p.x)}</div>
                    <div>{yM?.label}: {yM?.format(p.y)}</div>
                  </div>
                )
              }}
            />
            <Scatter data={points} shape={(props: unknown) => {
              const p = props as { cx: number; cy: number; payload: { cc: string } }
              return <circle cx={p.cx} cy={p.cy} r={5.5} fill={`var(--c-${p.payload.cc})`} stroke="var(--surface)" strokeWidth={1.5} />
            }} />
          </ScatterChart>
        </ResponsiveContainer>
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

function Picker({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
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

export { Flag, num }
