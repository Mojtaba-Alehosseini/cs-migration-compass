/* Every opening, with its filters and its map — the browsable half of the old
 * /postings, on its own route so it loads its own weight.
 *
 * Package 17, Tier 3. The merged /work page shows per-country counts and eight
 * examples each, and loads a 144 KB summary to do it. This page is the one that
 * is genuinely ABOUT the list: 48,267 advertisements, filterable, with the map.
 * It loads the full 24 MB payload on demand, which is the right trade for a
 * page whose entire purpose is the list, and the wrong one for a page that
 * shows eight rows per country.
 *
 * That split is what took /work from 0.79 to 1.00 — measured, the cost was
 * never the download but 484ms of main-thread time parsing and filtering the
 * array fifteen times. NEEDS-DECISION #38.
 *
 * Nothing here is new. Every control, panel and disclosure is the one the old
 * /postings rendered, moved rather than rewritten.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAsync } from '../components/explore/useAsync'
import { Gap, ChartSkeleton } from '../components/explore/Controls'
import { Flag } from '../components/Flag'
import { useData } from '../data/store'
import { loadPostings, fmtCompany, PROVIDER_LABEL, type Posting } from '../data/postings'
import { PostingPay, DISPLAY_CURRENCIES, DISPLAY_CURRENCY_LABEL, type DisplayCurrency }
  from '../components/PostingPay'
import { LAND_PATH, LAND_VIEWBOX } from '../data/land'
import { project } from '../components/CityMap'

/* ---- the map, lifted from the old /postings unchanged ---- */
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


const LEVELS = ['intern', 'junior', 'senior', 'staff+'] as const

