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
 * WHERE THE OLD PANELS WENT. The position half is composed from its original
 * components — ProfileForm, CountryRow, PayVsCost and CoverageMap are imported
 * from Position.tsx rather than reimplemented, so those cannot silently
 * diverge. The old /postings' browsable list, its filters and its map are NOT
 * here: they are /openings, which loads the full payload on demand. PublishedPay
 * below is a rewrite rather than an import, and is therefore the one panel that
 * CAN drift from what /postings showed.
 *
 * An earlier version of this comment said "NOTHING IS DROPPED. Every panel both
 * old routes rendered is composed here from its original component." Neither
 * sentence was true, and adversarial review found nine further things the merge
 * had dropped after the first five were restored. A header that asserts
 * completeness is a claim like any other and has to survive the same check.
 * REPORT-P17.md gate 7 itemises the mapping.
 */

import { useCallback, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAsync } from '../components/explore/useAsync'
import { Gap } from '../components/explore/Controls'
import { Flag } from '../components/Flag'
import { loadWages, type WageCountry } from '../data/explore'
import { loadOccupations, useData } from '../data/store'
import { loadExperienceGradient, profileFromParams, profileToParams, DEFAULT_OCCUPATION,
  type Profile } from '../data/profile'
import { loadOpenings, fmtCompany, type Openings as OpeningsData } from '../data/postings'
import { PostingPay, DISPLAY_CURRENCIES, DISPLAY_CURRENCY_LABEL, type DisplayCurrency,
  type CrossRate } from '../components/PostingPay'
import { PayVsCost, CoverageMap } from './Position'
import { CountryStripRow, RowListSkeleton } from '../components/work/CountryStripRow'
import { ProfileLine } from '../components/work/ProfileLine'

/* ---------------------------------------------------------------- openings --- */

/** NEEDS-DECISION #51 — "the site already publishes every other error rate."
 *  This is the classifier's: out-of-fold F1 with its own 95% CI, captioned
 *  beside the "software openings" count it qualifies rather than left in an
 *  evaluation file nobody reading this panel would ever open. */
function ClassifierCaption({ d }: { d: { f1: number; ci95: [number, number]; n_true: number } }) {
  return (
    <>
      {' '}The "software" label itself is a classifier's guess, measured at F1{' '}
      <b className="tnum">{d.f1.toFixed(2)}</b> (95% CI {d.ci95[0].toFixed(2)}–{d.ci95[1].toFixed(2)},
      against {d.n_true} hand-labelled titles) — the same set every published median on this page
      is drawn from, not a different, cleaner one.
    </>
  )
}

/** Software openings for one country, and — where employers named a figure —
 *  the employer's own range. Never a per-posting estimate, never ranked. */
