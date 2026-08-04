/* The editable budget.
 *
 * Prefilled from our city averages, then the user overrides it and savings and
 * years-to-home move live. The formula is on screen the whole time — a computed
 * number that hides its computation is just an assertion. */

import { Flag } from './Flag'
import { money, num, years } from '../data/format'
import {
  HOME_M2, effectiveLiving, effectiveRent, isNeverAffordable, m2PerYear,
  netFor, savingsPerYear, yearsToHome, type Budget,
} from '../data/compute'
import type { Band, City } from '../data/types'

interface Props {
  cities: City[]
  budget: Budget
  onChange: (b: Budget) => void
  band: Band
}

export function BudgetEditor({ cities, budget, onChange, band }: Props) {
  const rentFactor = budget.rentFactor ?? 1
  const livingFactor = budget.livingFactor ?? 1
  const edited = rentFactor !== 1 || livingFactor !== 1

  return (
    <div className="panel" style={{ marginTop: 18 }}>
      <h2>Your assumptions</h2>
      <div className="sub">
        These start from each city’s own averages. Move them and every figure below recalculates —
        nothing is baked in.
      </div>

      <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginBottom: 14 }}>
        <Slider
          label="Rent"
          hint="as a share of the listed 1-bed outside the centre"
          value={rentFactor}
          onChange={(v) => onChange({ ...budget, rentFactor: v })}
        />
        <Slider
          label="Everything else"
          hint="food, transport, phone, going out"
          value={livingFactor}
          onChange={(v) => onChange({ ...budget, livingFactor: v })}
        />
        {edited && (
          <button className="pill" style={{ alignSelf: 'center' }}
            onClick={() => onChange({})}>
            reset to city averages
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(270px, 1fr))' }}>
        {cities.map((city) => (
          <Waterfall key={city.id} city={city} band={band} budget={budget} />
        ))}
      </div>

      <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 12, lineHeight: 1.7 }}>
        <b style={{ color: 'var(--ink-2)' }}>Years to a home</b> = price of a {HOME_M2} m² flat outside the
        centre ÷ what you save in a year. Savings = salary after that country’s real tax, minus rent,
        minus living costs.
      </p>
    </div>
  )
}

function Slider({ label, hint, value, onChange }:
  { label: string; hint: string; value: number; onChange: (v: number) => void }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
      <span style={{ fontWeight: 600, color: 'var(--ink-1)' }}>{label}</span>
      <span style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
        <input
          type="range" min={60} max={140} step={5}
          value={Math.round(value * 100)}
          onChange={(e) => onChange(Number(e.target.value) / 100)}
          style={{ width: 150, accentColor: 'var(--accent)' }}
          aria-label={`${label} — ${hint}`}
        />
        <span className="tnum" style={{ fontWeight: 600, color: 'var(--ink-1)' }}>
          {Math.round(value * 100)}%
        </span>
      </span>
      <span style={{ color: 'var(--ink-3)' }}>{hint}</span>
    </label>
  )
}

/** The money waterfall — salary in, rent and living out, what remains. */
function Waterfall({ city, band, budget }: { city: City; band: Band; budget: Budget }) {
  const net = netFor(city, band)
  const rent = effectiveRent(city, budget)
  const living = effectiveLiving(city, budget)
  const saved = savingsPerYear(city, band, budget)
  const y2h = yearsToHome(city, band, budget)
  const m2 = m2PerYear(city, band, budget)
  const never = isNeverAffordable(city, band, budget)

  if (net == null || rent == null || living == null) {
    return (
      <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius-md)', padding: 12 }}>
        <Head city={city} />
        <p className="nodata" style={{ marginTop: 8 }}>
          We can’t work this out for {city.name} — no{' '}
          {[net == null && 'salary or tax rate', rent == null && 'rent', living == null && 'living-cost']
            .filter(Boolean).join(' or ')} figure.
        </p>
      </div>
    )
  }

  const rentYr = rent * 12
  const livingYr = living * 12
  const max = Math.max(net, 1)
  const h = (v: number) => `${Math.max(3, (Math.abs(v) / max) * 84)}px`

  return (
    <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius-md)', padding: 12 }}>
      <Head city={city} />
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 9, height: 104, margin: '16px 0 4px' }}>
        <Col label={<>a year,<br />after tax</>} value={money(net)} height={h(net)} color="var(--ink-2)" />
        <Col label="rent" value={`−${money(rentYr)}`} height={h(rentYr)} color="var(--warn)" />
        <Col label="living" value={`−${money(livingYr)}`} height={h(livingYr)} color="var(--note)" />
        <Col label="saved" value={money(saved)} height={h(saved ?? 0)} color="var(--accent)" />
      </div>

      {never ? (
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--warn)', marginTop: 10 }}>
          Nothing is left at the end of the year, so buying never happens on this salary.
          Try a higher band or lower assumptions.
        </p>
      ) : y2h != null && m2 != null ? (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginBottom: 5 }}>
            A {HOME_M2} m² flat costs {money((city.apt_price_outside_usd_m2 ?? 0) * HOME_M2)}.
            Your savings buy <b>~{num(m2, 1)} m² a year</b>:
          </div>
          <div style={{
            position: 'relative', height: 16, border: '1px solid var(--line)',
            borderRadius: 'var(--radius-sm)', background: 'var(--surface-sunk)', overflow: 'hidden',
          }}>
            <div style={{
              position: 'absolute', inset: '0 auto 0 0',
              width: `${Math.min(100, (1 / y2h) * 100)}%`,
              background: 'repeating-linear-gradient(90deg, var(--accent) 0 9.5px, var(--accent-strong) 9.5px 10px)',
              opacity: 0.85, transition: 'width var(--dur-slow) var(--ease-out)',
            }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 4 }}>
            <span>year 0</span>
            <span>one year of saving</span>
            <span>year {years(y2h)} → the keys</span>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function Head({ city }: { city: City }) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <Flag cc={city.country} size={16} />
      <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>{city.name}</span>
    </div>
  )
}

function Col({ label, value, height, color }:
  { label: React.ReactNode; value: string; height: string; color: string }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center', gap: 4 }}>
      <span className="tnum" style={{ fontSize: 'var(--text-2xs)', fontWeight: 600 }}>{value}</span>
      <div style={{
        width: '100%', height, background: color, borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
        transition: 'height var(--dur-slow) var(--ease-out)',
      }} />
      <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', textAlign: 'center', lineHeight: 1.3 }}>
        {label}
      </span>
    </div>
  )
}
