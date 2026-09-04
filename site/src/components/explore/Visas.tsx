/* Visas & staying — the theme with no trend lines, on purpose.
 *
 * Everything here comes from core.json, which is already loaded, so this theme
 * costs no extra request. Nothing is fetched, nothing is extrapolated, and no
 * curve is fitted: visa rules move by decree.
 */

import { Flag } from '../Flag'
import { useData } from '../../data/store'
import { ChartFoot, type HeroStat } from './Controls'
import { money } from '../../data/format'
import type { Country } from '../../data/types'

/** What the design annotates beside a country's ribbon. */
const NOTE: Record<string, string> = {
  US: ' · ⚑ lottery + Iran ban',
  QA: ' · no citizenship',
  AE: 'golden visa only — no citizenship path',
}

/** The mockup writes these three as constants. They are derived here instead,
 *  from the same country records the ribbons draw, so the headline cannot drift
 *  away from the rows underneath it. */
export function visaHero(countries: Country[]): HeroStat[] {
  const withPr = countries.filter((k) => k.pr_years_typical != null)
  const fastest = withPr.reduce((a, b) => (a.pr_years_typical! <= b.pr_years_typical! ? a : b))
  const de = countries.find((k) => k.id === 'DE')
  const noPath = countries.filter((k) => k.citizenship_years_typical == null)
  return [
    { value: fastest.pr_years_typical, format: (v) => `~${v} yrs`,
      label: `fastest road to permanent residency — ${fastest.name}`, source: 'Express Entry' },
    { value: de?.citizenship_years_typical ?? null, format: (v) => `~${v} yrs`,
      label: 'arrival to a German passport — dual allowed', source: 'since 2024' },
    { value: noPath.length, format: (v) => String(Math.round(v)),
      label: 'countries with no citizenship path at all',
      source: noPath.map((k) => k.name.replace('United Arab Emirates', 'UAE')).join(' · ') },
  ]
}

export function VisasTheme() {
  const data = useData()
  const rows = [...data.countries].sort((a, b) => {
    const ap = a.pr_years_typical ?? 999
    const bp = b.pr_years_typical ?? 999
    return ap - bp
  })

  return (
    <>
      <div className="panel s6" style={{ borderStyle: 'solid' }}>
        <h2>No trend lines here, on purpose</h2>
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', lineHeight: 'var(--leading-relaxed)', marginTop: 6 }}>
          Visa rules change by decree, not by trend — a curve fitted to thresholds would imply they
          drift smoothly, and they don’t. So this theme holds today’s rules, dated, warned when stale.
          The history that matters is on the country pages, in words.
        </p>
      </div>

      <div className="panel s3">
        <h2>Years to security, today</h2>
        <div className="sub">
          Flag ribbon = typical years to permanent residency; dashes continue to
          citizenship. The same bars answer question four on the home field.
        </div>
        <div>
          {rows.map((k) => {
            const pr = k.pr_years_typical
            const cit = k.citizenship_years_typical
            if (pr == null) {
              return (
                <div className="vrow" key={k.id}>
                  <span className="nm">{k.name}</span>
                  <span aria-hidden="true" style={{
                    width: 16, height: 10, border: '1.5px dashed var(--ink-3)', borderRadius: 4, flex: 'none',
                  }} />
                  <b><em>{NOTE[k.id] ?? 'no permanent path'}</em></b>
                </div>
              )
            }
            return (
              <div className="vrow" key={k.id}>
                <span className="nm">{k.name}</span>
                <span className="ribbon-grow" style={{ display: 'inline-flex', flex: 'none' }}>
                  <FlagBar cc={k.id} width={Math.max(12, pr * 10)} />
                </span>
                {cit != null && cit > pr && (
                  <span className="ext" aria-hidden="true" style={{ width: (cit - pr) * 10 }} />
                )}
                <b>
                  ~{pr}{cit != null ? ` → ~${cit}` : ''} yrs
                  {NOTE[k.id] && <em>{NOTE[k.id]}</em>}
                </b>
              </div>
            )
          })}
        </div>
      </div>

      <Thresholds countries={data.countries} />
    </>
  )
}

