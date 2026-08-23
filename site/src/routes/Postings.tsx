/* Package 12, tier 5.2 — the postings panel. What employers ADVERTISE while
 * hiring, never confused with what this site's own wage spine (Explore ·
 * Money) says people ARE paid — a different quantity, drawn in a different
 * register, on a different page, from a different file (data/postings.ts,
 * never importing data/explore.ts). See postings.ts's own header for the
 * full account of that boundary.
 *
 * TAKEN from the reference the owner cited (j97.dev): filters (level,
 * location, category), a list <-> map toggle, a posted-salary column.
 *
 * REFUSED, on purpose, per the work order's own Tier 5.2:
 *   - a per-posting "estimated total comp" column — a fabricated estimate
 *     sitting in a table of real employer-stated ranges is exactly the
 *     number this project does not print. Where an employer stated
 *     nothing, the cell says so, in words, not a guess.
 *   - Bay-Area TC bands — banding comes from the distributions this site
 *     already publishes (Explore · Money), per country, never invented here.
 *   - a ranking. Filtering to postings matching a filter is a filter.
 *     Scoring which ones someone should apply to is a recommendation, and
 *     this site does not make those (see the footer strapline on every page:
 *     "we never rank places or tell you where to go" — postings get the
 *     identical discipline).
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAsync } from '../components/explore/useAsync'
import { useData } from '../data/store'
import { Flag } from '../components/Flag'
import { Gap, ChartSkeleton } from '../components/explore/Controls'
import { loadPostings, fmtCompensation, fmtCompany, PROVIDER_LABEL, type Posting } from '../data/postings'
import { LAND_PATH, LAND_VIEWBOX } from '../data/land'
import { project } from '../components/CityMap'

/** Package 12, tier 5.1's own `advertised` chart-kit mode needed a real chart
 *  to be visible on — the mode existed in engine.ts but nothing rendered it
 *  anywhere, found while gathering this package's own gate 9 evidence. Median
 *  advertised pay by country, annual-salary postings only, expressed in USD.
 *  Package 16 — countries below the floor are NO LONGER dropped server-side,
 *  and this comment used to say they were. They are all present in
 *  pay_summary_by_country carrying `publishable: false` and a `withheld_reason`,
 *  because "we harvested 21 GB postings and 13 of them are software" is a true
 *  and useful statement while a median of 13 is not. The floor itself is read
 *  from data.pay_summary_min_n (30), still never duplicated in this file.
 *
 *  Package 14: reads `data.pay_summary_by_country`, pre-computed at build
 *  time (build_postings.py) — this function used to scan the FULL raw
 *  `postings` array and sort each country's own values itself, which
 *  became a real, measured Lighthouse performance cost once this
 *  package's own postings recovery grew that array to 46,040 records.
 *  Same filter, same thresholds, same result shape; the expensive part
 *  just doesn't happen in the browser on every page load any more.
 *
 *  An earlier revision of this aggregate required native currency == USD,
 *  which meant every non-US country's own entry was quietly built from
 *  whichever of ITS postings a US-headquartered employer happened to quote
 *  in USD — a small, systematically biased subsample, not "no data" but
 *  worse (an independent adversarial review's own M8 finding). Fixed at
 *  the source (build_postings.py): every convertible currency now
 *  contributes, through the same year-matched FX conversion Tier 3.1
 *  already computes for every posting's own compensation.usd field — no
 *  new plumbing needed here, this file still never imports data/explore.ts
 *  or normalise.py directly. Only PERIOD is still restricted to annual —
 *  that conversion touches currency only, never period, so an hourly
 *  posting genuinely is a different quantity and stays excluded on
 *  purpose (disclosed below). */
/* Package 16 — advertisedByCountryCfg() removed, not disabled. It plotted a
 * median for every country with 5+ annual postings. docs/DATA-FITNESS.md §1
 * rules that claim unsupported: after de-duplicating and restricting to
 * software titles, exactly one of seven countries clears a defensible sample
 * floor, so a line ACROSS countries implies a comparison the data cannot make.
 * A function that can now only ever return null is worse than no function, so
 * it is gone; the panel below states the one country the evidence supports and
 * registers the rest as counts. */


