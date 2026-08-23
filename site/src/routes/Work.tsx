/* Where you'd stand, and what's open — /position and /postings, merged.
 *
 * Package 17, Tier 2. Built from design-mockup-position.html, which was
 * designed and driven first; this file follows that mockup's structure rather
 * than inventing one, and the mockup stays committed so the two can be compared.
 *
 * WHY THEY ARE ONE PAGE. They answer one question in two halves. "Where would I
 * stand?" and "what is actually open?" are the same person asking the same
 * thing, and splitting them across two routes made both weaker — the position
 * had no jobs beside it and the postings had no personal frame. Italy settles
 * the argument: no wage table for this occupation at all, so the position half
 * has nothing to say, and simultaneously the best openings coverage of the
 * fifteen countries at 48% naming a figure. On two routes that reads as one
 * broken page and one fine one. Together it reads as what it is.
 *
 * WHAT IT REFUSES, unchanged from the routes it replaces: no per-posting
 * estimated-comp column, no ranking of which jobs to apply for, no Bay-Area
 * comp bands. Filtering is fine. Scoring is a recommendation, and this site does
 * not make recommendations.
 *
 * NOTHING IS DROPPED. Every panel both old routes rendered is composed here
 * from its original component — ProfileForm, CountryRow, PayVsCost and
 * CoverageMap are imported from Position.tsx rather than reimplemented, so they
 * cannot silently diverge. REPORT-P17.md gate 7 itemises the mapping.
 */

import { useCallback, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAsync } from '../components/explore/useAsync'
import { Gap, ChartSkeleton } from '../components/explore/Controls'
import { Flag } from '../components/Flag'
import { loadWages, type WageCountry } from '../data/explore'
import { loadOccupations, useData } from '../data/store'
import { loadExperienceGradient, profileFromParams, profileToParams, DEFAULT_OCCUPATION,
  type Profile } from '../data/profile'
import { loadOpenings, fmtCompany, type Openings as OpeningsData } from '../data/postings'
import { PostingPay, DISPLAY_CURRENCIES, DISPLAY_CURRENCY_LABEL, type DisplayCurrency }
  from '../components/PostingPay'
import { ProfileForm, CountryRow, PayVsCost, CoverageMap } from './Position'

/* ---------------------------------------------------------------- openings --- */

/** Software openings for one country, and — where employers named a figure —
 *  the employer's own range. Never a per-posting estimate, never ranked. */
