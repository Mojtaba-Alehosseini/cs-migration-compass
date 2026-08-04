/* Home = the product, not a pitch.
 *
 * First screen: two preset cities already compared with real numbers, a search
 * box, and an eight-word headline. The pair rotates every few seconds until the
 * visitor touches anything, so the motion IS the data rather than decoration.
 * The no-recommendation stance is a one-line footnote, never hero copy. */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Flag } from '../components/Flag'
import { CountUp } from '../components/CountUp'
import { useData } from '../data/store'
import { money, years } from '../data/format'
import { isNeverAffordable, savingsPerYear, yearsToHome } from '../data/compute'
import type { City } from '../data/types'
import { ProfileNudge } from '../components/ProfileNudge'

/* Hand-picked pairs that each make a different point. None is a recommendation:
   they are simply contrasts that show what the dataset can answer. */
const PRESET_PAIRS: [string, string][] = [
  ['berlin', 'toronto'],     // the two most-asked-about destinations
  ['detroit', 'london'],     // cheapest home vs one of the hardest
  ['amsterdam', 'madrid'],   // northern pay vs southern cost
  ['stockholm', 'dubai'],    // taxed-and-permanent vs tax-free-and-temporary
  ['munich', 'melbourne'],   // two expensive tech hubs, different continents
]

const ROTATE_MS = 6000

export function Home() {
  const data = useData()
  const navigate = useNavigate()
  const [pairIndex, setPairIndex] = useState(0)
  const [touched, setTouched] = useState(false)
  const [query, setQuery] = useState('')
  const timer = useRef<number>(0)

  // Only keep pairs whose cities actually exist in the dataset.
  const pairs = useMemo(
    () => PRESET_PAIRS.filter(([a, b]) => data.cityById.has(a) && data.cityById.has(b)),
    [data],
  )

  useEffect(() => {
    if (touched || pairs.length < 2) return
    if (typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches) return
    timer.current = window.setInterval(() => setPairIndex((i) => (i + 1) % pairs.length), ROTATE_MS)
    return () => window.clearInterval(timer.current)
  }, [touched, pairs.length])

  const stop = useCallback(() => setTouched(true), [])

  const pair = pairs[pairIndex % pairs.length] ?? pairs[0]
  const left = pair ? data.cityById.get(pair[0]) : undefined
  const right = pair ? data.cityById.get(pair[1]) : undefined

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) return []
    const cities = data.cities
      .filter((c) => c.name.toLowerCase().includes(q))
      .map((c) => ({ kind: 'city' as const, id: c.id, name: c.name, sub: data.countryById.get(c.country)?.name ?? '' }))
    const countries = data.countries
      .filter((c) => c.name.toLowerCase().includes(q))
      .map((c) => ({ kind: 'country' as const, id: c.id, name: c.name, sub: 'country' }))
    return [...cities, ...countries].slice(0, 7)
  }, [query, data])

  return (
    <div className="wrap" style={{ paddingTop: 30 }}>
      <h1
        style={{
          fontSize: 'clamp(28px, 4vw, 44px)',
          maxWidth: '15ch',
          marginBottom: 18,
        }}
      >
        How far one developer salary goes.
      </h1>

      {/* search — the second of the two ways to reach data in one interaction */}
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap', marginBottom: 22, position: 'relative' }}>
        <input
          value={query}
          onChange={(e) => { setQuery(e.target.value); stop() }}
          placeholder="Type a city or country — Berlin, Canada, Doha…"
          aria-label="Search cities and countries"
          style={{
            flex: 1, minWidth: 240, border: '1px solid var(--line-strong)',
            background: 'var(--surface)', borderRadius: 'var(--radius-md)',
            padding: '11px 14px', fontSize: 'var(--text-sm)',
          }}
        />
        <Link
          className="btn-accent"
          to={left && right ? `/compare?places=${left.id},${right.id}` : '/compare'}
          style={{ textDecoration: 'none', display: 'inline-block' }}
        >
          Compare →
        </Link>

        {matches.length > 0 && (
          <ul
            style={{
              position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0,
              zIndex: 'var(--z-popover)' as never, listStyle: 'none', margin: 0, padding: 5,
              background: 'var(--surface)', border: '1px solid var(--line)',
              borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)',
            }}
          >
            {matches.map((m) => (
              <li key={`${m.kind}-${m.id}`}>
                <button
                  onClick={() => {
                    setQuery('')
                    navigate(m.kind === 'city' ? `/city/${m.id}` : `/country/${m.id}`)
                  }}
                  style={{
                    display: 'flex', width: '100%', gap: 8, alignItems: 'baseline',
                    padding: '8px 10px', borderRadius: 'var(--radius-sm)', textAlign: 'left',
                  }}
                >
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>{m.name}</span>
                  <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>{m.sub}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* the live mini-compare */}
      <div
        className="panel"
        onMouseEnter={stop}
        onFocusCapture={stop}
        style={{ padding: 'var(--space-6)' }}
      >
        <div
          style={{
            display: 'grid', gap: 18, alignItems: 'start',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          }}
        >
          {left && <MiniCity city={left} />}
          {right && <MiniCity city={right} />}
        </div>

        <div
          style={{
            marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--line)',
            display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap',
            fontSize: 'var(--text-2xs)', color: 'var(--ink-3)',
          }}
        >
          <span>Every number here has a source and a date — open any city to see them.</span>
          <Link to="/data" style={{ color: 'var(--ink-2)' }}>How we calculate this →</Link>

          {!touched && pairs.length > 1 && (
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 5, alignItems: 'center' }}>
              {pairs.map((_, i) => (
                <span
                  key={i}
                  aria-hidden="true"
                  style={{
                    width: 5, height: 5, borderRadius: '50%',
                    background: i === pairIndex % pairs.length ? 'var(--accent)' : 'var(--line-strong)',
                    transition: 'background-color var(--dur-base) var(--ease-out)',
                  }}
                />
              ))}
              <span className="visually-hidden">Preset comparisons rotate until you interact.</span>
            </span>
          )}
        </div>
      </div>

      <ProfileNudge active={touched} />

      <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 22, maxWidth: '70ch' }}>
        {data.cities.length} cities across {data.countries.length} countries, as of {data.as_of}. Cities are
        listed alphabetically — nothing here is ranked unless you rank it.
      </p>
    </div>
  )
}