function Openings({ name, block, display, crossRates, fxMaxGap, unavailable, classDecision }: {
  name: string
  block: OpeningsData['by_country'][string] | undefined
  display: DisplayCurrency
  crossRates: Record<string, CrossRate> | undefined
  /** NEEDS-DECISION #51 — the classifier's own measured F1 (out-of-fold, with
   *  its 95% CI) for the SW class, the same set these rows and every
   *  published median are drawn from. "Show it beside the figures it
   *  qualifies" was the ruling; this is the figure it qualifies. */
  classDecision?: { f1: number; ci95: [number, number]; n_true: number }
  fxMaxGap: number
  /** The openings summary did not load. Distinct from "nothing is open",
   *  which is a fact about the harvest — this is a fact about the fetch, and
   *  saying the first when the second happened is a lie the reader cannot
   *  check. Adversarial review finding 4. */
  unavailable?: boolean
}) {
  if (unavailable) {
    return (
      <Gap title="Openings didn't load" span="s6" level={5}>
        <p>
          The position beside this is unaffected — it comes from the national wage table, which
          loaded. What failed is the openings summary; reloading usually fixes it, and the full
          list lives on <Link to="/openings">Every opening</Link>.
        </p>
      </Gap>
    )
  }
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
      <Gap title={`Nothing open in ${name} right now`} span="s6" level={5}>
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
      <Gap title={`${software.length} software openings in ${name}, and none names a figure`}
             span="s6" level={5}>
        <p>
          Employers in {name} rarely publish pay in job advertisements. All {software.length} software
          openings here — of {all.length.toLocaleString()} advertisements the harvest reaches in{' '}
          {name} — are real and current; not one states a range. That is a fact about advertising
          convention, not about the jobs. The position beside this does not depend on it: it comes
          from the national wage table, which is published whether or not employers advertise pay.
          {classDecision && <ClassifierCaption d={classDecision} />}
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
        is shown, never this site's estimate of what a job pays, and the list is not ranked.
        {display !== 'native' && (
          <> Converted, it is that same range in another unit; a <sup className="fx-estimate">≈</sup>
            {' '}marks one whose rate came from a different year, and opens the method that says
            which.</>
        )}
        {classDecision && <ClassifierCaption d={classDecision} />}
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
              <td><PostingPay comp={p.compensation} display={display}
                crossRates={crossRates} maxGapYears={fxMaxGap} /></td>
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
          {/* /openings, not /data/postings-seed. The seed list holds the
            * companies and sources; it has never held the advertisements. The
            * previous commit removed one copy of this wrong signpost and left
            * this one, which renders six times on today's page. Adversarial
            * review finding 9. */}
          <Link to="/openings">The full list</Link> loads on demand.
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
function Pips({ on, of, faint, label }: {
  on: number; of: number; faint?: boolean
  /** What these pips MEAN, in words. The pips themselves are decorative
   *  `<i aria-hidden>`s, so without this the four data columns of the coverage
   *  matrix announced four empty cells — the pay-basis depth and the experience
   *  axis were unavailable to assistive tech entirely, and Lighthouse cannot
   *  see that because there is no rule against a cell being empty. Adversarial
   *  review, accessibility 1. */
  label: string
}) {
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      <span className="sr-only">{label}</span>
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

/** The published per-country advertised-pay figure, with its composition and
 *  the countries withheld from it.
 *
 *  This is package 16's headline deliverable and an earlier revision of the
 *  merge dropped it — it lived on /postings, /postings became a redirect, and
 *  nothing carried it across. Restored here rather than on the full-list page
 *  because it belongs beside the position: they are the two answers to "what
 *  does this country pay", one from a national wage table and one from what
 *  employers advertise, and they must never be blended.
 *
 *  Package 24, Tier 1b — the ONE always-open panel this used to be is split
 *  into the three pieces the work order's own below-fold ordering names
 *  separately ("openings detail · coverage on its three axes · the
 *  withheld-countries register · the beyond-our-fifteen section"). The
 *  COMPUTATION below is untouched, byte-for-byte, down to every
 *  adversarial-review comment attached to it (NEEDS-DECISION #45/#52's own
 *  in-scope/out-of-scope split) — only which JSX fragment renders inside
 *  which <details> changed. `usePublishedPaySlices` is the shared filtering
 *  the three render functions below it now call instead of computing once
 *  for one combined panel. */
function usePublishedPaySlices(summary: NonNullable<OpeningsData['pay_summary_by_country']>, spine: string[]) {
  const inScope = new Set(spine)
  const publishable = summary.filter((r) => r.publishable && r.median_published_usd_year != null)
  const withheld = summary.filter((r) => !r.publishable)
    .sort((a, b) => b.n_as_published - a.n_as_published)
  return {
    publishableIn: publishable.filter((r) => inScope.has(r.country)),
    publishableOut: publishable.filter((r) => !inScope.has(r.country)),
    withheldIn: withheld.filter((r) => inScope.has(r.country)),
    withheldOut: withheld.filter((r) => !inScope.has(r.country)),
    publishable, withheld,
  }
}

/** Below-fold item 1 (folded into "Openings detail"): the headline medians
 * themselves, in scope. */
function PublishedPayHeadline({ summary, spine }: {
  summary: NonNullable<OpeningsData['pay_summary_by_country']>
  spine: string[]
}) {
  const { publishableIn, publishable, withheld } = usePublishedPaySlices(summary, spine)
  if (publishable.length === 0 && withheld.length === 0) return null
  return (
    <div style={{ marginTop: 12 }}>
      <h2 style={{ fontSize: 'var(--text-sm)' }}>Median advertised pay, software roles only</h2>
      <div className="sub">
        Annual-salary advertisements, counted once per distinct role, restricted to titles
        classified as software and <b>limited to recent postings</b> — pay advertised in 2016 and in
        2026 are not the same quantity, and a median pooling them describes neither. This is the
        site's <b>advertised</b> mode: never blended with the wage tables above, and never
        comparable to them, because each posting contributes the <i>midpoint of an advertised
        range</i> rather than a salary anyone is paid.
      </div>
      {publishableIn.map((r) => (
        <div key={r.country} style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginTop: 10 }}>
          <Flag cc={r.country} size={13} />
          <span style={{ fontSize: 'var(--text-lg)', fontWeight: 600 }}>{r.country}</span>
          <span style={{ fontSize: 'var(--text-lg)' }} className="tnum">
            ${Math.round(r.median_published_usd_year!).toLocaleString()}
            {/* Most of GB, CA, FR and DE's inputs are converted at a
              * neighbouring year's rate — 76-94% of them — which is why those
              * four are publishable at all this package. A median resting
              * mostly on substituted rates wears the same mark its inputs do.
              * Adversarial review H2. */}
            {(r.composition?.fx_estimated_pct ?? 0) >= 50 && (
              <sup className="fx-estimate"
                aria-label={`Estimated: ${r.composition!.fx_estimated_pct}% of the advertisements `
                  + `behind this median were converted at a neighbouring year's rate`}
                title={`${r.composition!.fx_estimated_pct}% of these were converted at a rate from `
                  + `a neighbouring year — see the composition below`}>≈</sup>
            )}
          </span>
          <span className="sub">
            95% CI ${Math.round(r.ci_lo_published_usd_year!).toLocaleString()}–$
            {Math.round(r.ci_hi_published_usd_year!).toLocaleString()} · n ={' '}
            {r.n_software_only.toLocaleString()} distinct software roles
            {r.published_from_year ? `, posted ${r.published_from_year} or later` : ''}
          </span>
        </div>
      ))}
      {/* EVERY publishable country's composition, not just the first. Five
        * countries ship a composition block; this rendered only publishable[0]
        * — the US — so GB, CA, FR and DE showed a headline median with no
        * account of what it was made of, in the same package that made them
        * publishable. Package 16's stated lesson was that a median with no
        * description of its own composition is how the US figure came to be 77%
        * nine-year-old federal listings without anyone noticing. The closing
        * caveat is each country's OWN, computed server-side — the hardcoded
        * sentence about US federal listings used to be printed under all five.
        * Adversarial review H2. */}
      {publishableIn.some((r) => r.composition) && (
        <div style={{ marginTop: 10 }}>
          {publishableIn.filter((r) => r.composition).map((r) => (
            <p key={r.country} className="sub" style={{ marginTop: 8, maxWidth: '78ch' }}>
              <b>What the {r.country} figure is made of.</b>{' '}
              {Object.entries(r.composition!.by_year)
                .map(([y, k]) => `${y}: ${k.toLocaleString()}`).join(' · ')}
              {' — '}{r.composition!.share_from_latest_year_pct}% from the most recent year.{' '}
              {/* The provider share is NOT repeated here: the caveat below
                * opens with it, computed server-side, and printing both gave
                * "96.7% from a single source (ashby). 97% of these
                * advertisements come from one source (ashby)." */}
              {r.composition!.caveat}
            </p>
          ))}
        </div>
      )}
      {/* Conditional, because with nothing publishable this panel renders an
        * <h2>, no median, and then a sentence about rounding a figure that is
        * not there. Unreachable today at five publishable countries; it was one
        * withheld country away from being reachable at one. Adversarial review D7. */}
      {publishableIn.length > 0 && (
        <p className="sub" style={{ marginTop: 8 }}>
          Rounded to the nearest $1,000 because advertised pay is heaped to round thousands — 77.5%
          of native annual minima end in 0 or 5 — so a median of it resolves no finer.
        </p>
      )}
    </div>
  )
}