function Openings({ name, block, display, crossRates }: {
  name: string
  block: OpeningsData['by_country'][string] | undefined
  display: DisplayCurrency
  crossRates: Record<string, number>
}) {
  // Counts and examples arrive pre-computed in a 144 KB file rather than being
  // filtered out of a 24 MB array on the main thread — see loadOpenings(). The
  // software set is the CLASSIFIER's, the same one the published medians use,
  // never re-derived from titles here.
  const all = { length: block?.all ?? 0 }
  const software = { length: block?.software ?? 0 }
  const named = { length: block?.named ?? 0 }
  const examples = block?.examples ?? []

  if (software.length === 0) {
    return (
      <Gap title={`Nothing open in ${name} right now`} span="s6">
        <p>
          The harvest reaches {all.length.toLocaleString()} advertisement
          {all.length === 1 ? '' : 's'} in {name} and none of them classifies as software. That is
          what this panel found, not a statement about the market — the harvest follows companies,
          not countries.
        </p>
      </Gap>
    )
  }

  if (named.length === 0) {
    return (
      <Gap title={`${software.length} software openings in ${name}, and none names a figure`} span="s6">
        <p>
          Employers in {name} rarely publish pay in job advertisements. All {software.length} software
          openings here — of {all.length.toLocaleString()} advertisements the harvest reaches in{' '}
          {name} — are real and current; not one states a range. That is a fact about advertising
          convention, not about the jobs. The position beside this does not depend on it: it comes
          from the national wage table, which is published whether or not employers advertise pay.
        </p>
      </Gap>
    )
  }

  const share = Math.round((named.length / software.length) * 100)
  return (
    <>
      <div className="sub">
        <b className="tnum">{named.length}</b> of <b className="tnum">{software.length}</b> software
        openings in {name} name a figure — <b className="tnum">{share}%</b>. The employer's own range
        is shown; nothing here is estimated per posting, and the list is not ranked.
      </div>
      <table className="tbl" style={{ marginTop: 8 }}>
        <caption className="sr-only">
          Software openings in {name} whose advertisement states a pay range
        </caption>
        <thead>
          <tr>
            <th scope="col">Role</th>
            <th scope="col">Advertised pay</th>
            <th scope="col">Posted</th>
          </tr>
        </thead>
        <tbody>
          {examples.map((p) => (
            <tr key={p.id}>
              <th scope="row" style={{ fontWeight: 'var(--weight-normal)' }}>
                {p.url
                  ? <a href={p.url} target="_blank" rel="noopener noreferrer">{p.title}</a>
                  : p.title}
                <div className="sub">{fmtCompany(p.company, p.company_slug)}</div>
              </th>
              <td><PostingPay comp={p.compensation} display={display} crossRates={crossRates} /></td>
              <td className="sub" style={{ whiteSpace: 'nowrap' }}>
                {p.posted_at?.slice(0, 10) ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {named.length > examples.length && (
        <p className="sub" style={{ marginTop: 6 }}>
          Showing {examples.length} of {named.length}. Not ranked — these are the most recent.{' '}
          <Link to="/data/postings-seed">The full list</Link> loads on demand.
        </p>
      )}
    </>
  )
}

/** Coverage before effort — the mockup's own first panel. Three axes are what
 *  packages 7-11 established about whether a country can be compared at all;
 *  the fourth is whether anyone is actually advertising. A country can answer
 *  the position question perfectly and have nothing open, or the reverse, and a
 *  visitor is entitled to know which before filling anything in. */
function Pips({ on, of, faint }: { on: number; of: number; faint?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      {Array.from({ length: of }, (_, i) => (
        <i key={i} aria-hidden="true" style={{
          width: 15, height: 7, borderRadius: 2,
          background: i < on ? 'var(--accent)' : 'var(--line)',
          opacity: i < on && faint ? 0.45 : 1,
        }} />
      ))}
    </span>
  )
}

const DIST_PIPS: Record<string, { pips: number; label: string; ranks: boolean }> = {
  'full': { pips: 3, label: 'full distribution', ranks: true },
  'quartile-only': { pips: 2, label: 'quartiles only', ranks: true },
  'central-tendency-only': { pips: 1, label: 'median + mean only', ranks: false },
  'mean-only': { pips: 1, label: 'mean only', ranks: false },
}

/* ------------------------------------------------------------------- page --- */

export function Work() {
  const [params, setParams] = useSearchParams()
  const profile = profileFromParams(params)
  const core = useData()

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

  const { data: wages, error: wagesError } = useAsync(loadWages, 'wages')
  const { data: gradient, error: gradientError } = useAsync(loadExperienceGradient, 'gradient')
  const { data: occupations, error: occupationsError } = useAsync(loadOccupations, 'occupations')
  const { data: postings, error: postingsError } = useAsync(loadOpenings, 'openings')
  const loadError = wagesError ?? gradientError ?? occupationsError ?? postingsError

  const [display, setDisplay] = useState<DisplayCurrency>('native')
  const crossRates = useMemo(() => Object.fromEntries(
    Object.entries(postings?.display_fx?.rates ?? {}).map(([k, v]) => [k, v.rate]),
  ), [postings])
  const byCountry = postings?.by_country ?? {}

  const wageByCountry = useMemo(() => {
    const m = new Map<string, WageCountry>()
    for (const r of wages?.countries ?? []) {
      const iso = r.country.split('-')[0]!
      if (!m.has(iso)) m.set(iso, r)
    }
    return m
  }, [wages])

  const countryName = useCallback(
    (cc: string): string => String(core.countryById.get(cc)?.name ?? cc), [core])

  const supported = profile.occupation === DEFAULT_OCCUPATION
  // citiesByCountry, not cities.map — the same index Postings.tsx uses, and the
  // one the Dataset actually builds. Reading .cities directly produced an empty
  // list and a silently empty country loop.
  const spine = useMemo(() => [...core.citiesByCountry.keys()].sort(), [core])

  /* One section per WAGE ROW, not per country — Canada publishes two NOC codes
   * (CA-21231 and CA-21232, NEEDS-DECISION #12) and both are real positions
   * with different medians. Collapsing them to one lost a row the old page
   * rendered, which the UI regression suite caught. Countries with no wage row
   * at all (Italy) are appended, because "no table" is itself an answer this
   * page owes the reader. */
  const sections = useMemo(() => {
    const out: { key: string; cc: string; row: WageCountry | undefined }[] = []
    const seenFirst = new Set<string>()
    for (const row of wages?.countries ?? []) {
      const cc = row.country.split('-')[0]!
      if (!spine.includes(cc)) continue
      const first = !seenFirst.has(cc)
      seenFirst.add(cc)
      out.push({ key: first && row.country !== cc ? `${cc}-first` : row.country, cc, row })
    }
    for (const cc of spine) if (!seenFirst.has(cc)) out.push({ key: cc, cc, row: undefined })
    return out.sort((a, b) => a.cc.localeCompare(b.cc))
  }, [wages, spine])

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <h1 style={{ fontSize: 'var(--text-xl)' }}>Where you'd stand, and what's open</h1>
      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)', padding: '8px 0 12px', maxWidth: '72ch' }}>
        Two questions that were never really separate. A <b>position</b> is a rank inside a country's
        own published wage table — not an estimate of you. An <b>estimate</b> is this pipeline's own
        model, shown only ever beside the distribution it came from. <b>Openings</b> are real
        advertisements, with the employer's own range where they published one. Where a country
        cannot answer one of these, it says which one and why, before you spend effort on it.
      </p>

      {loadError && (
        <div className="panel" style={{ borderColor: 'var(--warn)' }}>
          <h2>The data didn't load</h2>
          <p style={{ color: 'var(--ink-2)', marginTop: 8 }}>{loadError}</p>
        </div>
      )}

      <ProfileForm profile={profile} occupations={occupations} onChange={onProfileChange} />

      <div className="panel" style={{ marginTop: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
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
          <p className="sub" style={{ margin: 0, maxWidth: '54ch' }}>
            "As advertised" is the default and the source of truth. Everything else is a derived
            view: a converted figure opens its own method, and carries a marker where no rate for
            its own year exists yet.
          </p>
        </div>
      </div>

      {/* Position + openings, country by country. One panel per country so the
        * two halves sit beside each other rather than on two pages. */}
      <div className="panel" style={{ marginTop: 12 }}>
        <h2>Position and openings, country by country</h2>
        <div className="sub">
          Position: this country's own published percentile table, ranked by its own experience
          cross where one exists (SE, NO), the published median everywhere else. Estimate: that
          table's own median, shifted the same way — always labelled, never a source citation.
          Openings: real advertisements classified as software.
        </div>
        {!wages || !gradient || !postings ? (
          <ChartSkeleton height={320} />
        ) : !supported ? (
          <Gap title="No wage data resolved for this occupation yet" span="s6">
            <p>
              Only software developers (ISCO-08 2512) has resolved wage data across the spine. The
              openings below are unaffected — they are classified from job titles, not from the
              occupation crosswalk.
            </p>
          </Gap>
        ) : (
          <>
            <table className="tbl" style={{ marginTop: 10 }}>
              <caption className="sr-only">
                Coverage by country: occupation, pay basis, experience and openings
              </caption>
              <thead>
                <tr>
                  <th scope="col">Country</th>
                  <th scope="col" title="Does this country's own occupation code resolve to the one you picked?">Occupation</th>
                  <th scope="col" title="How much of the wage distribution does the office publish?">Pay basis</th>
                  <th scope="col" title="Does the country publish an experience or age cross to personalise by?">Experience</th>
                  <th scope="col" title="Software openings, and how many name a figure">Openings</th>
                  <th scope="col">Reading</th>
                </tr>
              </thead>
              <tbody>
                {spine.map((cc) => {
                  const row = wageByCountry.get(cc)
                  const dist = row?.native?.distribution
                  const d = dist ? DIST_PIPS[dist] : undefined
                  const b = byCountry[cc]
                  const open = { length: b?.software ?? 0 }
                  const named = { length: b?.named ?? 0 }
                  const reading = !row ? 'No wage table for this occupation'
                    : !d?.ranks ? 'No rank — only a central figure'
                    : open.length === 0 ? 'Ranks; nothing open'
                    : named.length === 0 ? `Ranks; ${open.length} open, none name pay`
                    : `Ranks; ${named.length} of ${open.length} name pay`
                  return (
                    <tr key={cc}
                      >
                      <th scope="row" style={{ fontWeight: 'var(--weight-normal)' }}>
                        <a href={`#c-${cc}`}
                          style={{ background: 'none', border: 0, font: 'inherit',
                            color: 'inherit', cursor: 'pointer', display: 'flex', alignItems: 'center',
                            gap: 6, textDecoration: 'none',
                            // WCAG 2.5.8 target size — these links rendered 17px
                            // tall and Lighthouse flagged all fifteen. Padding,
                            // not a fixed height, so the cell grows only as far
                            // as the target needs.
                            minHeight: 24, padding: '4px 2px' }}>
                          <Flag cc={cc} size={12} /> <b>{cc}</b>
                          <span className="sub">{countryName(cc)}</span>
                        </a>
                      </th>
                      <td><Pips on={row ? 1 : 0} of={1} /></td>
                      <td><Pips on={d?.pips ?? 0} of={3} /></td>
                      <td><Pips on={cc === 'SE' || cc === 'NO' ? 1 : 0} of={1} faint /></td>
                      <td><Pips on={open.length === 0 ? 0 : named.length === 0 ? 1 : named.length >= 10 ? 3 : 2} of={3} /></td>
                      <td className="sub">{reading}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {/* Every country, position and openings side by side.
              *
              * An earlier revision showed only the country picked in the matrix
              * above. That looked tidier and was a real regression: the old
              * /position rendered all fifteen at once, and comparing them IS
              * the feature — the UI regression suite caught it immediately,
              * with eleven checks failing because the Netherlands, Norway and
              * Canada's two NOC rows were no longer in the document at all.
              * The matrix is a summary of these, never a filter on them. */}
            {sections.map(({ key, cc, row }) => {
              return (
                <section key={key} id={`c-${cc}`}
                  style={{ borderTop: '1px solid var(--line)', paddingTop: 14, marginTop: 14 }}>
                  <h3 style={{ fontSize: 'var(--text-md)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Flag cc={cc} size={15} /> {countryName(cc)}
                    {key !== cc && <span className="sub">· {key}</span>}
                  </h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 18, marginTop: 10 }}>
                    <div>
                      <h4 style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', margin: '0 0 6px' }}>
                        Where you'd stand
                      </h4>
                      {row
                        ? <CountryRow row={row} profile={profile} gradient={gradient} highlighted={false} />
                        : (
                          <Gap title={`No wage table for this occupation in ${countryName(cc)}`} span="s6">
                            <p>
                              The site holds no published wage distribution for {countryName(cc)} at
                              this occupation depth, so there is no table to rank inside. That is a
                              gap in what the national office publishes at a comparable code, not a
                              gap in {countryName(cc)}'s labour market. Nothing here is estimated
                              from a neighbouring country.
                            </p>
                          </Gap>
                        )}
                    </div>
                    <div>
                      <h4 style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', margin: '0 0 6px' }}>
                        What's actually open
                      </h4>
                      {/* Openings are keyed by ISO country, so Canada's two NOC
                        * rows share one openings panel rather than double-counting
                        * the same advertisements. Rendered against the first of
                        * the pair only. */}
                      {key === cc || key === `${cc}-first`
                        ? <Openings name={countryName(cc)} block={byCountry[cc]}
                            display={display} crossRates={crossRates} />
                        : (
                          <p className="sub">
                            Shown once for {countryName(cc)}, above — these are the same
                            advertisements, and the two national codes share them.
                          </p>
                        )}
                    </div>
                  </div>
                </section>
              )
            })}
          </>
        )}
      </div>

      {wages && gradient && (
        <>
          <PayVsCost profile={profile} wageByCountry={wageByCountry} gradient={gradient} />
          <CoverageMap wages={wages} gradient={gradient} />
        </>
      )}

      <p className="sub" style={{ marginTop: 14 }}>
        This page replaces <code>/position</code> and <code>/postings</code>; both still resolve
        here. The full posting list, its filters and the harvest's own coverage live on{' '}
        <Link to="/data/postings-seed">the seed-list page</Link>.
      </p>
    </div>
  )
}
