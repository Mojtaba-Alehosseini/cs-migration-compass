/* Country profile — stands alone, because a remote worker comparing places may
 * never care about a specific city. Carries the full jobs section and the
 * nationality-mix explorer. */

import { Link, useParams } from 'react-router-dom'
import { useState } from 'react'
import { Flag } from '../components/Flag'
import { Figure } from '../components/Figure'
import { Derived } from '../components/Derived'
import { useAsync } from '../components/explore/useAsync'
import { useData } from '../data/store'
import { asOfLabel, money, num, pct, rankOf, sourceName, NO_DATA } from '../data/format'
import { loadWages, CA_NOC_DISTINCTION, type WageCountry } from '../data/explore'
import { NotFound } from './NotFound'

const PERIOD_LABEL = { hour: '/hour', month: '/month', year: '/year' } as const

function fmtNative(v: number | null, currency: string): string {
  if (v == null) return NO_DATA
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(v)
  } catch {
    return `${Math.round(v).toLocaleString()} ${currency}`
  }
}

/** One country's native wage distribution — the SOURCE figure, rendered
 *  through <Figure>, EXCEPT Qatar: its "native" mean is this pipeline's own
 *  weighted average of PSA's separately-published Male/Female series (see
 *  build_wage_distribution.py's _extract_qa), a real derivation despite
 *  being in "native currency" — <Figure> claiming it as "as published"
 *  was adversarial review finding F15. Qatar renders through <Derived>
 *  instead, with the weighting made explicit as its own chain step. */
function WageRowFigure({ row }: { row: WageCountry }) {
  const n = row.native
  const spread = n.value.p10 != null && n.value.p90 != null
    ? `${fmtNative(n.value.p10, n.currency)} – ${fmtNative(n.value.p90, n.currency)}`
    : n.value.p25 != null && n.value.p75 != null
      ? `${fmtNative(n.value.p25, n.currency)} – ${fmtNative(n.value.p75, n.currency)} (p25–p75)`
      : null
  // FIXED (tier 7, adversarial review finding F14): a binary ternary treated
  // every distribution value that wasn't literally 'central-tendency-only'
  // as "Full distribution as published" — including 'mean-only' (Qatar,
  // UAE), which have neither a median nor any spread at all. Now names all
  // four shapes correctly.
  const distributionNote = {
    full: 'Full P10–P90 distribution as published.',
    'quartile-only': 'P25–P75 spread published; P10/P90 are not.',
    'central-tendency-only': 'Mean/median only, no percentile spread published.',
    'mean-only': 'A single mean only — no median, no spread published.',
  }[n.distribution]

  if (n.weighting_note) {
    return (
      <div style={{ marginTop: 10 }}>
        <Derived chain={[{ op: 'weighted_mean', detail: n.weighting_note }]}
          result={{ value: n.value.mean ?? 0, currency: n.currency }}>
          <span className="big" style={{ fontSize: 'var(--text-xl)' }}>
            {fmtNative(n.value.mean, n.currency)}{PERIOD_LABEL[n.period]}
          </span>
        </Derived>
        <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
          {n.n_employees != null ? `n = ${num(n.n_employees)} · ` : ''}{n.year}
        </div>
      </div>
    )
  }
  // Germany only (finding F6, adversarial review): this native figure is
  // regular_pay annualised at extraction, not Destatis's own published
  // annual number — <Figure> claiming "as published" would be the same
  // bug package 9 fixed for Qatar's weighted mean (weighting_note, above).
  if (n.annualised_note) {
    return (
      <div style={{ marginTop: 10 }}>
        <Derived chain={[{ op: 'annualise', detail: n.annualised_note }]}
          result={{ value: n.value.median ?? n.value.mean ?? 0, currency: n.currency }}>
          <span className="big" style={{ fontSize: 'var(--text-xl)' }}>
            {fmtNative(n.value.median ?? n.value.mean, n.currency)}{PERIOD_LABEL[n.period]}
          </span>
        </Derived>
        <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
          {n.n_employees != null ? `n = ${num(n.n_employees)} · ` : ''}{n.year}
        </div>
      </div>
    )
  }
  // Denmark only (package 10, tier 0.2): this native figure is DST's own
  // STANDARDIZED HOURLY EARNINGS concept (STAND), not the more commonly
  // reached-for FORINKL — named here because DST's own separately-published
  // monthly headline (MDRSNIT) confirms STAND, not FORINKL, is what
  // reconciles. See NEEDS-DECISION #17 and scripts/src_salary_dk.py.
  const mdrsnitNote = n.mdrsnit_check
    ? ` Matches Danmarks Statistik's own monthly headline (MDRSNIT): `
      + `${n.mdrsnit_check.stand_dkk_hour} DKK/standardised hour × 160.33h/month = `
      + `${Math.round(n.mdrsnit_check.computed_monthly).toLocaleString()} DKK, DST publishes `
      + `${Math.round(n.mdrsnit_check.published_mdrsnit).toLocaleString()} DKK `
      + `(${n.mdrsnit_check.residual_pct > 0 ? '+' : ''}${n.mdrsnit_check.residual_pct.toFixed(3)}%).`
    : ''
  return (
    <div style={{ marginTop: 10 }}>
      <Figure source={{
        name: row.source_id, what: `${distributionNote} `
          + (row.crosswalk.comparable && row.crosswalk.degraded_by ? row.crosswalk.degraded_by : '')
          + mdrsnitNote,
        asOf: String(n.year), confidence: 'official',
      }}>
        <span className="big" style={{ fontSize: 'var(--text-xl)' }}>
          {fmtNative(n.value.median ?? n.value.mean, n.currency)}{PERIOD_LABEL[n.period]}
        </span>
      </Figure>
      {spread && <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 3 }}>{spread}</div>}
      <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
        {n.n_employees != null ? `n = ${num(n.n_employees)} · ` : ''}{n.year}
      </div>
    </div>
  )
}