/* Approximate capital/hub coordinates for the countries postings actually
 * resolve to (scripts/postings_common.py's own country_from_location table,
 * mirrored here for the map view only — a country DOT position, not a
 * precise posting location no source in this package ever publishes). A
 * country missing from this table still appears in the LIST view and in
 * the per-country counts; it just has no dot on the map, which is honestly
 * a map limitation, not a data one. */
const COUNTRY_LATLON: Record<string, [number, number]> = {
  US: [38.9, -77.0], GB: [51.5, -0.1], DE: [52.5, 13.4], FR: [48.9, 2.3], CA: [45.4, -75.7],
  IE: [53.3, -6.3], NL: [52.4, 4.9], ES: [40.4, -3.7], IT: [41.9, 12.5], SE: [59.3, 18.1],
  DK: [55.7, 12.6], NO: [59.9, 10.8], FI: [60.2, 24.9], AU: [-33.9, 151.2], IN: [19.1, 72.9],
  PL: [52.2, 21.0], PT: [38.7, -9.1], SG: [1.3, 103.8], JP: [35.7, 139.7], CN: [39.9, 116.4],
  HK: [22.3, 114.2], TW: [25.0, 121.6], KR: [37.6, 127.0], MY: [3.1, 101.7], ID: [-6.2, 106.8],
  TH: [13.8, 100.5], VN: [21.0, 105.8], PH: [14.6, 121.0], MX: [19.4, -99.1], BR: [-23.5, -46.6],
  AR: [-34.6, -58.4], CL: [-33.4, -70.7], CO: [4.7, -74.1], PE: [-12.0, -77.0], CH: [47.4, 8.5],
  AT: [48.2, 16.4], BE: [50.9, 4.3], PT2: [0, 0],
  QA: [25.3, 51.5], AE: [25.2, 55.3], ZA: [-26.2, 28.0], NZ: [-36.8, 174.8], IL: [32.1, 34.8],
}
delete COUNTRY_LATLON.PT2

const MAP = { LON0: -128, LON1: 157, LAT0: -45, LAT1: 62, W: LAND_VIEWBOX.w, H: LAND_VIEWBOX.h }

function fmtDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function levelGuess(title: string | null): 'intern' | 'junior' | 'senior' | 'staff+' | null {
  if (!title) return null
  const t = title.toLowerCase()
  if (/\bintern(ship)?\b/.test(t)) return 'intern'
  if (/\b(staff|principal|distinguished|director|head of|vp\b)/.test(t)) return 'staff+'
  if (/\b(senior|sr\.?|lead|iii|l3|l4)\b/.test(t)) return 'senior'
  if (/\b(junior|jr\.?|entry|graduate|new grad|associate|i\b)/.test(t)) return 'junior'
  return null
}
const LEVEL_LABEL = { intern: 'Intern', junior: 'Junior', senior: 'Senior', 'staff+': 'Staff+' } as const

