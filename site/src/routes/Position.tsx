/* Package 10 — profile, position, estimate: "the site does not estimate a
 * person, it locates them." A short form (Tier 1), a sourced position
 * (Tier 2, <Figure>), a modelled estimate beside it (Tier 3, <Derived>),
 * pay run through the site's existing cost machinery (Tier 4), and a
 * coverage map naming what the feature can and cannot do per country
 * (Tier 5). No AI, no network beyond the site's own JSON, no personal data
 * leaves the browser — package 12's CV reader is the only thing that adds
 * any of those, and it fills this same form, never a different one.
 */

import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useData } from '../data/store'
import { loadOccupations, type Occupations } from '../data/store'
import { loadWages, type WageCountry } from '../data/explore'
import {
  loadExperienceGradient, profileFromParams, profileToParams, computePosition,
  computeEstimate, computeEstimateUsdYear, knownPercentilePoints, DEFAULT_OCCUPATION, type Profile,
} from '../data/profile'
import { useAsync } from '../components/explore/useAsync'
import { Figure } from '../components/Figure'
import { Derived } from '../components/Derived'
import { Gap, ChartSkeleton } from '../components/explore/Controls'
import { Flag } from '../components/Flag'
import { useSelection } from '../data/selection'
import { stabilityOf, yearsToHome, savingsPerYear, type Budget } from '../data/compute'
import { years as fmtYearsToHome, NO_DATA } from '../data/format'
import { UnstableMark } from '../components/Unstable'

const PERIOD_LABEL = { hour: '/hour', month: '/month', year: '/year' } as const

function fmtNative(v: number | null, currency: string): string {
  if (v == null) return NO_DATA
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(v)
  } catch {
    return `${Math.round(v).toLocaleString()} ${currency}`
  }
}

function ordinal(pct: number): string {
  const r = Math.round(pct)
  return `P${r}`
}

/* ------------------------------------------------------------- gates --- */

/** Tier 5: what this feature can do for a country, cross-checked against
 *  what the resolver actually returned — not asserted separately from it
 *  (gate 11's own requirement).
 *
 *  Position and estimate both need exactly two things to work at all:
 *  scripts/crosswalk.py's own comparability verdict, AND a real percentile
 *  spread (>=2 of p10/p25/median/p75/p90) to place a rank within or clamp
 *  an estimate against. Those are two INDEPENDENT reasons a country can be
 *  excluded — an earlier version of this function collapsed them into one
 *  three-tier scheme labelled by distribution shape ("4-digit match" /
 *  "quartile-only match"), which meant a country refused by the crosswalk
 *  at 2-digit depth but still publishing a full percentile spread (Spain)
 *  rendered the self-contradictory "4-digit match, ES forced 4-digit down
 *  to 2-digit" — the tier name and the reason it was demoted described two
 *  different things. Finding F6, adversarial review. Reporting both
 *  verdicts separately removes the contradiction structurally rather than
 *  wording around it. */
function coverageFor(row: WageCountry | undefined, absentReason: string | undefined): {
  works: boolean; crosswalkOk: boolean; crosswalkDetail: string; distributionDetail: string
} {
  if (!row) {
    return { works: false, crosswalkOk: false, crosswalkDetail: absentReason ?? 'no wage source at all', distributionDetail: '—' }
  }
  const crosswalkOk = row.crosswalk.comparable
  const crosswalkDetail = crosswalkOk
    ? `${row.crosswalk.depth}-digit match${row.crosswalk.degraded_by ? ` (${row.crosswalk.degraded_by})` : ''}`
    : row.crosswalk.reason
  const d = row.native.distribution
  const hasSpread = d === 'full' || d === 'quartile-only'
  const distributionDetail = hasSpread
    ? d.replace(/-/g, ' ')
    : `${row.source_id} publishes only a ${d.replace(/-/g, ' ')} — no spread to rank or shift against`
  return { works: crosswalkOk && hasSpread, crosswalkOk, crosswalkDetail, distributionDetail }
}