/** Below-fold item 3: "the withheld-countries register." */
function PublishedPayWithheld({ summary, meta, minN, spine }: {
  summary: NonNullable<OpeningsData['pay_summary_by_country']>
  meta: OpeningsData['pay_summary_meta']
  minN: number
  spine: string[]
}) {
  const { withheldIn } = usePublishedPaySlices(summary, spine)
  if (withheldIn.length === 0) return meta?.vintage_cost ? <p className="sub">{meta.vintage_cost}</p> : null
  return (
    <>
      {withheldIn.length > 0 && (
        <div>
          <h3 style={{ fontSize: 'var(--text-sm)', margin: '0 0 6px' }}>Too few to quote a median</h3>
          <div className="sub" style={{ marginBottom: 8 }}>
            Counts below are advertisements whose annual pay could be priced in USD — not every
            posting harvested. None reaches {minN} distinct software roles, so none gets a median.
            Their counts are real; a median of them would not be.
          </div>
          <div style={{ maxHeight: 240, overflowY: 'auto' }} tabIndex={0} role="region"
            aria-label="Countries withheld from the advertised-pay figure, scrollable">
            <table className="tbl">
              <caption className="sr-only">
                Countries withheld from the advertised-pay figure
              </caption>
              <thead>
                <tr>
                  <th scope="col">Country</th>
                  <th scope="col" style={{ textAlign: 'right' }}>Annual pay, priced in USD</th>
                  <th scope="col" style={{ textAlign: 'right' }}>…once per role</th>
                  <th scope="col" style={{ textAlign: 'right' }}>…software, recent</th>
                  <th scope="col">Why withheld</th>
                </tr>
              </thead>
              <tbody>
                {withheldIn.map((r) => (
                  <tr key={r.country}>
                    <th scope="row">{r.country}</th>
                    <td style={{ textAlign: 'right' }}>{r.n_as_published.toLocaleString()}</td>
                    <td style={{ textAlign: 'right' }}>{r.n_deduped.toLocaleString()}</td>
                    <td style={{ textAlign: 'right' }}>{r.n_software_only.toLocaleString()}</td>
                    <td className="sub">{r.withheld_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {meta?.vintage_cost && <p className="sub" style={{ marginTop: 8 }}>{meta.vintage_cost}</p>}
    </>
  )
}

/** Below-fold item 4: "the beyond-our-fifteen section." */
function PublishedPayBeyond15({ summary, spine }: {
  summary: NonNullable<OpeningsData['pay_summary_by_country']>
  spine: string[]
}) {
  const { publishableOut, withheldOut } = usePublishedPaySlices(summary, spine)
  if (publishableOut.length === 0 && withheldOut.length === 0) {
    return (
      <p className="sub">
        Nothing outside the site's fifteen currently clears the advertised-pay publish floor.
      </p>
    )
  }
  return (
    <>
      {/* NEEDS-DECISION #45/#52 — everything the harvest reached outside the
        * site's fifteen, kept separate the same way /openings' own country
        * dropdown already separates "this site covers" from "also in the
        * harvest." publishableOut exists for the moment an out-of-scope
        * country DOES clear the 30-posting publish floor (none does on the
        * current corpus, checked directly — France is closest at 29, an
        * earlier version of this comment wrongly claimed it already
        * cleared the bar, adversarial review caught it against the real
        * data) — without this branch, that country would render as an
        * undifferentiated headline chip beside the fifteen's own the day it
        * crosses 30. Carries the same disclosure the in-scope rows above
        * do (FX-estimate marker, publish window, rounding note) so crossing
        * that floor doesn't also mean crossing into a LESS disclosed
        * treatment than the fifteen get. */}
      {(publishableOut.length > 0 || withheldOut.length > 0) && (
        <div>
          <div className="sub" style={{ marginBottom: 8 }}>
            The harvest reaches {publishableOut.length + withheldOut.length} countries this site
            does not cover — no cost-of-living, tax or housing data, so nothing here joins a
            comparison or a headline count above. Shown because the numbers are real, not because
            they are part of this site's fifteen.
          </div>
          {publishableOut.map((r) => (
            <div key={r.country} style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginTop: 8, opacity: 0.85 }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>{r.country}</span>
              <span style={{ fontSize: 'var(--text-sm)' }} className="tnum">
                ${Math.round(r.median_published_usd_year!).toLocaleString()}
                {(r.composition?.fx_estimated_pct ?? 0) >= 50 && (
                  <sup className="fx-estimate"
                    aria-label={`Estimated: ${r.composition!.fx_estimated_pct}% of the advertisements `
                      + `behind this median were converted at a neighbouring year's rate`}
                    title={`${r.composition!.fx_estimated_pct}% of these were converted at a rate from `
                      + `a neighbouring year`}>≈</sup>
                )}
              </span>
              <span className="sub">
                95% CI ${Math.round(r.ci_lo_published_usd_year!).toLocaleString()}–$
                {Math.round(r.ci_hi_published_usd_year!).toLocaleString()} · n ={' '}
                {r.n_software_only.toLocaleString()} distinct software roles
                {r.published_from_year ? `, posted ${r.published_from_year} or later` : ''}
                {' · outside the site\'s scope'}
              </span>
            </div>
          ))}
          {publishableOut.length > 0 && (
            <p className="sub" style={{ marginTop: 8 }}>
              Rounded to the nearest $1,000 because advertised pay is heaped to round thousands — the
              same rounding the fifteen's own figures above use.
            </p>
          )}
          {withheldOut.length > 0 && (
            <div style={{ maxHeight: 200, overflowY: 'auto', marginTop: 10 }} tabIndex={0} role="region"
              aria-label="Countries outside the site's scope, too few advertisements for a median">
              <table className="tbl">
                <caption className="sr-only">
                  Countries outside the site's fifteen, too few advertisements for a median
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Country</th>
                    <th scope="col" style={{ textAlign: 'right' }}>Annual pay, priced in USD</th>
                    <th scope="col" style={{ textAlign: 'right' }}>…once per role</th>
                    <th scope="col" style={{ textAlign: 'right' }}>…software, recent</th>
                    <th scope="col">Why withheld</th>
                  </tr>
                </thead>
                <tbody>
                  {withheldOut.map((r) => (
                    <tr key={r.country}>
                      <th scope="row">{r.country}</th>
                      <td style={{ textAlign: 'right' }}>{r.n_as_published.toLocaleString()}</td>
                      <td style={{ textAlign: 'right' }}>{r.n_deduped.toLocaleString()}</td>
                      <td style={{ textAlign: 'right' }}>{r.n_software_only.toLocaleString()}</td>
                      <td className="sub">{r.withheld_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  )
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
  // The whole rate object, not `.rate` — PostingPay matches each posting's own
  // year against `by_year`. Mapping this down to one number is what made every
  // cross-rate conversion silently use 2025.
  const crossRates = postings?.display_fx?.rates
  const fxMaxGap = postings?.display_fx?.max_gap_years ?? 0
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
    const out: { key: string; cc: string; row: WageCountry | undefined; firstOfCountry: boolean }[] = []
    const seenFirst = new Set<string>()
    for (const row of wages?.countries ?? []) {
      const cc = row.country.split('-')[0]!
      if (!spine.includes(cc)) continue
      const first = !seenFirst.has(cc)
      seenFirst.add(cc)
      // The key is the wage row's OWN code and nothing else. An earlier version
      // wrote `${cc}-first` here as a sentinel for "render the openings panel
      // against this one", and it leaked straight into the visible heading:
      // Canada's first section read "Canada · CA-first" while the row three
      // lines below it read CA-21231. The sentinel is a boolean now, because
      // that is what it always was. Adversarial review finding 5.
      out.push({ key: row.country, cc, row, firstOfCountry: first })
    }
    for (const cc of spine) if (!seenFirst.has(cc)) out.push({ key: cc, cc, row: undefined, firstOfCountry: true })
    return out.sort((a, b) => a.cc.localeCompare(b.cc) || a.key.localeCompare(b.key))
  }, [wages, spine])

  /** Each absent country's own stated reason, keyed by code. The wage build
   *  records why a country has no row — "ISTAT publishes no occupation-level
   *  (CP2011) earnings flow at all, per src_salary_it.py" — and the gap where
   *  the table would be is the place a reader asks the question. */
  const absentReason = useMemo(() => {
    const m = new Map<string, string>()
    for (const a of wages?.absent ?? []) m.set(a.country.split('-')[0]!, a.reason)
    return m
  }, [wages])

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <h1 style={{ fontSize: 'var(--text-xl)' }}>Where you'd stand</h1>
      <p className="lede" style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)', padding: '6px 0 14px', maxWidth: '64ch' }}>
        Fifteen countries, ranked by their own published pay table. Where one can't answer that, it
        says why.
      </p>

      {loadError && (
        <div className="panel" style={{ borderColor: 'var(--warn)' }}>
          <h2>The data didn't load</h2>
          <p style={{ color: 'var(--ink-2)', marginTop: 8 }}>{loadError}</p>
        </div>
      )}

      {/* Package 24, Tier 1b — "Drop a CV, or set it yourself," one line,
        * replacing the old always-open CV panel and three-field form. Both
        * still live inside it, completely unchanged (package 10's own
        * no-network gate on the form, package 22's Art 50 disclosure on the
        * CV step) — only the collapsed/expanded wrapper around them is new. */}
      <ProfileLine profile={profile} occupations={occupations} countryName={countryName}
        onProfileChange={onProfileChange} />

      {/* THE ANSWER. Fifteen countries' worth of rows (sixteen sections —
        * Canada publishes two NOC codes, NEEDS-DECISION #12), each one
        * flag-dot / distribution strip with a marker / estimate / openings
        * count. Four marks carry what this page used to say in fourteen
        * paragraphs — see CountryStripRow's own header for the full budget.
        * Gated on `wages`/`gradient` only, not `postings` — Adversarial
        * review finding 4 (package 17): gating the position half on the
        * openings summary meant one failed fetch of a 150 KB convenience
        * file replaced fifteen countries' positions with a permanent
        * skeleton. Each row's own openings count degrades independently. */}
      <div className="panel" style={{ marginTop: 12, padding: '8px 14px' }}>
        {!wages || !gradient ? (
          <RowListSkeleton count={spine.length} />
        ) : !supported ? (
          <Gap title="No wage data resolved for this occupation yet" span="s6">
            <p>
              Only software developers (ISCO-08 2512) has resolved wage data across the spine, so
              there is no position to show for this one. Switch back to Software developers to see
              real positions; the openings themselves are classified from job titles rather than
              from the occupation crosswalk, so they are unaffected by this and are listed in full
              on <Link to="/openings">Every opening</Link>.
            </p>
          </Gap>
        ) : (
          sections.map(({ key, cc, row, firstOfCountry }, i) => (
            <CountryStripRow
              key={key}
              row={row}
              cc={cc}
              name={countryName(cc)}
              secondCode={row && key !== cc ? row.national_code : undefined}
              profile={profile}
              gradient={gradient}
              openings={byCountry[cc]}
              // Canada's two NOC rows share one openings block — the SAME
              // advertisements, classified by title, never by NOC code, so
              // both rows show the identical count. The old page showed it
              // once and printed a note on the second row explaining why;
              // this row has no room for a permanent note, so the same fact
              // goes into the tap card instead — nothing lost, relocated.
              openingsSharedWithCode={!firstOfCountry && row ? sections.find((s) => s.cc === cc && s.firstOfCountry)?.row?.national_code : undefined}
              absentReason={absentReason.get(cc)}
              highlighted={profile.country != null && cc === profile.country}
              index={i}
            />
          ))
        )}
      </div>

      {/* Below the fold, in the order the work order specifies: openings
        * detail, coverage on its three axes, the withheld-countries
        * register, the beyond-our-fifteen section. All of it still honest,
        * none of it competing with the answer above. */}

      <details className="disclosure panel">
        <summary style={{ cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
          Openings detail — real advertisements, employer's own range
        </summary>
        <div style={{ marginTop: 10 }}>
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
          {postings?.pay_summary_by_country && (
            <PublishedPayHeadline summary={postings.pay_summary_by_country} spine={spine} />
          )}
          {spine.map((cc) => (
            <div key={cc} style={{ borderTop: '1px solid var(--line)', paddingTop: 12, marginTop: 12 }}>
              <h3 style={{ fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: 6, margin: '0 0 6px' }}>
                <Flag cc={cc} size={13} /> {countryName(cc)}
              </h3>
              <Openings name={countryName(cc)} block={byCountry[cc]}
                display={display} crossRates={crossRates} fxMaxGap={fxMaxGap}
                unavailable={!postings}
                classDecision={postings?.title_class_summary?.class_decisions?.SW} />
            </div>
          ))}
        </div>
      </details>

      <details className="disclosure panel">
        <summary style={{ cursor: 'pointer', fontSize: 'var(--text-sm)' }}>Coverage, on its three axes</summary>
        <table className="tbl" style={{ marginTop: 10 }}>
          <caption className="sr-only">Coverage by country: occupation, pay basis, experience</caption>
          <thead>
            <tr>
              <th scope="col">Country</th>
              <th scope="col" title="Does this country's own occupation code resolve to the one you picked?">Occupation</th>
              <th scope="col" title="How much of the wage distribution does the office publish?">Pay basis</th>
              <th scope="col" title="Does the country publish an experience or age cross to personalise by?">Experience</th>
              <th scope="col">Reading</th>
            </tr>
          </thead>
          <tbody>
            {spine.map((cc) => {
              const row = wageByCountry.get(cc)
              const dist = row?.native?.distribution
              const d = dist ? DIST_PIPS[dist] : undefined
              const reading = !row ? 'No wage table for this occupation'
                : !d?.ranks ? 'No rank — only a central figure'
                : 'Ranks against the published table'
              return (
                <tr key={cc}>
                  <th scope="row" style={{ fontWeight: 'var(--weight-normal)' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Flag cc={cc} size={12} /> <b>{cc}</b>
                      <span className="sub">{countryName(cc)}</span>
                    </span>
                  </th>
                  <td><Pips on={row ? 1 : 0} of={1}
                    label={row ? 'Occupation code resolves' : 'No occupation code resolves'} /></td>
                  <td><Pips on={d?.pips ?? 0} of={3}
                    label={d?.label ?? 'no distribution published'} /></td>
                  <td><Pips on={cc === 'SE' || cc === 'NO' ? 1 : 0} of={1} faint
                    label={cc === 'SE' || cc === 'NO'
                      ? 'Publishes an experience or age cross'
                      : 'No experience or age cross published'} /></td>
                  <td className="sub">{reading}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </details>

      <details className="disclosure panel">
        <summary style={{ cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
          Too few advertisements to quote a median pay figure
        </summary>
        <div style={{ marginTop: 10 }}>
          {postings?.pay_summary_by_country ? (
            <PublishedPayWithheld summary={postings.pay_summary_by_country}
              meta={postings.pay_summary_meta} minN={postings.pay_summary_min_n} spine={spine} />
          ) : <p className="sub">Openings summary unavailable.</p>}
        </div>
      </details>

      <details className="disclosure panel">
        <summary style={{ cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
          Beyond our fifteen — the harvest reaches further, uncovered here
        </summary>
        <div style={{ marginTop: 10 }}>
          {postings?.pay_summary_by_country ? (
            <PublishedPayBeyond15 summary={postings.pay_summary_by_country} spine={spine} />
          ) : <p className="sub">Openings summary unavailable.</p>}
        </div>
      </details>

      {/* `supported` is not optional here, and dropping it in the merge was the
        * worst thing package 17 did. computeEstimate() never reads
        * profile.occupation — the gate was the ONLY thing stopping it — so
        * without it /work?occupation=isco08:2511 printed "Your estimate ·
        * $135,980/yr" for Systems analysts, from the US SOFTWARE DEVELOPER row,
        * on the same screen that had just said no wage data resolves for that
        * occupation. A fabricated figure under a shareable URL, which is the
        * one thing this site exists not to do. Adversarial review finding 2. */}
      {wages && gradient && supported && (
        <PayVsCost profile={profile} wageByCountry={wageByCountry} gradient={gradient} />
      )}
      {/* The coverage map describes what the site can answer at all, so it is
        * still worth drawing when this occupation is not one of them — that is
        * exactly when a reader needs it. It reads `wages`, never the profile. */}
      {wages && gradient && <CoverageMap wages={wages} gradient={gradient} />}

      <p className="sub" style={{ marginTop: 14 }}>
        This page replaces <code>/position</code> and <code>/postings</code>; both still resolve
        here. <Link to="/openings">Every opening</Link> holds the full list with its filters and
        loads on demand; <Link to="/data/postings-seed">the seed list</Link> holds the companies and
        sources behind it.
      </p>
    </div>
  )
}