function PostingRow({ p }: { p: Posting }) {
  const comp = fmtCompensation(p.compensation)
  return (
    <tr>
      <td style={{ padding: '7px 10px', fontSize: 'var(--text-xs)' }}>
        {p.country && <Flag cc={p.country} size={12} />}{' '}
        {/* HN's own company_slug is always the literal "hn" -- a provider
         *  placeholder, not a per-company token the way every other
         *  provider's slug is -- so fmtCompany() would prettify it into a
         *  meaningless "Hn" label rather than the honest "no distinct
         *  company identity here" the provider label already conveys. */}
        {p.provider === 'hn' ? (p.company ?? PROVIDER_LABEL[p.provider]) : fmtCompany(p.company, p.company_slug)}
      </td>
      <td style={{ padding: '7px 10px', fontSize: 'var(--text-xs)' }}>
        {p.url ? <a href={p.url} target="_blank" rel="noopener noreferrer">{p.title}</a> : p.title}
      </td>
      <td style={{ padding: '7px 10px', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
        {p.location_raw ?? (p.remote ? 'Remote' : NO_LOCATION)}
      </td>
      <td style={{ padding: '7px 10px', fontSize: 'var(--text-xs)', fontWeight: comp ? 600 : 400 }}
        title={p.compensation?.raw_text || undefined}>
        {comp || (
          <span style={{ color: 'var(--ink-3)', fontWeight: 400, fontStyle: 'italic' }}>
            not stated
          </span>
        )}
      </td>
      <td style={{ padding: '7px 10px', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>{fmtDate(p.posted_at)}</td>
    </tr>
  )
}
const NO_LOCATION = '—'

export function Postings() {
  const { data, error } = useAsync(loadPostings, 'postings')
  const core = useData()
  const [view, setView] = useState<'list' | 'map'>('list')
  const [countryFilter, setCountryFilter] = useState('')
  const [levelFilter, setLevelFilter] = useState('')
  const [query, setQuery] = useState('')
  const [remoteOnly, setRemoteOnly] = useState(false)

  const filtered = useMemo(() => {
    if (!data) return []
    return data.postings.filter((p) => {
      if (countryFilter && p.country !== countryFilter) return false
      if (levelFilter && levelGuess(p.title) !== levelFilter) return false
      if (remoteOnly && !p.remote) return false
      if (query.trim() && !p.title?.toLowerCase().includes(query.trim().toLowerCase())) return false
      return true
    })
  }, [data, countryFilter, levelFilter, remoteOnly, query])

  // Package 16 — the panel carries 85 countries this site does not cover, 17.1%
  // of the corpus. Listing them in one flat dropdown reads as coverage: nothing
  // told a reader that picking Poland gets postings but no city, no cost of
  // living, no tax model and no years-to-home. Split into two labelled groups so
  // the difference is visible without hiding data anyone might want.
  // NEEDS-DECISION.md #45 holds the actual scope question.
  const [inScope, outOfScope] = useMemo(() => {
    if (!data) return [[], []] as [[string, number][], [string, number][]]
    const covered = new Set(core.citiesByCountry.keys())
    const all = Object.entries(data.country_counts)
      .filter(([cc]) => cc !== 'unresolved')
      .sort((a, b) => b[1] - a[1]) as [string, number][]
    return [all.filter(([cc]) => covered.has(cc)), all.filter(([cc]) => !covered.has(cc))]
  }, [data, core])

  const mapDots = useMemo(() => {
    // Package 14 -- gated on view === 'map': this scans every one of
    // `filtered`'s own rows (up to the full postings count when no filter
    // is active -- 46,040 after this package's own recovery, package 12's
    // own 43,034) and runs a lat/lon projection per country. The JSX below
    // only ever renders these dots when view === 'map' (the SVG isn't in
    // the DOM otherwise), but this useMemo previously ran unconditionally
    // on every filter change regardless of which view was showing --
    // wasted work on the far more common 'list' default, measured live
    // contributing to a real Lighthouse performance regression this
    // package's own postings recovery surfaced (more real data to scan).
    if (view !== 'map') return []
    // Counted from `filtered`, not `data.country_counts` -- an earlier
    // version read the raw, unfiltered totals here, so switching to Map
    // view silently dropped every active filter (found live by this
    // package's own adversarial review: filtering the list to Qatar's own
    // 7 postings, then switching to Map, still drew all 42 countries'
    // worth of global dots). The list view already used `filtered`
    // correctly; this brings the map view in line with it.
    const counts = new Map<string, number>()
    for (const p of filtered) {
      if (!p.country) continue
      counts.set(p.country, (counts.get(p.country) ?? 0) + 1)
    }
    return [...counts.entries()]
      .filter(([cc]) => COUNTRY_LATLON[cc])
      .map(([cc, count]) => {
        const [lat, lon] = COUNTRY_LATLON[cc]!
        const { x, y } = project(lat, lon)
        return { cc, count, x, y }
      })
  }, [filtered, view])
  const maxDot = Math.max(1, ...mapDots.map((d) => d.count))

  // Package 16 — the caption used to read "one dot per resolved country", which
  // was never true: the coordinate table holds 42 countries and the panel
  // resolves 100, so 58 were silently dropped by the filter above. Widening
  // country resolution from 12.1% to 9.4% unresolved made it worse (74 -> 100
  // countries) without touching the table, which is what turned a quiet
  // inaccuracy into a visible one. Rather than assert a number that drifts, the
  // gap is computed from the same table the dots come from.
  const mapOmitted = useMemo(() => {
    const counts = new Map<string, number>()
    for (const p of data?.postings ?? []) {
      if (p.country) counts.set(p.country, (counts.get(p.country) ?? 0) + 1)
    }
    const missing = [...counts.entries()].filter(([cc]) => !COUNTRY_LATLON[cc])
    const total = [...counts.values()].reduce((s, k) => s + k, 0)
    const n = missing.reduce((s, [, k]) => s + k, 0)
    return {
      n,
      countries: missing.length,
      shownCountries: Object.keys(COUNTRY_LATLON).length,
      pct: total ? Math.round((100 * n) / total) : 0,
      largest: missing.sort((a, b) => b[1] - a[1]).slice(0, 3).map(([cc]) => cc),
    }
  }, [data])

  const providersAvailable = data ? Object.entries(data.provider_summary).filter(([, v]) => v.available) : []
  const withComp = data ? data.postings.filter((p) => p.compensation).length : 0
  // Package 16 — split once, here, so the panel and the withheld register can
  // never disagree about which countries qualify.
  const publishable = useMemo(
    () => (data?.pay_summary_by_country ?? []).filter((r) => r.publishable && r.median_published_usd_year != null),
    [data],
  )
  const withheld = useMemo(
    () => (data?.pay_summary_by_country ?? [])
      .filter((r) => !r.publishable)
      .sort((a, b) => b.n_as_published - a.n_as_published),
    [data],
  )

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <h1 style={{ fontSize: 'var(--text-xl)' }}>Postings</h1>
      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)', padding: '8px 0 12px', maxWidth: '72ch' }}>
        What employers <b>advertise</b> while hiring — not what this site's own wage spine (
        <Link to="/explore/money">Explore · Money</Link>) says people are actually paid. Two different
        quantities, never merged into one number: advertised ranges are wide, usually exclude equity
        and bonus, and skew toward roles that are currently hard to fill.{' '}
        <Link to="/data/postings-seed">Which companies, and why this skews where it does →</Link>
      </p>

      {error && (
        <div className="panel" style={{ borderColor: 'var(--warn)' }}>
          <h2>The data didn't load</h2>
          <p style={{ color: 'var(--ink-2)', marginTop: 8 }}>{error}</p>
        </div>
      )}

      {!data ? (
        // Reserves the shape of the three panels below, not one small
        // placeholder swapped for all of them at once — found live via this
        // package's own gate 14 (Lighthouse): the bare "Loading…" panel this
        // page shipped with first scored CLS 0.206 (worth 25 points of the
        // performance score on its own) because 35,936 postings' worth of
        // content popped in and pushed the whole page down in one jump. Same
        // fix already established for Jobs.tsx and Money.tsx's own panels —
        // this page's layout is a single-column stack rather than their
        // panel-span grid, so it borrows ChartSkeleton directly rather than
        // going through ThemeSkeleton's own grid-span wrapper.
        <>
          {/* Package 16 — re-measured at the 1350px Lighthouse desktop viewport
            * after the pay panel replaced the chart. Panel chrome is 34px
            * (16+16 padding, 1+1 border), so these are (rendered panel height −
            * 34): the filter panel renders 187 and the pay panel 584. The old
            * 346 was sized for the seven-country chart that no longer exists and
            * left a 238px gap; the 116 was already 37px short before this
            * package touched anything. Together they cost CLS 0.254. */}
          <div className="panel"><ChartSkeleton height={153} /></div>
          <div className="panel" style={{ marginTop: 12 }}><ChartSkeleton height={550} /></div>
          <div className="panel" style={{ marginTop: 12 }}><ChartSkeleton height={460} /></div>
        </>
      ) : (
        <>
          <div className="panel">
            <div className="sub">
              {/* Package 16 — raw rows and distinct roles are different numbers and
                * are now named as such. 5.98% of rows are re-listings of a role
                * already in the panel: the same requisition re-announced, or one
                * role opened in several locations. 99.9% of them carry their own
                * URL, so they are genuine separate advertisements, not scraping
                * artifacts — which is why they are counted here and excluded from
                * every derived statistic, rather than deleted. */}
              {data.postings.length.toLocaleString()} advertisements
              {data.duplicate_summary
                ? ` (${data.duplicate_summary.distinct_roles.toLocaleString()} distinct roles — ${data.duplicate_summary.re_listings.toLocaleString()} are re-listings)`
                : ''}
              , {Object.keys(data.seed_companies).length.toLocaleString()}{' '}
              companies, {providersAvailable.length} sources ({providersAvailable.map(([k]) => PROVIDER_LABEL[k]).join(', ')}).{' '}
              {withComp.toLocaleString()} ({data.postings.length ? Math.round(withComp / data.postings.length * 100) : 0}%)
              state a real pay range.
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 12, alignItems: 'flex-end' }}>
              <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
                Search title
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. backend, rust, staff"
                  style={{ display: 'block', marginTop: 4, padding: '6px 8px', border: '1px solid var(--line)',
                    background: 'var(--surface)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', minWidth: 200 }} />
              </label>
              <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
                Country
                <select value={countryFilter} onChange={(e) => setCountryFilter(e.target.value)}
                  style={{ display: 'block', marginTop: 4, padding: '6px 8px', border: '1px solid var(--line)',
                    background: 'var(--surface)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)' }}>
                  <option value="">All ({data.postings.length.toLocaleString()})</option>
                  <optgroup label="Countries this site covers">
                    {inScope.map(([cc, k]) => <option key={cc} value={cc}>{cc} ({k.toLocaleString()})</option>)}
                  </optgroup>
                  <optgroup label="Also in the harvest — not covered by this site">
                    {outOfScope.map(([cc, k]) => <option key={cc} value={cc}>{cc} ({k.toLocaleString()})</option>)}
                  </optgroup>
                </select>
              </label>
              <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
                Level <span style={{ opacity: 0.6 }}>(guessed from title)</span>
                <select value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)}
                  style={{ display: 'block', marginTop: 4, padding: '6px 8px', border: '1px solid var(--line)',
                    background: 'var(--surface)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)' }}>
                  <option value="">Any</option>
                  {Object.entries(LEVEL_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </label>
              <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 6 }}>
                <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
                Remote only
              </label>
              <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
                <button type="button" onClick={() => setView('list')}
                  className={view === 'list' ? 'chip chip-ok' : 'chip chip-quiet'} style={{ cursor: 'pointer' }}>List</button>
                <button type="button" onClick={() => setView('map')}
                  className={view === 'map' ? 'chip chip-ok' : 'chip chip-quiet'} style={{ cursor: 'pointer' }}>Map</button>
              </div>
            </div>
            <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 8 }}>
              "Category" (occupation) is not filterable yet — see the classifier's own status on{' '}
              <Link to="/data/postings-seed">the seed-list page</Link>.{' '}
              {outOfScope.length > 0 && (
                <>
                  The harvest also reaches <b>{outOfScope.length} countries this site does not
                  cover</b>{' '}
                  ({outOfScope.reduce((s, [, k]) => s + k, 0).toLocaleString()} advertisements,{' '}
                  {Math.round(100 * outOfScope.reduce((s, [, k]) => s + k, 0) / data.postings.length)}%).
                  They are listed separately above: there are postings for them, but none of this
                  site's cost-of-living, tax or housing data.
                </>
              )}
            </p>
          </div>

          {/* Package 16, Tier 2 — docs/DATA-FITNESS.md §1 rules this claim
            * "Not supported as labelled — 1 country, not 7; nearest $1,000".
            * The seven-country line is gone. What replaces it publishes only
            * countries clearing the sample floor, rounded to the precision the
            * heaping supports, with the interval shown; every other country is
            * still reported, as a COUNT, so the reader sees the panel's real
            * coverage instead of a median computed from five postings. */}
          <div className="panel" style={{ marginTop: 12 }}>
            <h2>Median advertised pay, software roles only</h2>
            <div className="sub">
              Annual-salary postings, converted to USD at each posting's own year, counted once per
              distinct role, restricted to titles classified as software, and{' '}
              <b>limited to recent postings</b> — pay advertised in 2016 and in 2026 are not the same
              quantity, and a median pooling them describes neither. This is this site's{' '}
              <b>advertised</b> mode — never blended with the survey-sourced lines on{' '}
              <Link to="/explore/money">Explore · Money</Link>, and never comparable to them: each
              posting contributes the <i>midpoint of an advertised range</i>, which is a property of
              the advertisement, not a salary anyone is paid.
            </div>
            {publishable.length > 0 ? (
              <div style={{ marginTop: 12 }}>
                {publishable.map((r) => (
                  <div key={r.country} style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 'var(--text-xl)', fontWeight: 600 }}>{r.country}</span>
                    <span style={{ fontSize: 'var(--text-xl)' }}>
                      ${Math.round(r.median_published_usd_year!).toLocaleString()}
                    </span>
                    <span style={{ color: 'var(--ink-3)' }}>
                      95% CI ${Math.round(r.ci_lo_published_usd_year!).toLocaleString()}–$
                      {Math.round(r.ci_hi_published_usd_year!).toLocaleString()} · n ={' '}
                      {r.n_software_only.toLocaleString()} distinct software roles
                      {r.published_from_year ? `, posted ${r.published_from_year} or later` : ''}
                    </span>
                  </div>
                ))}
                {/* Package 16 — every published number on this site carries a source, a
                  * date and a denominator. This one carried no date, and it mattered more
                  * than anywhere else: pooled across every vintage the US median was
                  * $175,000, sitting between a 2026 population near $204,000 and a
                  * 2016-2017 one near $87,000. A bimodal mixture wearing a point estimate.
                  * The window fixes that and introduces its own selection, which is why
                  * the composition is printed rather than described. */}
                {publishable[0]?.composition && (
                  <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 10 }}>
                    <b>What this is made of.</b>{' '}
                    {Object.entries(publishable[0]!.composition!.by_year)
                      .map(([y, k]) => `${y}: ${k.toLocaleString()}`)
                      .join(' · ')}
                    {' — '}
                    {publishable[0]!.composition!.share_from_latest_year_pct}% from the most recent
                    year. {publishable[0]!.composition!.largest_provider_share_pct}% come from a
                    single source ({publishable[0]!.composition!.largest_provider}). Restricting to
                    recent postings also removes US federal listings entirely, since every one of
                    those is dated 2016–2018 — so this is private job-board pay, not the whole
                    market.
                  </p>
                )}
                <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 10 }}>
                  Rounded to the nearest $1,000 because advertised pay is heaped to round thousands —
                  77.5% of native annual minima end in 0 or 5 — so a median of it resolves no finer.
                  The cents this figure used to carry were produced by currency conversion, not by any
                  employer.
                </p>
              </div>
            ) : null}
            {withheld.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <h3 style={{ fontSize: 'var(--text-sm)', margin: '0 0 6px' }}>
                  Too few to quote a median
                </h3>
                <div className="sub" style={{ marginBottom: 8 }}>
                  These counts are <b>much smaller than each country's posting total</b>, and two
                  filters explain almost all of the gap. Most advertisements state no pay at all, or
                  state it hourly or monthly rather than annually. Then, for every country except
                  the US, <b>the current year cannot be converted to USD</b>: the World Bank
                  exchange-rate series ends at 2025, and this site never substitutes a neighbouring
                  year's rate. That removes 88–92% of the annual-pay postings for Great Britain,
                  Canada, Germany and France — almost all of them 2026. So these are not simply
                  countries with little data; they are countries whose recent data cannot yet be
                  priced. None reaches {data!.pay_summary_min_n} qualifying software roles, so none
                  gets a median. Shown rather than hidden, because the gap is the finding.
                </div>
                {/* Package 16 — bounded, so the panel's height does not depend on
                  * how many countries happen to fall below the floor. Unbounded, it
                  * rendered 1,115px against a 346px skeleton and cost CLS 0.254,
                  * which is 13 points of the Lighthouse performance score on the one
                  * route that was already the site's worst. Found by gate 12. */}
                <div
                  tabIndex={0}
                  role="region"
                  aria-label="Countries withheld from the advertised-pay figure, scrollable"
                  style={{ maxHeight: 260, overflowY: 'auto' }}
                >
                <table className="tbl">
                  <caption className="sr-only">
                    Countries withheld from the advertised-pay figure, with their counts of postings whose annual pay could be priced in USD
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Country</th>
                      {/* Package 16 — these headers each named a bigger quantity than the
                        * number beneath them. "With pay range" showed 21 for GB, which has
                        * 346 postings with a pay range; the 21 was annual-and-convertible.
                        * "Distinct roles" showed 20 against GB's actual 2,063, reusing a
                        * term this page defines two panels above. Found by an adversarial
                        * review reading the rendered page. */}
                      <th scope="col" style={{ textAlign: 'right' }}>Annual pay, priced in USD</th>
                      <th scope="col" style={{ textAlign: 'right' }}>…once per role</th>
                      <th scope="col" style={{ textAlign: 'right' }}>…software, recent</th>
                      <th scope="col">Why withheld</th>
                    </tr>
                  </thead>
                  <tbody>
                    {withheld.map((r) => (
                      <tr key={r.country}>
                        <th scope="row">{r.country}</th>
                        <td style={{ textAlign: 'right' }}>{r.n_as_published.toLocaleString()}</td>
                        <td style={{ textAlign: 'right' }}>{r.n_deduped.toLocaleString()}</td>
                        <td style={{ textAlign: 'right' }}>{r.n_software_only.toLocaleString()}</td>
                        <td style={{ color: 'var(--ink-3)' }}>{r.withheld_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              </div>
            )}
          </div>

          {view === 'map' ? (
            <div className="panel" style={{ marginTop: 12 }}>
              <h2>Where these postings are</h2>
              <div className="sub">
                One dot per resolved country <b>this map holds a point for</b>, sized by posting
                count. Never per individual posting — no source in this package publishes
                coordinates precise enough for that.
                {mapOmitted.n > 0 && (
                  <> {' '}The map's coordinate table covers {mapOmitted.shownCountries} countries;{' '}
                    <b>{mapOmitted.n.toLocaleString()} postings ({mapOmitted.pct}%) across{' '}
                    {mapOmitted.countries} others are not drawn</b> — largest{' '}
                    {mapOmitted.largest.join(', ')}. They are still in the list and the counts above.
                  </>
                )}
              </div>
              <svg viewBox={`0 0 ${MAP.W} ${MAP.H}`} style={{ width: '100%', height: 'auto', marginTop: 10 }} role="img"
                aria-label={`${mapDots.length} countries with postings, largest: ${mapDots.slice().sort((a, b) => b.count - a.count)[0]?.cc ?? 'none'}`}>
                <path d={LAND_PATH} fill="var(--surface-raised)" stroke="var(--line)" strokeWidth={0.5} />
                {mapDots.map((d) => (
                  <circle key={d.cc} cx={d.x} cy={d.y} r={3 + (d.count / maxDot) * 10}
                    fill="var(--accent)" opacity={0.55} stroke="var(--surface)" strokeWidth={0.5}>
                    <title>{d.cc}: {d.count} postings</title>
                  </circle>
                ))}
              </svg>
            </div>
          ) : filtered.length === 0 ? (
            <Gap title="No postings match these filters" span="s6">
              <p>Try clearing the country or level filter.</p>
            </Gap>
          ) : (
            <div className="panel" style={{ marginTop: 12, overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <caption className="visually-hidden">
                  {filtered.length.toLocaleString()} postings matching the current filters
                </caption>
                <thead>
                  <tr style={{ textAlign: 'left', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
                    <th scope="col" style={{ padding: '4px 10px' }}>Company</th>
                    <th scope="col" style={{ padding: '4px 10px' }}>Title</th>
                    <th scope="col" style={{ padding: '4px 10px' }}>Location</th>
                    <th scope="col" style={{ padding: '4px 10px' }}>Advertised pay</th>
                    <th scope="col" style={{ padding: '4px 10px' }}>Posted</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, 500).map((p) => <PostingRow key={p.id} p={p} />)}
                </tbody>
              </table>
              {filtered.length > 500 && (
                <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 8 }}>
                  Showing the first 500 of {filtered.length.toLocaleString()} matching postings — narrow with a filter to see more of the rest.
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