/* --------------------------------------------------------------- form --- */

function ProfileForm({ profile, occupations, onChange }: {
  profile: Profile; occupations: Occupations | null
  onChange: (patch: Partial<Profile>) => void
}) {
  const options = occupations
    ? Object.entries(occupations.shared_keys).sort((a, b) => a[1].level - b[1].level || a[1].title.localeCompare(b[1].title))
    : []

  return (
    <div className="panel">
      <h2>Where do you sit?</h2>
      <div className="sub">Three fields, no network beyond this site's own data, updates as you type.</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginTop: 12 }}>
        <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
          Occupation
          <select
            value={profile.occupation}
            onChange={(e) => onChange({ occupation: e.target.value })}
            style={{
              display: 'block', width: '100%', marginTop: 4, padding: '7px 8px',
              border: '1px solid var(--line)', background: 'var(--surface)',
              borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', color: 'var(--ink-1)',
            }}
          >
            {options.map(([key, meta]) => (
              <option key={key} value={key}>
                {meta.title} ({meta.level === 4 ? '4-digit' : meta.level === 2 ? '2-digit only' : 'major group only'})
                {key !== 'isco08:2512' ? ' — no wage data resolved yet' : ''}
              </option>
            ))}
          </select>
          {profile.occupation !== DEFAULT_OCCUPATION && (
            <span style={{ display: 'block', marginTop: 4, color: 'var(--warn)', fontSize: 'var(--text-2xs)' }}>
              Only Software developers (isco08:2512) has resolved wage data as of this package — every
              other occupation will show as absent below. See NEEDS-DECISION.md.
            </span>
          )}
        </label>

        <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
          Years of professional experience
          <input
            type="number" min={0} max={50} step={0.5}
            value={profile.yearsProfessional}
            onChange={(e) => {
              const v = Number(e.target.value)
              if (Number.isFinite(v) && v >= 0) onChange({ yearsProfessional: v })
            }}
            style={{
              display: 'block', width: '100%', marginTop: 4, padding: '7px 8px',
              border: '1px solid var(--line)', background: 'var(--surface)',
              borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', color: 'var(--ink-1)',
            }}
          />
        </label>

        <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
          Where you are now (optional)
          <select
            value={profile.country ?? ''}
            onChange={(e) => onChange({ country: e.target.value || undefined })}
            style={{
              display: 'block', width: '100%', marginTop: 4, padding: '7px 8px',
              border: '1px solid var(--line)', background: 'var(--surface)',
              borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', color: 'var(--ink-1)',
            }}
          >
            <option value="">Not specified</option>
            {['AE', 'AU', 'CA', 'DE', 'DK', 'ES', 'FI', 'GB', 'IE', 'IT', 'NL', 'NO', 'QA', 'SE', 'US'].map((cc) => (
              <option key={cc} value={cc}>{cc}</option>
            ))}
          </select>
          <span style={{ display: 'block', marginTop: 4, color: 'var(--ink-3)', fontSize: 'var(--text-2xs)' }}>
            Highlights that row below. Not joined into "pay against cost" — pick actual cities there.
          </span>
        </label>
      </div>
      <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 10 }}>
        No submit button — the position and estimate below update live. This form works with the
        network disabled after the page has loaded once.
      </p>
    </div>
  )
}

/* ---------------------------------------------------------- one row --- */

