/* Weather — a year has a shape.
 *
 * A thirty-year normal has no trend in it, so a trend line would be an
 * invention. The honest chart is the year itself: each city's daily range as a
 * band, high to low, with freezing marked.
 *
 * The normals are already in core.json, so this theme costs no extra request.
 */

import { useMemo, useState } from 'react'
import { Chart } from '../chart/Chart'
import type { ChartCfg, Series, Pt } from '../chart/engine'
import { Picker, ChartFoot, ChartTable, Gap, type HeroStat } from './Controls'
import { useData } from '../../data/store'
import type { City } from '../../data/types'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const cc = (c: string) => `var(--c-${c})`

/** Cities whose monthly normals actually arrived. The rest are named, never
 *  filled in — see the gap card below. */
export const withNormals = (cities: City[]) => cities.filter((c) => (c.climate.monthly?.length ?? 0) === 12)

export function weatherHero(cities: City[]): HeroStat[] {
  const have = withNormals(cities)
  if (!have.length) return []
  const hiOf = (c: City) => Math.max(...c.climate.monthly!.map((m) => m.avg_high_c))
  const loOf = (c: City) => Math.min(...c.climate.monthly!.map((m) => m.avg_low_c))
  const hot = have.reduce((a, b) => (hiOf(a) > hiOf(b) ? a : b))
  const cold = have.reduce((a, b) => (loOf(a) < loOf(b) ? a : b))
  return [
    { value: hiOf(hot), format: (v) => `${v.toFixed(0)}°C`,
      label: `hottest month among covered cities — ${hot.name}`, source: '1991–2020 normals' },
    { value: loOf(cold), format: (v) => `${v < 0 ? '−' : ''}${Math.abs(v).toFixed(0)}°C`,
      label: `coldest month — ${cold.name}`, source: '1991–2020 normals' },
    { value: have.length, format: (v) => `${Math.round(v)} of ${cities.length}`,
      label: 'cities with monthly normals so far', source: 'the rest are named, not guessed' },
  ]
}

export function WeatherTheme() {
  const data = useData()
  const have = useMemo(() => withNormals(data.cities), [data.cities])
  const missing = useMemo(
    () => data.cities.filter((c) => (c.climate.monthly?.length ?? 0) !== 12),
    [data.cities],
  )
  const [picks, setPicks] = useState(['boston', 'abu-dhabi'])

  const cfg = useMemo<ChartCfg>(() => {
    const series: Series[] = []
    const bands: NonNullable<ChartCfg['bands']> = []
    for (const id of picks) {
      const c = have.find((x) => x.id === id)
      if (!c?.climate.monthly) continue
      const hi = c.climate.monthly.map((m, i) => [i, m.avg_high_c] as Pt)
      const lo = c.climate.monthly.map((m, i) => [i, m.avg_low_c] as Pt)
      series.push({ key: `${id}_h`, label: c.name, color: cc(c.country), pts: hi, hoverLabel: `${c.name} high` })
      series.push({ key: `${id}_l`, color: cc(c.country), pts: lo, mode: 'lo', hoverLabel: `${c.name} low` })
      bands.push({ hi: `${id}_h`, lo: `${id}_l`, color: cc(c.country) })
    }
    return {
      aria: `Monthly temperature normals, daily high to low, for ${picks.join(' and ')}`,
      x: { min: 0, max: 11, ticks: MONTHS.map((m, i) => [i, m] as [number, string]) },
      y: { min: -17, max: 46, ticks: [[-15, '−15°'], [0, '0°'], [15, '15°'], [30, '30°'], [45, '45°']] },
      zero: 0,
      series,
      bands,
      fmtX: (v) => MONTHS[v] ?? '',
      fmtV: (p) => `${(p[1] ?? 0).toFixed(1)} °C`,
    }
  }, [have, picks])

  const csv = picks.flatMap((id) => {
    const c = have.find((x) => x.id === id)
    return (c?.climate.monthly ?? []).map((m, i) => ({
      city: c!.name, month: MONTHS[i], avg_high_c: m.avg_high_c, avg_low_c: m.avg_low_c,
    }))
  })

  return (
    <>
      <div className="panel s6">
        <h2>A year has a shape</h2>
        <div className="sub">
          Thirty-year normals have no trend — the honest chart is the year itself.
          The band is each city’s daily range, high to low; the dotted rule is freezing. Swap the
          cities and watch the shapes trade places.
        </div>
        <div className="crail">
          <span className="lbl">two cities</span>
          <Picker label="Cities" cap={2}
            items={have.map((c) => ({ k: c.id, cc: c.country, label: c.name }))}
            active={picks} onChange={setPicks} />
        </div>
        {/* Swapping a city changes which shapes are on screen, not the values of
            a shared shape — so it crossfades rather than pretending to morph. */}
        <Chart id="ex-normals" cfg={cfg} transition="fade" />
        <ChartFoot csv={{ name: 'compass-climate-normals.csv', rows: csv }}>
          <span className="chip chip-ok">● Official · 1991–2020 normals, ERA5</span>
          <span className="chip chip-quiet">the same overlay lives in Compare for the cities you picked</span>
        </ChartFoot>
        <ChartTable caption="Monthly normals — the numbers behind this chart"
          head={['City', 'Month', 'Avg high °C', 'Avg low °C']}
          rows={csv.map((r) => [r.city, r.month ?? '', r.avg_high_c, r.avg_low_c])} />
      </div>

      <Gap title={`${missing.length} cities are still waiting`} span="s3"
        where={<>Pipeline status on the <a href="#/data">Data page →</a></>}>
        <p>
          {have.length} of {data.cities.length} cities carry monthly normals so far; the rest arrive with the
          next pipeline run. Until then their pages show annual figures and name what’s missing —
          never a guess.
        </p>
        <p style={{ color: 'var(--ink-3)' }}>
          Waiting: {missing.map((c) => c.name).join(' · ')}
        </p>
      </Gap>

      <Gap title="The matcher stays off" span="s3">
        <p>
          “Find a climate you can live in” scores nothing until you set a limit — there is no
          default climate a person is assumed to want. It keeps its place below, unchanged.
        </p>
      </Gap>
    </>
  )
}
