/* Twelve-month temperature curves, overlaid.
 *
 * An annual average hides the thing people actually want to know: what a
 * February is like, and whether the summer is unbearable. Overlaying the
 * selected cities on one set of axes answers both at a glance, and a country
 * keeps its colour here as everywhere else.
 *
 * Cities without normals are listed by name rather than silently absent.
 *
 * This is the same chart kit Explore draws with, and the same band language:
 * one panel of it replaced the 380 KB charting library that used to ride along
 * with Compare for this single overlay.
 */

import { useMemo } from 'react'
import { Chart } from './chart/Chart'
import type { ChartCfg, Pt, Series } from './chart/engine'
import { downloadCsv } from '../lib/export'
import type { City } from '../data/types'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function ClimateOverlay({ cities }: { cities: City[] }) {
  const withData = cities.filter((c) => c.climate.monthly?.length === 12)
  const without = cities.filter((c) => !c.climate.monthly?.length)

  const rows = useMemo(() => MONTHS.map((label, i) => {
    const row: Record<string, string | number | null> = { month: label }
    for (const c of withData) {
      const m = c.climate.monthly![i]!
      row[`${c.name} high`] = m.avg_high_c
      row[`${c.name} low`] = m.avg_low_c
    }
    return row
  }), [withData])

  const cfg = useMemo<ChartCfg>(() => {
    const series: Series[] = []
    const bands: NonNullable<ChartCfg['bands']> = []
    for (const c of withData) {
      const colour = `var(--c-${c.country})`
      series.push({
        key: `${c.id}_h`, label: c.name, color: colour, hoverLabel: `${c.name} high`,
        pts: c.climate.monthly!.map((m, i) => [i, m.avg_high_c] as Pt),
      })
      series.push({
        key: `${c.id}_l`, color: colour, mode: 'lo', hoverLabel: `${c.name} low`,
        pts: c.climate.monthly!.map((m, i) => [i, m.avg_low_c] as Pt),
      })
      bands.push({ hi: `${c.id}_h`, lo: `${c.id}_l`, color: colour })
    }
    const all = withData.flatMap((c) => c.climate.monthly!.flatMap((m) => [m.avg_high_c, m.avg_low_c]))
    const lo = Math.min(...all, 0)
    const hi = Math.max(...all, 0)
    const pad = 4
    return {
      aria: `Monthly temperature normals for ${withData.map((c) => c.name).join(', ')}`,
      h: 260, padL: 42, padR: 74,
      x: { min: 0, max: 11, ticks: MONTHS.map((m, i) => [i, m] as [number, string]) },
      y: {
        min: Math.floor((lo - pad) / 5) * 5,
        max: Math.ceil((hi + pad) / 5) * 5,
        ticks: [-15, 0, 15, 30, 45]
          .filter((v) => v >= lo - pad && v <= hi + pad)
          .map((v) => [v, `${v < 0 ? '−' : ''}${Math.abs(v)}°`] as [number, string]),
      },
      zero: 0,
      series,
      bands,
      fmtX: (v) => MONTHS[v] ?? '',
      fmtV: (p) => `${(p[1] ?? 0).toFixed(1)} °C`,
    }
  }, [withData])

  if (withData.length === 0) {
    return (
      <p className="nodata" style={{ marginTop: 8 }}>
        No monthly climate normals for {cities.map((c) => c.name).join(' or ')}.
      </p>
    )
  }

  return (
    <div style={{ marginTop: 6 }}>
      <Chart id={`climate-overlay-${withData.map((c) => c.id).join('-')}`} cfg={cfg} transition="fade" />

      <div style={{
        display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center',
        fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 6,
      }}>
        <span>Solid = average daily high · dashed = average daily low.</span>
        <span className="chip chip-quiet">1991–2020 normals · ERA5 reanalysis</span>
        {without.length > 0 && (
          <span className="chip chip-note">
            no normals for {without.map((c) => c.name).join(', ')}
          </span>
        )}
        <button className="pill" style={{ marginLeft: 'auto' }}
          onClick={() => downloadCsv('compass-climate-normals.csv', rows)}>⤓ CSV</button>
      </div>

      <details className="chart-table">
        <summary>Monthly normals — the numbers behind this chart</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Month</th>
              {withData.map((c) => <th key={c.id} scope="col">{c.name} high / low °C</th>)}
            </tr>
          </thead>
          <tbody>
            {MONTHS.map((m, i) => (
              <tr key={m}>
                <td>{m}</td>
                {withData.map((c) => (
                  <td key={c.id}>
                    {c.climate.monthly![i]!.avg_high_c} / {c.climate.monthly![i]!.avg_low_c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