export function CountryProfile() {
  const { id } = useParams()
  const data = useData()
  const country = id ? data.countryById.get(id) : undefined
  if (!country) return <NotFound />

  const cities = data.citiesByCountry.get(country.id) ?? []
  const e = country.enriched
  const { data: wages } = useAsync(loadWages, 'wages')
  const wageRows = wages?.countries.filter((c) => c.country === country.id || c.country.startsWith(`${country.id}-`))
  const wageAbsence = wages?.absent.find((a) => a.country === country.id)

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Flag cc={country.id} size={24} title={`Flag of ${country.name}`} />
        <h1 style={{ fontSize: 'var(--text-xl)' }}>{country.name}</h1>
      </div>

      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)', padding: '8px 0 12px', maxWidth: '72ch' }}>
        {country.job_market.summary?.split('. ').slice(0, 2).join('. ')}.
      </p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
        {cities.map((c) => (
          <Link key={c.id} to={`/city/${c.id}`} className="chip chip-quiet" style={{ textDecoration: 'none' }}>
            {c.name}
          </Link>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12, padding: '12px 0' }}>

        <div className="panel">
          <h2>Getting in</h2>
          <div className="sub">Main skilled routes. These change often — each carries its date.</div>
          {country.visa.skilled_routes.map((r, i) => (
            <div key={i} style={{ marginTop: 10, paddingTop: 10, borderTop: i ? '1px solid var(--line)' : undefined }}>
              <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>{r.name}</div>
              <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginTop: 3 }}>{r.summary}</p>
              {r.salary_threshold_usd != null && (
                <span className="chip chip-note" style={{ marginTop: 6 }}>
                  Needs about {money(r.salary_threshold_usd)} a year · as of {asOfLabel(country.as_of)}
                </span>
              )}
            </div>
          ))}
          {country.visa.iran_friction && (
            <div className="chip chip-risk" style={{ marginTop: 10, display: 'block', lineHeight: 1.6 }}>
              <b>Iranian passport — {country.visa.iran_friction.level} friction.</b>{' '}
              {country.visa.iran_friction.notes.slice(0, 260)}…
            </div>
          )}
        </div>

        <div className="panel">
          <h2>Finding work</h2>
          <div className="sub">How big the tech job market actually is.</div>
          {e.ict_specialists ? (
            <>
              <div className="big" style={{ fontSize: 'var(--text-2xl)' }}>
                {num(e.ict_specialists.thousands * 1000)}
              </div>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
                people work in IT ({pct(e.ict_specialists.share_pct, 1)} of everyone with a job,{' '}
                {e.ict_specialists.year})
              </div>
              {e.total_employment && (
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginTop: 6 }}>
                  Out of {num(e.total_employment.thousands * 1000)} jobs in total.
                </div>
              )}
              <Link to="/explore/jobs" style={{ fontSize: 'var(--text-2xs)', display: 'inline-block', marginTop: 8 }}>
                See the 20-year trend →
              </Link>
            </>
          ) : (
            <p className="nodata" style={{ marginTop: 8 }}>
              No IT-employment count for {country.name}. Eurostat covers EU and EFTA countries only, and
              we do not substitute another source for it. Gulf jobs data in particular is thin.
            </p>
          )}
          <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginTop: 10 }}>
            {country.job_market.new_grad_reality}
          </p>
        </div>

        <div className="panel">
          <h2>What developers earn here</h2>
          <div className="sub">The primary software-developer occupation, in its own currency, as published.</div>
          {wageRows === undefined ? (
            <p className="nodata" style={{ marginTop: 8 }}>Loading…</p>
          ) : wageRows.length > 0 ? (
            wageRows.map((row) => (
              <div key={row.country} style={row.country !== wageRows[0]!.country
                ? { marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--line)' } : undefined}>
                {wageRows.length > 1 && (
                  <div style={{ fontSize: 'var(--text-2xs)', fontWeight: 600, color: 'var(--ink-2)' }}>
                    {row.national_code}
                  </div>
                )}
                <WageRowFigure row={row} />
                {CA_NOC_DISTINCTION[row.country] && (
                  <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 4, maxWidth: '60ch' }}>
                    {CA_NOC_DISTINCTION[row.country]}
                  </div>
                )}
              </div>
            ))
          ) : wageAbsence ? (
            <p className="nodata" style={{ marginTop: 8 }}>{wageAbsence.reason}</p>
          ) : (
            <p className="nodata" style={{ marginTop: 8 }}>No developer-wage figure for {country.name}.</p>
          )}
          <Link to="/explore/money" style={{ fontSize: 'var(--text-2xs)', display: 'inline-block', marginTop: 8 }}>
            Compare across countries →
          </Link>
        </div>

        <div className="panel">
          <h2>Who already lives there</h2>
          <div className="sub">People born in another country, and where they came from.</div>
          {e.foreign_born ? (
            <>
              <Figure source={{
                name: 'UN DESA ÷ World Bank', what: e.foreign_born.formula,
                asOf: String(e.foreign_born.year), confidence: 'official',
                url: 'https://www.un.org/development/desa/pd/content/international-migrant-stock',
              }}>
                <span className="big" style={{ fontSize: 'var(--text-2xl)' }}>{pct(e.foreign_born.share_pct, 1)}</span>
              </Figure>
              <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
                of the population was born abroad — {num(e.foreign_born.count)} people, {e.foreign_born.year}
              </div>
              {e.iranian_born && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', marginTop: 8 }}>
                  <b>{num(e.iranian_born.count)}</b> of them were born in Iran.
                </div>
              )}
              {e.top_origins && <OriginExplorer origins={e.top_origins} />}
            </>
          ) : (
            <p className="nodata">No migrant-stock figure for {country.name}.</p>
          )}
        </div>

        <div className="panel">
          <h2>Life, measured</h2>
          <div className="sub">Global indices translated into ranks with their denominator.</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: '6px 0 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <li style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)' }}>
              <b className="big" style={{ fontSize: 'var(--text-md)' }}>
                {rankOf(e.happiness?.rank ?? country.indices.whr_rank, e.happiness?.of ?? 147)}
              </b>{' '}for happiness
            </li>
            <li style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)' }}>
              <b className="big" style={{ fontSize: 'var(--text-md)' }}>{rankOf(country.indices.gpi_rank, 163)}</b>{' '}
              on the Global Peace Index
            </li>
            <li style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)' }}>
              <b className="big" style={{ fontSize: 'var(--text-md)' }}>
                {country.indices.hdi != null ? country.indices.hdi.toFixed(3) : NO_DATA}
              </b>{' '}Human Development Index
            </li>
            <li style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)' }}>
              <b className="big" style={{ fontSize: 'var(--text-md)' }}>
                {country.indices.ef_epi_score != null ? country.indices.ef_epi_band : 'native'}
              </b>{' '}English among locals
            </li>
          </ul>
          {country.indices.freedom_note && (
            <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginTop: 10, lineHeight: 1.6 }}>
              {country.indices.freedom_note}
            </p>
          )}
        </div>

        <div className="panel" style={{ gridColumn: '1 / -1' }}>
          <h2>The honest version</h2>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', lineHeight: 'var(--leading-relaxed)', marginTop: 6 }}>
            {country.reality_paragraph}
          </p>
          <div style={{ borderTop: '1px solid var(--line)', marginTop: 12, paddingTop: 9, fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
            {country.sources.length} sources · as of {asOfLabel(country.as_of)} ·{' '}
            {country.sources.slice(0, 4).map(sourceName).join(' · ')} ·{' '}
            <Link to="/data">all sources →</Link>
          </div>
        </div>
      </div>
    </div>
  )
}

