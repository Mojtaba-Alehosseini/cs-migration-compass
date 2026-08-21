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
import { Flag } from '../components/Flag'
import { Gap, ChartTable, ChartSkeleton } from '../components/explore/Controls'
import { Chart } from '../components/chart/Chart'
import type { ChartCfg, Pt } from '../components/chart/engine'
import { loadPostings, fmtCompensation, fmtCompany, PROVIDER_LABEL, type Posting, type PostingsData } from '../data/postings'
import { LAND_PATH, LAND_VIEWBOX } from '../data/land'
import { project } from '../components/CityMap'

const MIN_ADVERTISED_CHART_N = 5
const MAX_ADVERTISED_CHART_COUNTRIES = 12

/** Package 12, tier 5.1's own `advertised` chart-kit mode needed a real chart
 *  to be visible on — the mode existed in engine.ts but nothing rendered it
 *  anywhere, found while gathering this package's own gate 9 evidence. Median
 *  advertised USD/year pay by country, restricted to USD-denominated annual
 *  figures only (disclosed below) to avoid pulling in FX conversion — a
 *  bigger addition than this one chart earns, and the wage-spine's own
 *  normalise.py is off-limits here regardless (this file never imports
 *  data/explore.ts). Countries below MIN_ADVERTISED_CHART_N are dropped
 *  rather than shown on a sample too thin to mean anything.
 *
 *  Package 14: reads `data.pay_summary_by_country`, pre-computed at build
 *  time (build_postings.py) — this function used to scan the FULL raw
 *  `postings` array and sort each country's own values itself, which
 *  became a real, measured Lighthouse performance cost once this
 *  package's own postings recovery grew that array to 46,040 records.
 *  Same filter, same thresholds, same result shape; the expensive part
 *  just doesn't happen in the browser on every page load any more. */
function advertisedByCountryCfg(data: PostingsData): ChartCfg | null {
  const rows = data.pay_summary_by_country
    .slice(0, MAX_ADVERTISED_CHART_COUNTRIES)
    .map((r) => ({ cc: r.country, n: r.n, med: r.median_usd_year }))
  if (rows.length < 3) return null

  const pts: Pt[] = rows.map((r, i) => [i, r.med, false, r.n])
  const maxV = Math.max(...rows.map((r) => r.med))
  const yMax = Math.ceil(maxV / 20000) * 20000
  // Tick VALUE and tick LABEL must come from the same rounding, not two
  // independent ones -- an earlier version rounded the value to the
  // nearest 10,000 but the label text to the nearest 1,000, so a gridline
  // at data-value 110,000 carried the label "$106K" (found live by this
  // package's own adversarial review, reading the rendered SVG directly).
  const yTicks: [number, string][] = [0, 0.5, 1].map((f) => {
    const v = Math.round((yMax * f) / 10000) * 10000
    return [v, `$${Math.round(v / 1000)}K`]
  })
  return {
    aria: `Median advertised USD/year pay by country: ${rows.map((r) => `${r.cc} $${Math.round(r.med).toLocaleString()}`).join(', ')}`,
    w: 940, h: 220, padL: 56, padR: 86,
    x: { min: 0, max: rows.length - 1, ticks: rows.map((r, i) => [i, r.cc] as [number, string]) },
    y: { min: 0, max: yMax, ticks: yTicks },
    series: [{
      key: 'advertised', label: 'advertised', color: 'var(--accent)', mode: 'advertised', markers: true,
      // Keep the n (index 3) point data -- an earlier version stripped it
      // via `.map(([x,y]) => [x,y])`, which emptied the accessible
      // ChartTable's own "n" column for every row (found live: the
      // rendered <td> cells were present but blank, on a chart whose
      // whole point is showing real per-country denominators).
      pts,
    }],
    fmtX: (v) => rows[Math.round(v)]?.cc ?? '',
    fmtV: (p) => {
      const r = rows[Math.round(p[0])]
      return r ? `$${Math.round(r.med).toLocaleString()}/yr (n=${r.n})` : ''
    },
  }
}

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

  const countries = useMemo(() => {
    if (!data) return []
    return Object.entries(data.country_counts)
      .filter(([cc]) => cc !== 'unresolved')
      .sort((a, b) => b[1] - a[1])
  }, [data])

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

  const providersAvailable = data ? Object.entries(data.provider_summary).filter(([, v]) => v.available) : []
  const withComp = data ? data.postings.filter((p) => p.compensation).length : 0
  const advertisedCfg = useMemo(() => (data ? advertisedByCountryCfg(data) : null), [data])

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
          <div className="panel"><ChartSkeleton height={116} /></div>
          <div className="panel" style={{ marginTop: 12 }}><ChartSkeleton height={346} /></div>
          <div className="panel" style={{ marginTop: 12 }}><ChartSkeleton height={460} /></div>
        </>
      ) : (
        <>
          <div className="panel">
            <div className="sub">
              {data.postings.length.toLocaleString()} postings, {Object.keys(data.seed_companies).length.toLocaleString()}{' '}
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
                  {countries.map(([cc, n]) => <option key={cc} value={cc}>{cc} ({n})</option>)}
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
              <Link to="/data/postings-seed">the seed-list page</Link>.
            </p>
          </div>

          {advertisedCfg && (
            <div className="panel" style={{ marginTop: 12 }}>
              <h2>Median advertised pay by country</h2>
              <div className="sub">
                USD-denominated, annual-salary postings only ({MIN_ADVERTISED_CHART_N}+ per country to
                appear) — the dotted line is this site's <b>advertised</b> mode, never restyled from
                and never blended with the survey-sourced lines on{' '}
                <Link to="/explore/money">Explore · Money</Link>. Hourly and non-USD postings (most of
                this panel's own non-US rows) are excluded from this one chart to avoid mixing pay
                periods or currencies into a single axis — they still appear in the table and map below.
              </div>
              <Chart id="postings-advertised-by-country" cfg={advertisedCfg} transition="fade">
                <ChartTable
                  caption="Median advertised USD/year pay by country"
                  head={['Country', 'Median advertised', 'n']}
                  rows={advertisedCfg.series[0]!.pts.map((p) => {
                    const cc = advertisedCfg.x.ticks[Math.round(p[0])]?.[1] ?? ''
                    return [cc, `$${Math.round(p[1] ?? 0).toLocaleString()}`, String(p[3] ?? '')]
                  })}
                />
              </Chart>
            </div>
          )}

          {view === 'map' ? (
            <div className="panel" style={{ marginTop: 12 }}>
              <h2>Where these postings are</h2>
              <div className="sub">One dot per resolved country, sized by posting count. Never per individual posting — no source in this package publishes coordinates precise enough for that.</div>
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
