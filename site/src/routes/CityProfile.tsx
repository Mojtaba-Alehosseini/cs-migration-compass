/* City profile — everything we hold about one place.
 *
 * Opens with ONE human sentence, then at most three plain-language chips. Every
 * figure is tappable. Computed numbers show their computation. Missing data says
 * what is missing rather than vanishing. */

import { Link, useParams } from 'react-router-dom'
import { Flag, FlagRibbon } from '../components/Flag'
import { Figure } from '../components/Figure'
import { useData } from '../data/store'
import { money, num, pct, sourceName, years, NO_DATA, asOfLabel } from '../data/format'
import {
  HOME_M2, isNeverAffordable, m2PerYear, missingInputs, netFor, savingsPerYear, yearsToHome,
} from '../data/compute'
import { NotFound } from './NotFound'
import type { Band } from '../data/types'
import { useState } from 'react'

const BAND_LABEL: Record<Band, string> = {
  new_grad: 'Starting out',
  mid: '3–5 years in',
  senior: 'Senior',
}

export function CityProfile() {
  const { id } = useParams()
  const data = useData()
  const city = id ? data.cityById.get(id) : undefined
  const [band] = useState<Band>('mid')
  const [allJobs, setAllJobs] = useState(false)

  if (!city) return <NotFound />
  const country = data.countryById.get(city.country)
  if (!country) return <NotFound />

  const net = netFor(city, band)
  const saved = savingsPerYear(city, band)
  const y2h = yearsToHome(city, band)
  const m2 = m2PerYear(city, band)
  const never = isNeverAffordable(city, band)
  const missing = missingInputs(city, band)
  const lf = city.salary_levels_fyi

  const chips = buildChips(country)

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <Flag cc={city.country} size={24} title={`Flag of ${country.name}`} />
        <h1 style={{ fontSize: 'var(--text-xl)' }}>
          {city.name}{' '}
          <Link to={`/country/${country.id}`}
            style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-3)', fontWeight: 400, marginLeft: 4 }}>
            {country.name}
          </Link>
        </h1>
      </div>

      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)', padding: '8px 0 10px', maxWidth: '72ch' }}>
        {city.tech_scene_note}
      </p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', paddingBottom: 6 }}>
        {chips.map((c, i) => (
          <span key={i} className={`chip ${c.tone}`}>{c.text}</span>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12, padding: '12px 0' }}>

        {/* ---- salaries ---- */}
        <div className="panel">
          <h2>What developers earn here</h2>
          <div className="sub">Per year, before tax. Tap any number to see where it comes from.</div>

          <div style={{ display: 'inline-flex', border: '1px solid var(--line)', borderRadius: 'var(--radius-md)', overflow: 'hidden', marginBottom: 12 }}>
            <button onClick={() => setAllJobs(false)} aria-pressed={!allJobs}
              style={tabStyle(!allJobs)}>Developers</button>
            <button onClick={() => setAllJobs(true)} aria-pressed={allJobs}
              style={tabStyle(allJobs)}>All jobs</button>
          </div>

          {!allJobs ? (
            <>
              {(['new_grad', 'mid', 'senior'] as Band[]).map((b) => {
                const v = city.salary_usd_year[b]
                const max = city.salary_usd_year.senior ?? v ?? 1
                const top = lf?.median_total_comp_usd ?? null
                return (
                  <div key={b} style={{ margin: '9px 0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
                      <span>{BAND_LABEL[b]}</span>
                      <Figure source={{
                        name: 'talent.com + PayScale',
                        url: city.sources.find((s) => s.includes('talent.com') || s.includes('payscale')),
                        what: city.salary_usd_year.note ?? 'Market-wide band for this city.',
                        asOf: city.as_of, confidence: 'crowd',
                      }}>
                        <b className="tnum">{money(v)}</b>
                      </Figure>
                    </div>
                    <div style={{ position: 'relative', height: 11, background: 'var(--surface-sunk)', borderRadius: 'var(--radius-sm)', marginTop: 5, overflow: 'hidden' }}>
                      {v != null && (
                        <div style={{
                          position: 'absolute', inset: '0 auto 0 0', width: `${(v / (max || 1)) * 88}%`,
                          background: 'var(--accent)', opacity: 0.85, borderRadius: 'var(--radius-sm)',
                        }} />
                      )}
                      {b === 'mid' && v != null && top != null && top > v && (
                        <div title="what top employers pay on top" style={{
                          position: 'absolute', top: 0, bottom: 0,
                          left: `${(v / (max || 1)) * 88}%`,
                          width: `${Math.min(30, ((top - v) / (max || 1)) * 88)}%`,
                          background: 'repeating-linear-gradient(90deg, var(--accent) 0 3px, transparent 3px 6px)',
                          opacity: 0.55,
                        }} />
                      )}
                    </div>
                  </div>
                )
              })}
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginTop: 8 }}>
                {lf?.median_total_comp_usd != null ? (
                  <>Hatched = the extra that big-name employers pay. Their median total package here is{' '}
                    <Figure source={{
                      name: 'levels.fyi', url: lf.source, asOf: lf.as_of, confidence: 'crowd',
                      what: 'Total compensation — base plus stock plus bonus, so partly a definition difference from the market band above.',
                    }}><b>{money(lf.median_total_comp_usd)}</b></Figure>.
                  </>
                ) : lf?.unavailable_reason ? (
                  <span className="nodata">No levels.fyi figure for {city.name} — {lf.unavailable_reason.slice(0, 120)}…</span>
                ) : null}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)' }}>
              <p>
                We hold the national average wage from the OECD for {country.name}. Open the{' '}
                <Link to="/explore/money">Money theme</Link> to see developer pay against it over time.
              </p>
              <p style={{ marginTop: 8, color: 'var(--ink-3)' }}>
                Comparing a city developer salary with a national all-jobs average mixes two
                geographies, so we show them side by side rather than as a single ratio here.
              </p>
            </div>
          )}
        </div>

        {/* ---- a month here ---- */}
        <div className="panel">
          <h2>A month in {city.name}</h2>
          {net != null && city.rent_1br_outside_usd_month != null && city.col_single_no_rent_usd_month != null ? (
            <>
              <div className="sub">
                Take the mid-level paycheck. After {country.name}’s taxes,{' '}
                <Figure source={{
                  name: 'OECD Taxing Wages + national calculators',
                  what: country.tax.net_note ?? undefined, asOf: country.as_of, confidence: 'official',
                }}>
                  <b>{money(net / 12)}</b>
                </Figure>{' '}
                lands in your account each month. Where it goes:
              </div>
              <MonthBar
                rent={city.rent_1br_outside_usd_month}
                living={city.col_single_no_rent_usd_month}
                net={net / 12}
              />
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 6 }}>
                {pct(city.net_pct)} of gross survives tax in {country.name}.
              </div>
            </>
          ) : (
            <p className="nodata" style={{ marginTop: 8 }}>
              We can’t break down a month here — no {missing.join(' or ')} figure for {city.name}.
            </p>
          )}
        </div>

        {/* ---- years to home ---- */}
        <div className="panel">
          <h2>The path to owning a home</h2>
          <div className="sub">Every step shown, every number editable in Compare.</div>
          {never ? (
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--warn)', marginTop: 8 }}>
              At this salary nothing is left after rent and living costs, so buying never happens.
              That is the honest answer for {city.name}, not a very large number.
            </p>
          ) : y2h != null && m2 != null && city.apt_price_outside_usd_m2 != null ? (
            <>
              <div className="big" style={{ fontSize: 'var(--text-2xl)' }}>{years(y2h)}</div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginTop: 6, lineHeight: 1.7 }}>
                A {HOME_M2} m² flat outside the centre costs{' '}
                <Figure source={{
                  name: 'Numbeo', url: city.sources.find((s) => s.includes('numbeo')),
                  what: 'Crowd-reported purchase price per square metre.', asOf: city.as_of, confidence: 'crowd',
                }}>
                  <b>{money(city.apt_price_outside_usd_m2 * HOME_M2)}</b>
                </Figure>.
                You save {money(saved)} a year, which buys <b>~{num(m2, 1)} m² a year</b>.
              </div>
              <div style={{
                position: 'relative', height: 16, border: '1px solid var(--line)', marginTop: 10,
                borderRadius: 'var(--radius-sm)', background: 'var(--surface-sunk)', overflow: 'hidden',
              }}>
                <div style={{
                  position: 'absolute', inset: '0 auto 0 0', width: `${Math.min(100, (1 / y2h) * 100)}%`,
                  background: 'repeating-linear-gradient(90deg, var(--accent) 0 9.5px, var(--accent-strong) 9.5px 10px)',
                  opacity: 0.85,
                }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 4 }}>
                <span>year 0</span><span>after one year</span><span>year {years(y2h)} → the keys</span>
              </div>
            </>
          ) : (
            <p className="nodata" style={{ marginTop: 8 }}>
              No data — we have no {missing.join(' or ')} figure for {city.name}, so this can’t be worked out.
            </p>
          )}
        </div>

        {/* ---- journey ---- */}
        <div className="panel">
          <h2>From landing to a {country.name} passport</h2>
          <div className="sub">The legal road, step by step. Typical times — real cases vary.</div>
          <Journey
            cc={country.id}
            pr={country.pr_years_typical}
            cit={country.citizenship_years_typical}
            route={country.visa.skilled_routes[0]?.name}
            dual={country.dual_citizenship}
          />
        </div>

        {/* ---- life measured ---- */}
        <div className="panel">
          <h2>Life here, measured</h2>
          <div className="sub">The big global surveys, in plain words.</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9, marginTop: 6 }}>
            {country.enriched.happiness?.rank != null && (
              <LifeRow big={`#${country.enriched.happiness.rank}`}>
                of {country.enriched.happiness.of ?? '—'} countries for happiness — residents rate their
                own lives {num(country.enriched.happiness.score, 1)}/10
              </LifeRow>
            )}
            {country.indices.gpi_rank != null && (
              <LifeRow big={`#${country.indices.gpi_rank}`}>of 163 on the Global Peace Index</LifeRow>
            )}
            {country.indices.ef_epi_score != null ? (
              <LifeRow big={country.indices.ef_epi_band ?? '—'}>
                English level among locals ({country.indices.ef_epi_score} on the EF index)
              </LifeRow>
            ) : (
              <LifeRow big="native">English is the native language here</LifeRow>
            )}
            {city.climate.sunshine_hours_yr != null ? (
              <LifeRow big={`${num(city.climate.sunshine_hours_yr)} h`}>
                of sunshine a year{city.climate.winter_avg_low_c != null &&
                  `, and winter lows around ${num(city.climate.winter_avg_low_c, 1)} °C`}
              </LifeRow>
            ) : (
              <LifeRow big={NO_DATA}>no sunshine figure for {city.name}</LifeRow>
            )}
          </div>
        </div>

        {/* ---- reality ---- */}
        <div className="panel" style={{ gridColumn: '1 / -1' }}>
          <h2>What people actually say</h2>
          <div className="sub">Our honest summary of expat surveys and community reports — not marketing.</div>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', lineHeight: 'var(--leading-relaxed)' }}>
            {country.reality_paragraph}
          </p>
          <div style={{ borderTop: '1px solid var(--line)', marginTop: 12, paddingTop: 9, fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
            Sources for this page: {city.sources.slice(0, 5).map(sourceName).join(' · ')}
            {city.sources.length > 5 && ` and ${city.sources.length - 5} more`} ·{' '}
            data as of {asOfLabel(city.as_of)} · <Link to="/data">see all with links →</Link>
          </div>
        </div>
      </div>
    </div>
  )
}