function CountryRow({ row, profile, gradient, highlighted }: {
  row: WageCountry; profile: Profile
  gradient: NonNullable<ReturnType<typeof useAsync<Awaited<ReturnType<typeof loadExperienceGradient>>>>['data']>
  highlighted: boolean
}) {
  const position = computePosition(profile, row, gradient)
  const estimate = computeEstimate(profile, row, gradient)
  const [iso] = row.country.split('-')

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr 1fr', gap: 12, alignItems: 'baseline',
      padding: '10px 0', borderTop: '1px solid var(--line)',
      background: highlighted ? 'var(--surface-raised)' : undefined }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 'var(--text-xs)', fontWeight: 600 }}>
        <Flag cc={iso!} size={14} /> {row.country}
      </div>
      <div>
        {position.ok ? (
          <Figure source={{
            name: position.sourceLabel, asOf: String(position.year), confidence: 'official',
            what: `${row.country} has no experience cross of its own — this is the published median `
              + '(P50), not personalised to your years of experience.',
          }}>
            <span className="big" style={{ fontSize: 'var(--text-md)' }}>
              {ordinal(position.pct)} of {row.national_code}
            </span>
          </Figure>
        ) : (
          <span className="nodata" style={{ fontSize: 'var(--text-2xs)' }}>{position.reason}</span>
        )}
        {position.ok && (
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
            {position.n != null ? `n = ${position.n.toLocaleString()} · ` : ''}{position.year}
          </div>
        )}
      </div>
      <div>
        {estimate.ok ? (
          <Derived chain={estimate.chain} result={{ value: estimate.value, currency: estimate.currency }}>
            <span className="big" style={{ fontSize: 'var(--text-md)' }}>
              {fmtNative(estimate.value, estimate.currency)}{PERIOD_LABEL[row.native.period]}
            </span>
          </Derived>
        ) : (
          <span className="nodata" style={{ fontSize: 'var(--text-2xs)' }}>{estimate.reason}</span>
        )}
      </div>
    </div>
  )
}

/* --------------------------------------------------------- pay v cost --- */