export function Openings() {
  const { data, error } = useAsync(loadPostings, 'postings')
  const core = useData()
  const [country, setCountry] = useState('')
  const [level, setLevel] = useState('')
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [query, setQuery] = useState('')
  const [display, setDisplay] = useState<DisplayCurrency>('native')
  const [view, setView] = useState<'list' | 'map'>('list')
  // Package 17 — 100 rows, not 500. The old /postings rendered 500 immediately
  // and scored 0.86; this page renders a <Derived> per pay cell, which is more
  // work per row, and 500 of them took it to 0.75. A hundred is more than fits
  // on a screen and the rest is one click away.
  const [limit, setLimit] = useState(100)

  const crossRates = useMemo(() => Object.fromEntries(
    Object.entries(data?.display_fx?.rates ?? {}).map(([k, v]) => [k, v.rate]),
  ), [data])

  const filtered = useMemo(() => {
    if (!data) return [] as Posting[]
    const q = query.trim().toLowerCase()
    return data.postings.filter((p) => {
      if (country && p.country !== country) return false
      if (level && levelGuess(p.title) !== level) return false
      if (remoteOnly && !p.remote) return false
      if (q && !p.title?.toLowerCase().includes(q)) return false
      return true
    })
  }, [data, country, level, remoteOnly, query])

  const mapDots = useMemo(() => {
    if (view !== 'map') return []
    const counts = new Map<string, number>()
    for (const p of filtered) { if (p.country) counts.set(p.country, (counts.get(p.country) ?? 0) + 1) }
    return [...counts.entries()]
      .filter(([cc]) => COUNTRY_LATLON[cc])
      .map(([cc, count]) => {
        const [lat, lon] = COUNTRY_LATLON[cc]!
        const { x, y } = project(lat, lon)
        return { cc, count, x, y }
      })
  }, [filtered, view])
  const maxDot = Math.max(1, ...mapDots.map((d) => d.count))

  /** What the map cannot draw, computed from the same table the dots come from
   *  so the caption can never drift from the drawing. */
  const mapOmitted = useMemo(() => {
    const counts = new Map<string, number>()
    for (const p of data?.postings ?? []) {
      if (p.country) counts.set(p.country, (counts.get(p.country) ?? 0) + 1)
    }
    const missing = [...counts.entries()].filter(([cc]) => !COUNTRY_LATLON[cc])
    const total = [...counts.values()].reduce((s, k) => s + k, 0)
    const n = missing.reduce((s, [, k]) => s + k, 0)
    return {
      n, countries: missing.length, shownCountries: Object.keys(COUNTRY_LATLON).length,
      pct: total ? Math.round((100 * n) / total) : 0,
      largest: missing.sort((a, b) => b[1] - a[1]).slice(0, 3).map(([cc]) => cc),
    }
  }, [data])


  // In-scope and out-of-scope countries stay separated, exactly as the old
  // /postings separated them: the harvest reaches countries this site does not
  // cover, and a flat dropdown reads as coverage. NEEDS-DECISION #45.
  const [inScope, outOfScope] = useMemo(() => {
    if (!data) return [[], []] as [[string, number][], [string, number][]]
    const covered = new Set(core.citiesByCountry.keys())
    const all = Object.entries(data.country_counts)
      .filter(([cc]) => cc !== 'unresolved')
      .sort((a, b) => b[1] - a[1]) as [string, number][]
    return [all.filter(([cc]) => covered.has(cc)), all.filter(([cc]) => !covered.has(cc))]
  }, [data, core])

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <h1 style={{ fontSize: 'var(--text-xl)' }}>Every opening</h1>
      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)', padding: '8px 0 12px', maxWidth: '72ch' }}>
        The full harvest, filterable. For where you'd stand against a country's own wage table, and
        the openings that match a profile, see <Link to="/work">Position &amp; openings</Link>. This
        page loads the whole array on demand — it is the one page for which that is the right trade.
      </p>

      {error && (
        <div className="panel" style={{ borderColor: 'var(--warn)' }}>
          <h2>The data didn't load</h2>
          <p style={{ color: 'var(--ink-2)', marginTop: 8 }}>{error}</p>
        </div>
      )}

      {!data ? <div className="panel"><ChartSkeleton height={420} /></div> : (
        <>
          <div className="panel">
            <div className="sub">
              {data.postings.length.toLocaleString()} advertisements
              {data.duplicate_summary
                ? ` (${data.duplicate_summary.distinct_roles.toLocaleString()} distinct roles — ${data.duplicate_summary.re_listings.toLocaleString()} are re-listings)`
                : ''}
              , {Object.keys(data.seed_companies).length.toLocaleString()} companies.{' '}
              {data.postings.filter((p) => p.compensation).length.toLocaleString()} state a real pay
              range.
              {outOfScope.length > 0 && (
                <> The harvest also reaches <b>{outOfScope.length} countries this site does not
                  cover</b> ({outOfScope.reduce((s, [, k]) => s + k, 0).toLocaleString()}{' '}
                  advertisements). They are listed separately below: there are postings for them,
                  but none of this site's cost-of-living, tax or housing data.
                </>
              )}
            </div>

            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 12, alignItems: 'flex-end' }}>
              <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
                Search title
                <input value={query} onChange={(e) => setQuery(e.target.value)}
                  style={{ display: 'block', marginTop: 4, padding: '6px 8px', border: '1px solid var(--line)',
                    background: 'var(--surface)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)' }} />
              </label>
              <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
                Country
                <select value={country} onChange={(e) => setCountry(e.target.value)}
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
                <select value={level} onChange={(e) => setLevel(e.target.value)}
                  style={{ display: 'block', marginTop: 4, padding: '6px 8px', border: '1px solid var(--line)',
                    background: 'var(--surface)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)' }}>
                  <option value="">Any</option>
                  {LEVELS.map((l) => <option key={l} value={l}>{LEVEL_LABEL[l]}</option>)}
                </select>
              </label>
              <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
                Show pay in
                <select value={display} onChange={(e) => setDisplay(e.target.value as DisplayCurrency)}
                  style={{ display: 'block', marginTop: 4, padding: '6px 8px', border: '1px solid var(--line)',
                    background: 'var(--surface)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)' }}>
                  {DISPLAY_CURRENCIES.map((c) => (
                    <option key={c} value={c}>{DISPLAY_CURRENCY_LABEL[c]}</option>
                  ))}
                </select>
              </label>
              <label style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', display: 'flex', gap: 6, alignItems: 'center' }}>
                <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
                Remote only
              </label>
              <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
                <button type="button" onClick={() => setView('list')}
                  className={view === 'list' ? 'chip chip-ok' : 'chip chip-quiet'}
                  aria-pressed={view === 'list'} style={{ cursor: 'pointer' }}>List</button>
                <button type="button" onClick={() => setView('map')}
                  className={view === 'map' ? 'chip chip-ok' : 'chip chip-quiet'}
                  aria-pressed={view === 'map'} style={{ cursor: 'pointer' }}>Map</button>
              </div>
            </div>
          </div>

          {view === 'map' ? (
            <div className="panel" style={{ marginTop: 12 }}>
              <h2>Where these postings are</h2>
              <div className="sub">
                One dot per resolved country <b>this map holds a point for</b>, sized by posting
                count, and reflecting the filters above. Never per individual posting — no source in
                this package publishes coordinates precise enough for that.
                {mapOmitted.n > 0 && (
                  <> {' '}The coordinate table covers {mapOmitted.shownCountries} countries;{' '}
                    <b>{mapOmitted.n.toLocaleString()} postings ({mapOmitted.pct}%) across{' '}
                    {mapOmitted.countries} others are not drawn</b> — largest{' '}
                    {mapOmitted.largest.join(', ')}. They are still in the list and the counts above.
                  </>
                )}
              </div>
              <svg viewBox={`0 0 ${MAP.W} ${MAP.H}`} style={{ width: '100%', height: 'auto', marginTop: 10 }}
                role="img"
                aria-label={`${mapDots.length} countries with postings, largest: ${
                  mapDots.slice().sort((a, b) => b.count - a.count)[0]?.cc ?? 'none'}`}>
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
              <h2>{filtered.length.toLocaleString()} postings matching the current filters</h2>
              <table className="tbl" style={{ marginTop: 8 }}>
                <caption className="sr-only">Job postings matching the current filters</caption>
                <thead>
                  <tr>
                    <th scope="col">Company</th>
                    <th scope="col">Title</th>
                    <th scope="col">Location</th>
                    <th scope="col">Advertised pay</th>
                    <th scope="col">Posted</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, limit).map((p) => (
                    <tr key={p.id}>
                      <td>
                        {p.country && <Flag cc={p.country} size={12} />}{' '}
                        {p.provider === 'hn'
                          ? (p.company ?? PROVIDER_LABEL[p.provider])
                          : fmtCompany(p.company, p.company_slug)}
                      </td>
                      <td>
                        {p.url
                          ? <a href={p.url} target="_blank" rel="noopener noreferrer">{p.title}</a>
                          : p.title}
                      </td>
                      <td className="sub">{p.location_raw ?? (p.remote ? 'Remote' : '—')}</td>
                      <td><PostingPay comp={p.compensation} display={display} crossRates={crossRates} /></td>
                      <td className="sub" style={{ whiteSpace: 'nowrap' }}>{fmtDate(p.posted_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length > limit && (
                <p className="sub" style={{ marginTop: 8 }}>
                  Showing the first {limit.toLocaleString()} of {filtered.length.toLocaleString()}.
                  Not ranked — these are in harvest order.{' '}
                  <button type="button" onClick={() => setLimit((n) => n + 400)}
                    className="chip chip-quiet" style={{ cursor: 'pointer' }}>
                    Show 400 more
                  </button>
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