function FlagBar({ cc, width }: { cc: string; width: number }) {
  return (
    <span style={{
      display: 'inline-block', width, height: 12, borderRadius: 6, overflow: 'hidden', flex: 'none',
    }}>
      <span style={{ display: 'block', width: '100%', height: '100%', transform: 'scaleX(4)', transformOrigin: 'left' }}>
        <Flag cc={cc} size={12} />
      </span>
    </span>
  )
}

/** Every salary floor on one ruler, in the same dollars the pay charts use.
 *  Countries with no floor are named rather than dropped: running on points is
 *  a fact about the route, not a missing number. */
function Thresholds({ countries }: { countries: Country[] }) {
  const rows = countries.map((k) => {
    // The cheapest door in, not just the first route on file: some countries
    // (AE) list a no-floor route before a route that does carry a threshold,
    // which would otherwise misreport the country as having no floor at all.
    const route = (k.visa?.skilled_routes ?? []).reduce<
      NonNullable<Country['visa']>['skilled_routes'][number] | null
    >((cheapest, r) => {
      if (r.salary_threshold_usd == null) return cheapest
      if (cheapest == null || r.salary_threshold_usd < cheapest.salary_threshold_usd!) return r
      return cheapest
    }, null)
    return {
      cc: k.id,
      name: k.name,
      route: route?.name ?? null,
      usd: route?.salary_threshold_usd ?? null,
      asOf: k.as_of,
    }
  })
  const has = rows.filter((r) => r.usd != null).sort((a, b) => a.usd! - b.usd!)
  const nulls = rows.filter((r) => r.usd == null)

  const W = 620
  const H = 150
  const PL = 14
  const PR = 14
  const X = (v: number) => PL + (v / 130000) * (W - PL - PR)

  // Simple lane packing so close floors do not sit on top of each other.
  const lanes: { x: number; lane: number }[] = []
  const placed = has.map((r) => {
    const x = X(r.usd!)
    let lane = 0
    while (lanes.some((l) => l.lane === lane && Math.abs(l.x - x) < 26)) lane++
    lanes.push({ x, lane })
    const y = H / 2 + 6 + (lane % 2 ? 18 : -2) * (lane > 1 ? 1.4 : 1)
    return { ...r, x, y }
  })

  return (
    <div className="panel s3">
      <h2>The price of the door</h2>
      <div className="sub">
        Every salary floor on one ruler — the same dollars the pay charts use.
        Countries with no floor run on points or sponsorship instead, and say so.
      </div>
      <div className="chart ruler">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Minimum salary thresholds for skilled work visas">
          {[[25000, '$25k'], [50000, '$50k'], [75000, '$75k'], [100000, '$100k'], [125000, '$125k']].map(([v, l]) => (
            <g key={String(v)}>
              <line x1={X(v as number)} x2={X(v as number)} y1={26} y2={H - 22} className="gridline" />
              <text x={X(v as number)} y={H - 8} fontSize="10" fill="var(--ink-3)" textAnchor="middle">{l}</text>
            </g>
          ))}
          {placed.map((p) => (
            <g key={p.cc}>
              <title>{`${p.name} — ${p.route ?? ''}: ${money(p.usd)}/yr`}</title>
              <text x={p.x} y={p.y - 13} fontSize="9.5" fill="var(--ink-2)" textAnchor="middle">{p.cc}</text>
              <circle cx={p.x} cy={p.y} r={8.5} fill="var(--surface)" stroke="var(--line-strong)" />
            </g>
          ))}
        </svg>
        <div className="dots" aria-hidden="true">
          {placed.map((p) => (
            <span key={p.cc} style={{ left: `${(p.x / W) * 100}%`, top: `${(p.y / H) * 100}%` }}>
              <Flag cc={p.cc} size={14} />
            </span>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
        {nulls.map((r) => (
          <span key={r.cc} className="chip chip-quiet" style={{ display: 'inline-flex', gap: 5, alignItems: 'center' }}>
            <Flag cc={r.cc} size={11} />
            {r.name} — points or sponsorship, no salary floor
          </span>
        ))}
      </div>
      <ChartFoot>
        <span className="chip chip-ok">● Official · national immigration sites</span>
        <span className="chip chip-quiet">each figure carries its date — staleness warns at 6 months</span>
      </ChartFoot>
    </div>
  )
}
