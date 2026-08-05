/* Twelve-month temperature curves, overlaid.
 *
 * An annual average hides the thing people actually want to know: what a
 * February is like, and whether the summer is unbearable. Overlaying the
 * selected cities on one set of axes answers both at a glance, and a country
 * keeps its colour here as everywhere else.
 *
 * Cities without normals are listed by name rather than silently absent.
 */

import { useMemo } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { num } from '../data/format'
import { downloadCsv } from '../lib/export'
import type { City } from '../data/types'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function ClimateOverlay({ cities }: { cities: City[] }) {
  const withData = cities.filter((c) => c.climate.monthly?.length === 12)
  const without = cities.filter((c) => !c.climate.monthly?.length)

  const rows = useMemo(() => {
    return MONTHS.map((label, i) => {
      const row: Record<string, string | number | null> = { month: label }
      for (const c of withData) {
        const m = c.climate.monthly![i]!
        row[`${c.name} high`] = m.avg_high_c
        row[`${c.name} low`] = m.avg_low_c
      }
      return row
    })
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
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 14, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'var(--ink-3)' }} stroke="var(--line)" />
            <YAxis
              tickFormatter={(v) => `${v}°`}
              tick={{ fontSize: 11, fill: 'var(--ink-3)' }}
              stroke="var(--line)" width={40}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--ink-1)', border: 'none', borderRadius: 9,
                color: 'var(--paper)', fontSize: 12,
              }}
              formatter={(v, n) => [`${num(typeof v === 'number' ? v : null, 1)} °C`, String(n)]}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {withData.map((c) => [
              <Line key={`${c.id}h`} type="monotone" dataKey={`${c.name} high`}
                stroke={`var(--c-${c.country})`} strokeWidth={2.2} dot={false} />,
              <Line key={`${c.id}l`} type="monotone" dataKey={`${c.name} low`}
                stroke={`var(--c-${c.country})`} strokeWidth={1.5} strokeDasharray="3 3"
                dot={false} opacity={0.75} />,
            ])}
          </LineChart>
        </ResponsiveContainer>
      </div>

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
    </div>
  )
}