function MiniCity({ city }: { city: City }) {
  const data = useData()
  const country = data.countryById.get(city.country)
  const never = isNeverAffordable(city, 'mid')
  const y2h = yearsToHome(city, 'mid')

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
        <Flag cc={city.country} size={22} />
        <Link
          to={`/city/${city.id}`}
          style={{ fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--ink-1)', textDecoration: 'none' }}
        >
          {city.name}
        </Link>
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>{country?.name}</span>
      </div>

      <Row label="Mid-level dev, before tax" >
        <CountUp value={city.salary_usd_year.mid} format={money} />
      </Row>
      <Row label="Rent, 1-bed outside centre">
        <CountUp value={city.rent_1br_outside_usd_month} format={(v) => money(v)} />
        <span className="unit">/mo</span>
      </Row>
      <Row label="Kept after rent and living">
        <CountUp value={savingsPerYear(city, 'mid')} format={money} />
        <span className="unit">/yr</span>
      </Row>
      <Row label="Years to own a 90 m² flat">
        {never ? (
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--warn)' }}>never on this salary</span>
        ) : (
          <CountUp value={y2h} format={(v) => years(v)} />
        )}
      </Row>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10,
        padding: '7px 0', borderTop: '1px solid var(--line)',
      }}
    >
      <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>{label}</span>
      <span className="big" style={{ fontSize: 'var(--text-md)' }}>{children}</span>
    </div>
  )
}