function PayVsCost({ profile, wageByCountry, gradient }: {
  profile: Profile
  wageByCountry: Map<string, WageCountry>
  gradient: NonNullable<ReturnType<typeof useAsync<Awaited<ReturnType<typeof loadExperienceGradient>>>>['data']>
}) {
  const data = useData()
  const sel = useSelection()
  const cities = sel.ids.map((id) => data.cityById.get(id)).filter((c) => c != null)

  if (cities.length === 0) {
    return (
      <div className="panel">
        <h2>Pay against cost</h2>
        <p className="nodata" style={{ marginTop: 8 }}>
          Pick cities on <Link to="/compare">Compare</Link> or the map to see your estimate run through
          net pay, rent and living costs here.
        </p>
      </div>
    )
  }

  return (
    <div className="panel">
      <h2>Pay against cost</h2>
      <div className="sub">Your estimate, run through the same net → savings → years-to-home this site already computes.</div>
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {cities.map((city) => {
          const row = wageByCountry.get(city.country)
          const est = row ? computeEstimateUsdYear(profile, row, gradient) : null
          if (!est || !est.ok) {
            // Named, not just absent — gate 5's own "excluded by pay basis, with
            // the on-screen reason" requirement, distinct from a crosswalk-depth
            // or distribution-depth exclusion (each has its own real cause).
            const reason = !row
              ? `no wage distribution at all for ${city.country}`
              : !row.crosswalk.comparable
                ? row.crosswalk.reason
                : knownPercentilePoints(row.native.value).length < 2
                  ? `${row.source_id} publishes only a ${row.native.distribution.replace(/-/g, ' ')} — no spread to shift an estimate against`
                  : `${city.country}'s pay composition is unverified (neither regular_pay nor total_earnings — see pay_composition.json), so no USD figure can be run through cost-of-living`
            return (
              <div key={city.id} style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-3)' }}>
                <Flag cc={city.country} size={12} /> {city.name}: {reason}.
              </div>
            )
          }
          const budget: Budget = { salaryUsdYearOverride: est.value }
          const y = yearsToHome(city, 'mid', budget)
          const savings = savingsPerYear(city, 'mid', budget)
          const stability = stabilityOf(city, 'mid', budget)
          const never = savings != null && savings <= 0
          return (
            <div key={city.id} style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 'var(--text-xs)', flexWrap: 'wrap' }}>
              <Flag cc={city.country} size={14} /><b>{city.name}</b>
              <span style={{ color: 'var(--ink-2)' }}>
                {/* Wraps the whole chain (clamp, basis-fallback disclosure) in a
                    real method card instead of discarding it — an earlier version
                    rendered this as plain text, so Denmark's own clamp and Spain's
                    own total_earnings-basis substitution were computed but never
                    shown, contradicting computeEstimateUsdYear's own "never
                    silent" doc comment. Finding F4, adversarial review. */}
                <Derived chain={est.chain} result={{ value: est.value, currency: est.currency }}>
                  {fmtNative(est.value, est.currency)}/yr ({row!.native.year})
                </Derived>
                {' → '}
                {savings != null ? `${fmtNative(Math.round(savings), 'USD')} saved/yr` : NO_DATA} →{' '}
                {fmtYearsToHome(y, never)}
              </span>
              {stability === 'unstable' && <UnstableMark city={city} band="mid" budget={budget} />}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------- coverage --- */

function CoverageMap({ wages }: { wages: Awaited<ReturnType<typeof loadWages>> }) {
  // Canada carries two rows (CA-21231, CA-21232 — NEEDS-DECISION #12, still
  // open) rather than one plain "CA" — coverageFor() needs SOME row to
  // judge, so this takes the first. Not a resolution of #12 (which row
  // "represents" Canada is still undecided); just avoids the coverage map
  // wrongly claiming Canada has no wage distribution at all when it has
  // two full ones, which an earlier version of this map did by filtering
  // out every dash-suffixed row entirely — caught reading the map's own
  // live output against what wage_distribution.json actually carries.
  const byCountry = new Map<string, WageCountry>()
  for (const r of wages.countries) {
    const iso = r.country.split('-')[0]!
    if (!byCountry.has(iso)) byCountry.set(iso, r)
  }
  const absentByCountry = new Map(wages.absent.map((a) => [a.country, a.reason]))
  const ALL_15 = ['AE', 'AU', 'CA', 'DE', 'DK', 'ES', 'FI', 'GB', 'IE', 'IT', 'NL', 'NO', 'QA', 'SE', 'US']
  const rows = ALL_15.map((cc) => ({ cc, ...coverageFor(byCountry.get(cc), absentByCountry.get(cc)) }))
  const works = rows.filter((r) => r.works)
  const blocked = rows.filter((r) => !r.works)

  return (
    <div className="panel" style={{ gridColumn: '1 / -1' }}>
      <h2>Where this feature actually works</h2>
      <div className="sub">
        Everything packages 7–9 learned about occupation and distribution depth, applied to this one
        feature. This map describes Software developers (isco08:2512) specifically — the only
        occupation with resolved wage data — regardless of which occupation is currently selected
        above, since every other selection has no coverage to describe yet (see the panel above).
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14, marginTop: 10 }}>
        <div>
          <h3 style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)' }}>
            Position + estimate work ({works.length})
          </h3>
          <ul style={{ listStyle: 'none', padding: 0, margin: '6px 0 0' }}>
            {works.map((r) => (
              <li key={r.cc} style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 3 }}>
                <Flag cc={r.cc} size={11} /> <b style={{ color: 'var(--ink-2)' }}>{r.cc}</b> — {r.crosswalkDetail}, {r.distributionDetail}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)' }}>
            Neither works ({blocked.length})
          </h3>
          <ul style={{ listStyle: 'none', padding: 0, margin: '6px 0 0' }}>
            {blocked.map((r) => (
              <li key={r.cc} style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 3 }}>
                <Flag cc={r.cc} size={11} /> <b style={{ color: 'var(--ink-2)' }}>{r.cc}</b> —{' '}
                {r.crosswalkOk ? r.distributionDetail : r.crosswalkDetail}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- page --- */

export function Position() {
  const [params, setParams] = useSearchParams()
  const profile = profileFromParams(params)

  const update = useCallback((patch: Record<string, string | null>) => {
    setParams((cur) => {
      const next = new URLSearchParams(cur)
      for (const [k, v] of Object.entries(patch)) { if (v == null) next.delete(k); else next.set(k, v) }
      return next
    }, { replace: true })
  }, [setParams])

  const onProfileChange = useCallback((patch: Partial<Profile>) => {
    update(profileToParams({ ...profile, ...patch }))
  }, [profile, update])

  // useAsync's own contract: "say so honestly when it fails... silence would
  // read as empty" (site/src/components/explore/useAsync.ts). An earlier
  // version of this page destructured only `data`, so a failed fetch left a
  // permanent skeleton or an empty <select> with no explanation — finding
  // F16, adversarial review.
  const { data: wages, error: wagesError } = useAsync(loadWages, 'wages')
  const { data: gradient, error: gradientError } = useAsync(loadExperienceGradient, 'gradient')
  const { data: occupations, error: occupationsError } = useAsync(loadOccupations, 'occupations')
  const loadError = wagesError ?? gradientError ?? occupationsError

  // Keyed by ISO prefix so Canada's two NOC-code rows (CA-21231, CA-21232 —
  // NEEDS-DECISION #12, still open) resolve to a real row instead of
  // silently having none: the first one found, not a resolution of which
  // code "is" Canada.
  const wageByCountry = useMemo(() => {
    const m = new Map<string, WageCountry>()
    for (const r of wages?.countries ?? []) {
      const iso = r.country.split('-')[0]!
      if (!m.has(iso)) m.set(iso, r)
    }
    return m
  }, [wages])

  const supported = profile.occupation === DEFAULT_OCCUPATION

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <h1 style={{ fontSize: 'var(--text-xl)' }}>Your position</h1>
      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)', padding: '8px 0 12px', maxWidth: '72ch' }}>
        The site does not estimate a person — it locates you in the wage distributions packages 7–9
        already built. A position is a rank within a country's own published table; an estimate is
        this pipeline's own model, always shown beside its distribution, never mistaken for a
        measurement.
      </p>

      {loadError && (
        <div className="panel" style={{ borderColor: 'var(--warn)' }}>
          <h2>The data didn't load</h2>
          <p style={{ color: 'var(--ink-2)', marginTop: 8 }}>{loadError}</p>
        </div>
      )}

      <ProfileForm profile={profile} occupations={occupations} onChange={onProfileChange} />

      <div className="panel" style={{ marginTop: 12 }}>
        <h2>Position and estimate, country by country</h2>
        <div className="sub">Position: this country's own published percentile table. Estimate: that table's own median, shifted by the experience gradient — always labelled, never a source citation.</div>
        {!wages || !gradient ? (
          <ChartSkeleton height={220} />
        ) : !supported ? (
          <Gap title="No wage data resolved for this occupation yet" span="s6">
            <p>
              This pipeline has only resolved wage distributions for Software developers (isco08:2512)
              as of package 10 — every other occupation the crosswalk can name is a real, checked
              mapping (see the Data & methods page), but none has a harvested wage table behind it yet.
              Switch back to Software developers to see real positions and estimates.
            </p>
          </Gap>
        ) : (
          <div style={{ marginTop: 6 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '90px 1fr 1fr', gap: 12, fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', paddingBottom: 6 }}>
              <span /><span>Position</span><span>Estimate</span>
            </div>
            {wages.countries.map((row) => (
              <CountryRow key={row.country} row={row} profile={profile} gradient={gradient}
                highlighted={profile.country != null && row.country.split('-')[0] === profile.country} />
            ))}
            {wages.absent.length > 0 && (
              <Gap title={`${wages.absent.length} countries don't appear above`} span="s6"
                where={<>Full account in <Link to="/data">NEEDS-DECISION.md →</Link></>}>
                <p>{wages.absent.map((a) => `${a.country} — ${a.reason}`).join('; ')}. Absence drawn, not implied by a missing row.</p>
              </Gap>
            )}
          </div>
        )}
      </div>

      <div style={{ marginTop: 12 }}>
        {wages && gradient && supported && <PayVsCost profile={profile} wageByCountry={wageByCountry} gradient={gradient} />}
      </div>

      <div style={{ marginTop: 12 }}>
        {wages && <CoverageMap wages={wages} />}
      </div>
    </div>
  )
}
