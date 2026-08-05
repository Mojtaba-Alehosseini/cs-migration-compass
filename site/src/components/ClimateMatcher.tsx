/* Climate matcher — inert until you set a preference.
 *
 * This is a filter, and the site's rule is that every filter is off by default.
 * With no preference set it shows nothing and scores nothing: there is no
 * "default climate" a person is assumed to want. Once a preference exists it
 * measures distance from it, and it never hides a city — it orders and labels.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Flag } from './Flag'
import { useData } from '../data/store'
import { num } from '../data/format'
import type { City } from '../data/types'

interface Prefs {
  winterLow: number | null   // °C you are willing to live with in the coldest month
  summerHigh: number | null  // °C you are willing to tolerate in the hottest month
  wantSun: boolean
}

const EMPTY: Prefs = { winterLow: null, summerHigh: null, wantSun: false }

function coldestLow(c: City): number | null {
  const m = c.climate.monthly
  if (m?.length === 12) return Math.min(...m.map((x) => x.avg_low_c))
  return c.climate.winter_avg_low_c
}

function warmestHigh(c: City): number | null {
  const m = c.climate.monthly
  if (m?.length === 12) return Math.max(...m.map((x) => x.avg_high_c))
  return c.climate.summer_avg_high_c
}

export function ClimateMatcher() {
  const data = useData()
  const [prefs, setPrefs] = useState<Prefs>(EMPTY)

  const isSet = prefs.winterLow != null || prefs.summerHigh != null || prefs.wantSun

  const scored = useMemo(() => {
    if (!isSet) return []
    const sun = data.cities.map((c) => c.climate.sunshine_hours_yr).filter((v): v is number => v != null)
    const sunMax = sun.length ? Math.max(...sun) : 1

    return data.cities
      .map((city) => {
        const low = coldestLow(city)
        const high = warmestHigh(city)
        const missing: string[] = []
        let penalty = 0
        let used = 0

        if (prefs.winterLow != null) {
          if (low == null) missing.push('winter low')
          else { penalty += Math.max(0, prefs.winterLow - low) / 25; used++ }
        }
        if (prefs.summerHigh != null) {
          if (high == null) missing.push('summer high')
          else { penalty += Math.max(0, high - prefs.summerHigh) / 25; used++ }
        }
        if (prefs.wantSun) {
          const s = city.climate.sunshine_hours_yr
          if (s == null) missing.push('sunshine')
          else { penalty += 1 - s / sunMax; used++ }
        }

        return {
          city, low, high,
          match: used ? Math.max(0, 1 - penalty / used) : null,
          missing,
        }
      })
      .sort((a, b) => (b.match ?? -1) - (a.match ?? -1))
  }, [prefs, isSet, data])

  return (
    <div className="panel" style={{ marginTop: 12 }}>
      <h2>Find a climate you can live in</h2>
      <div className="sub">
        Nothing is set, so nothing is scored — there is no default climate we assume you want. Set a
        limit and every city is measured against it.
      </div>

      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', margin: '10px 0 4px' }}>
        <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontWeight: 600, color: 'var(--ink-1)' }}>Coldest month, no colder than</span>
          <span style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
            <input type="range" min={-15} max={18} step={1}
              value={prefs.winterLow ?? -15}
              onChange={(e) => setPrefs((p) => ({ ...p, winterLow: Number(e.target.value) }))}
              style={{ width: 150, accentColor: 'var(--accent)' }}
              aria-label="Coldest acceptable winter low in Celsius" />
            <b className="tnum" style={{ color: prefs.winterLow == null ? 'var(--ink-3)' : 'var(--ink-1)' }}>
              {prefs.winterLow == null ? 'not set' : `${prefs.winterLow} °C`}
            </b>
          </span>
        </label>

        <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontWeight: 600, color: 'var(--ink-1)' }}>Hottest month, no hotter than</span>
          <span style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
            <input type="range" min={18} max={45} step={1}
              value={prefs.summerHigh ?? 45}
              onChange={(e) => setPrefs((p) => ({ ...p, summerHigh: Number(e.target.value) }))}
              style={{ width: 150, accentColor: 'var(--accent)' }}
              aria-label="Hottest acceptable summer high in Celsius" />
            <b className="tnum" style={{ color: prefs.summerHigh == null ? 'var(--ink-3)' : 'var(--ink-1)' }}>
              {prefs.summerHigh == null ? 'not set' : `${prefs.summerHigh} °C`}
            </b>
          </span>
        </label>

        <label style={{ display: 'flex', gap: 7, alignItems: 'center', fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
          <input type="checkbox" checked={prefs.wantSun}
            onChange={(e) => setPrefs((p) => ({ ...p, wantSun: e.target.checked }))}
            style={{ accentColor: 'var(--accent)' }} />
          Sunshine matters to me
        </label>

        {isSet && (
          <button className="pill" style={{ alignSelf: 'center' }} onClick={() => setPrefs(EMPTY)}>
            Turn off
          </button>
        )}
      </div>

      {!isSet ? (
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 8 }}>
          Move a slider or tick the box to switch this on.
        </p>
      ) : (
        <>
          <ol style={{ listStyle: 'none', padding: 0, margin: '12px 0 0' }}>
            {scored.slice(0, 12).map((r, i) => (
              <li key={r.city.id} style={{
                display: 'flex', gap: 10, alignItems: 'center', padding: '5px 0',
                borderTop: i ? '1px solid var(--line)' : '1px solid var(--line)',
              }}>
                <Flag cc={r.city.country} size={15} />
                <Link to={`/city/${r.city.id}`} style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-1)', textDecoration: 'none', minWidth: 110 }}>
                  {r.city.name}
                </Link>
                <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', minWidth: 130 }}>
                  {r.low != null ? `${num(r.low, 1)}°` : '—'} to {r.high != null ? `${num(r.high, 1)}°` : '—'}
                </span>
                <span style={{ flex: 1, height: 7, background: 'var(--surface-sunk)', borderRadius: 4 }}>
                  {r.match != null && (
                    <span style={{
                      display: 'block', height: '100%', width: `${r.match * 100}%`,
                      background: `var(--c-${r.city.country})`, borderRadius: 4,
                      transition: 'width var(--dur-slow) var(--ease-out)',
                    }} />
                  )}
                </span>
                {r.missing.length > 0 && (
                  <span className="chip chip-note" style={{ fontSize: 10, padding: '1px 7px' }}>
                    no {r.missing.join(', ')}
                  </span>
                )}
              </li>
            ))}
          </ol>
          <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 10, lineHeight: 1.7 }}>
            Match is distance from the limits you set, using 1991–2020 monthly normals where we have
            them and the curated annual figures otherwise. A city missing a figure is scored on what it
            does have and says so — it is never dropped from the list. Showing 12 of {scored.length}.
          </p>
        </>
      )}
    </div>
  )
}