/** "find people from …" — the nationality-mix explorer. */
function OriginExplorer({ origins }: { origins: { origin: string; value: number }[] }) {
  const [q, setQ] = useState('')
  const shown = q.length > 1
    ? origins.filter((o) => o.origin.toLowerCase().includes(q.toLowerCase()))
    : origins.slice(0, 6)
  const max = Math.max(...origins.map((o) => o.value), 1)

  return (
    <div style={{ marginTop: 12 }}>
      <input
        value={q} onChange={(e) => setQ(e.target.value)}
        placeholder="find people from…"
        aria-label="Find a country of origin"
        style={{
          width: '100%', border: '1px solid var(--line)', background: 'var(--surface)',
          borderRadius: 'var(--radius-sm)', padding: '7px 10px', fontSize: 'var(--text-2xs)', marginBottom: 8,
        }}
      />
      {shown.length === 0 && <p className="nodata">No recorded community from “{q}”.</p>}
      {shown.slice(0, 10).map((o) => (
        <div key={o.origin} style={{ margin: '5px 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
            <span>{o.origin}</span>
            <span className="tnum">{num(o.value)}</span>
          </div>
          <div style={{ height: 5, background: 'var(--surface-sunk)', borderRadius: 3, marginTop: 2 }}>
            <div style={{ height: '100%', width: `${(o.value / max) * 100}%`, background: 'var(--accent)', borderRadius: 3, opacity: 0.75 }} />
          </div>
        </div>
      ))}
    </div>
  )
}