function tabStyle(on: boolean): React.CSSProperties {
  return {
    padding: '6px 12px', fontSize: 'var(--text-2xs)',
    background: on ? 'var(--accent)' : 'var(--surface)',
    color: on ? 'var(--accent-ink)' : 'var(--ink-2)',
  }
}

function LifeRow({ big, children }: { big: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', fontSize: 'var(--text-xs)', color: 'var(--ink-2)' }}>
      <b className="big" style={{ fontSize: 'var(--text-md)', minWidth: 58 }}>{big}</b>
      <span>{children}</span>
    </div>
  )
}

function MonthBar({ rent, living, net }: { rent: number; living: number; net: number }) {
  const left = Math.max(0, net - rent - living)
  const total = Math.max(net, rent + living)
  const w = (v: number) => `${(v / total) * 100}%`
  return (
    <>
      <div style={{ display: 'flex', height: 30, borderRadius: 'var(--radius-md)', overflow: 'hidden', margin: '7px 0 10px', fontSize: 'var(--text-2xs)', color: '#fff' }}>
        <span style={{ flexBasis: w(rent), background: 'var(--warn)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{money(rent)}</span>
        <span style={{ flexBasis: w(living), background: 'var(--note)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{money(living)}</span>
        <span style={{ flex: 1, background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{money(left)} stays with you</span>
      </div>
      <Row color="var(--warn)" label="Rent — a one-bedroom, outside the centre" value={money(rent)} />
      <Row color="var(--note)" label="Everything else — food, transport, phone, fun" value={money(living)} />
      <Row color="var(--accent)" label="Left over, if you live like this" value={money(left)} />
    </>
  )
}

function Row({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', padding: '3px 0' }}>
      <span><span style={{ color }}>■</span> {label}</span>
      <b className="tnum" style={{ color: 'var(--ink-1)' }}>{value}</b>
    </div>
  )
}

function Journey({ cc, pr, cit, route, dual }:
  { cc: string; pr: number | null; cit: number | null; route?: string; dual: { allowed: boolean | null; note?: string } }) {
  if (pr == null) {
    return (
      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--warn)', marginTop: 8 }}>
        {cc === 'AE'
          ? 'There is no permanent-residency or citizenship path here. Long stays run on renewable work or golden visas, tied to employment.'
          : 'No permanent path recorded for this country.'}
      </p>
    )
  }
  const span = Math.max(cit ?? pr, pr)
  return (
    <>
      <div style={{ position: 'relative', height: 4, background: 'var(--line)', borderRadius: 2, margin: '22px 0 8px' }}>
        <div style={{ position: 'absolute', inset: '0 auto 0 0', width: `${(pr / span) * 100}%`, background: 'var(--accent)', borderRadius: 2 }} />
        {[0, (pr / span) * 100, 100].map((left, i) => (
          <span key={i} style={{
            position: 'absolute', left: `${left}%`, top: '50%', transform: 'translate(-50%,-50%)',
            width: 14, height: 14, borderRadius: '50%',
            background: i === 0 ? 'var(--accent)' : 'var(--surface)',
            border: `3px solid ${i === 2 ? 'var(--ink-3)' : 'var(--accent)'}`,
          }} />
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10, marginTop: 14 }}>
        <Stop title="YEAR 0 — ARRIVE">
          You land on a work visa{route ? ` — typically the ${route}` : ''}.
        </Stop>
        <Stop title={`~YEAR ${pr} — STAY FOR GOOD`}>
          Permanent residency. You stop depending on an employer to remain.
        </Stop>
        {cit != null && (
          <Stop title={`~YEAR ${cit} — PASSPORT`} last>
            Citizenship. {dual.allowed
              ? 'You keep your existing passport.'
              : dual.allowed === false
                ? 'Dual citizenship is normally not permitted here.'
                : ''}
          </Stop>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <FlagRibbon cc={cc} width={Math.max(14, pr * 9)} />
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
          Flag ribbon = time to residency; the dashes continue to citizenship.
        </span>
      </div>
    </>
  )
}

function Stop({ title, children, last }: { title: string; children: React.ReactNode; last?: boolean }) {
  return (
    <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', lineHeight: 1.5 }}>
      <b style={{ display: 'block', color: last ? 'var(--ink-3)' : 'var(--accent)', fontWeight: 600, marginBottom: 2 }}>
        {title}
      </b>
      {children}
    </div>
  )
}

/** At most three chips, each a full plain-language statement. */
function buildChips(country: { id: string; citizenship_years_typical: number | null; dual_citizenship: { allowed: boolean | null }; visa: { study_pathway?: { masters_tuition_intl_usd_yr: number | null }; iran_friction?: { level: string } } }) {
  const chips: { text: string; tone: string }[] = []

  if (country.citizenship_years_typical != null) {
    chips.push({
      tone: 'chip-ok',
      text: country.dual_citizenship.allowed
        ? `A passport in about ${country.citizenship_years_typical} years — and you keep your current one`
        : `A passport in about ${country.citizenship_years_typical} years`,
    })
  } else {
    chips.push({ tone: 'chip-risk', text: 'There is no path to citizenship here, however long you stay' })
  }

  const tuition = country.visa.study_pathway?.masters_tuition_intl_usd_yr
  if (tuition === 0) {
    chips.push({ tone: 'chip-ok', text: 'University is nearly free, even for international students' })
  } else if (tuition != null && tuition > 30000) {
    chips.push({ tone: 'chip-note', text: `Studying here costs around ${money(tuition)} a year` })
  }

  if (country.visa.iran_friction?.level === 'high') {
    chips.push({ tone: 'chip-risk', text: 'Iranian passport holders face long extra security checks here' })
  }

  return chips.slice(0, 3)
}
