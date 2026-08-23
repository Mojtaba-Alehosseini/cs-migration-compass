/* Package 12 — advertised pay, loaded and typed separately from explore.ts's
 * own survey-earnings data on purpose. The work order's own Tier 5.1 (and
 * phase-4-salary-and-cv-plan.md's own S2.4) are explicit: what employers
 * ADVERTISE while hiring and what people ARE PAID (Eurostat, ONS, SCB, the
 * whole wage spine explore.ts already serves) are two different quantities,
 * never merged into one number. Keeping them in two files that never import
 * each other is that rule enforced structurally, not just by convention —
 * the same discipline scripts/build_postings.py's own module docstring
 * states for the Python side.
 */

import { loadHistory } from './store'

export interface Compensation {
  /** The employer's own figures, in the employer's own currency. Never
   *  rewritten, never withheld, and the default everywhere pay is shown. */
  min: number
  max: number
  currency: string
  period: 'year' | 'month' | 'hour'
  raw_text: string
  confidence: 'structured' | 'parsed_text'
  /** Package 17 — the converted view, present only when a rate existed within
   *  normalise.MAX_FX_GAP_YEARS of this posting's own year. `estimated` is true
   *  when the rate came from a different year than the posting; `fx_year` is
   *  the year actually used and `fx_year_requested` the one asked for. A
   *  consumer can therefore mark a substituted conversion without re-deriving
   *  why it was substituted, and there is no shape in which a substituted rate
   *  arrives looking exact. */
  usd?: {
    min: number
    max: number
    fx_rate: number
    fx_year: number
    fx_source: string
    fx_country_used: string
    estimated: boolean
    fx_gap_years: number
    fx_year_requested: number
  } | null
}

export interface Posting {
  id: string
  provider: string
  company: string | null
  company_slug: string
  title: string | null
  location_raw: string | null
  country: string | null
  remote: boolean | null
  url: string | null
  posted_at: string | null
  compensation: Compensation | null
  /** ISCO-08 code from the Gemini classifier. Still null on every row — that
   *  classifier has never run. Do NOT populate it from `title_class`: those are
   *  coarse job families, not ISCO codes, and conflating them would invite
   *  comparison against the wage spine, which the standing rules forbid. */
  occupation: { occupation_key: string; confidence: 'high' | 'medium' | 'low' } | null
  /* Package 16 — `title_class` and `duplicate_of` are NOT declared here on
   * purpose, because they are NOT SHIPPED. Both exist on every row in
   * data/processed/postings.json, which is what the analysis scripts read, and
   * build_site_data.py strips them before writing the browser payload: nothing
   * in site/src reads either one, and carrying them cost 15 Lighthouse points
   * on /postings, measured. Declaring them optional would be a type that lies —
   * it would promise a field that never arrives and invite code that silently
   * does nothing. If a category filter is built, ship them and declare them
   * together. The AGGREGATES are shipped and typed below:
   * `title_class_summary`, `duplicate_summary`, `pay_summary_by_country`. */
}

export interface SeedCompany {
  provider: string
  company_slug: string
  company: string | null
  job_count: number
}

export interface PostingsData {
  postings: Posting[]
  provider_summary: Record<string, { available: boolean; postings_count?: number; compensation_present_count?: number; generated_at?: string }>
  seed_companies: Record<string, SeedCompany>
  country_counts: Record<string, number>
  /** Package 14 — median USD/year advertised pay per country (n>=5, top 12,
   *  sorted descending), computed at build time (build_postings.py) rather
   *  than re-derived client-side from the full `postings` array on every
   *  page load — a real Lighthouse performance regression this package's
   *  own postings recovery caused (history/postings.json's own resource
   *  size grew to ~20MB). Same USD-denominated-annual-only filter the
   *  client-side version used, computed identically, just not in the
   *  browser. Named `pay_summary_by_country` / `median_usd_year`, not the
   *  first-tried `advertised_by_country` / `median` — found live by this
   *  package's own validate_data.py run: "advertised" + a bare "median" in
   *  the same file is exactly the field-name collision
   *  check_survey_vs_advertised_pay exists to catch (package 7's own rule
   *  2), a real trigger to respect by naming this unambiguously, not to
   *  silence. See build_postings.py's own comment at this field's
   *  construction for the full reasoning. */
  /** Package 16 — re-derived on DISTINCT ROLES (duplicates excluded) and
   *  restricted to titles the classifier ships as software. A country appears
   *  with a median only if it clears `pay_summary_min_n`; the rest carry
   *  `publishable: false` and a `withheld_reason`, and are shown as counts
   *  rather than dropped, because "we harvested 21 GB postings and 13 of them
   *  are software" is a true and useful statement while a median of 13 is not.
   *  `*_published_*` fields are rounded to the nearest $1,000: §0-D measured
   *  advertised pay heaped to round thousands, so a median of it resolves no
   *  finer, and the cents the old field carried were created by FX conversion
   *  rather than by any employer. */
  pay_summary_by_country: {
    country: string
    n_as_published: number
    n_deduped: number
    n_software_only: number
    n_software_all_years?: number
    published_from_year?: number
    /** The pooled-every-vintage median. A DIAGNOSTIC, never rendered as a
     *  headline: it is the number that mixed 2016 federal listings with 2026
     *  private ones and landed between them. */
    diagnostic_median_all_years_usd_year?: number | null
    composition?: {
      by_year: Record<string, number>
      by_provider: Record<string, number>
      share_from_latest_year_pct: number
      largest_provider: string
      largest_provider_share_pct: number
      caveat: string
    }
    median_as_published_usd_year: number | null
    median_usd_year?: number
    median_published_usd_year?: number
    ci_lo_published_usd_year?: number
    ci_hi_published_usd_year?: number
    ci_quality?: { n: number; do_not_quote: boolean; below_min_n_for_ci: boolean }
    delta_vs_as_published_pct?: number
    publishable: boolean
    withheld_reason: string | null
  }[]
  pay_summary_meta?: {
    basis: string
    min_n_to_publish: number
    published_rounding_usd: number
    rounding_reason: string
    n_publishable: number
    n_countries_considered: number
    midpoint_caveat: string
  }
  title_class_summary?: {
    shipped_classes: string[]
    counts: Record<string, number>
    caveat: string
  }
  display_fx?: {
    pivot: string
    rates: Record<string, { rate: number; year: number }>
    source: string
    note: string
  }
  duplicate_summary?: {
    raw_rows: number
    distinct_roles: number
    re_listings: number
    re_listings_pct: number
    reading: string
  }
  /** The N in "n>=N" above — shipped alongside the data itself (adversarial
   *  review L11) so the on-screen caption naming this threshold reads the
   *  one number that actually governs the filter, not a second,
   *  separately-maintained copy that build_postings.py's own MIN_CHART_N
   *  could drift from silently. */
  pay_summary_min_n: number
}

/** Package 14 — found gathering this package's own Lighthouse evidence: the
 *  seed-list transparency page (PostingsSeed.tsx) only ever reads these
 *  three fields, but was fetching the FULL `postings` array (~20MB, the
 *  same resource NEEDS-DECISION #38 already names as /postings' own
 *  dominant CPU cost) to get them — paying that cost a second time on a
 *  page that never touches the array at all. build_postings.py now writes
 *  this as its own small, separate file (verbatim copies of the same
 *  fields, never re-derived) — see that file's own comment at its
 *  construction. */
export interface PostingsSeedSummary {
  provider_summary: PostingsData['provider_summary']
  seed_companies: Record<string, SeedCompany>
  country_counts: Record<string, number>
}

export async function loadPostingsSeedSummary(): Promise<PostingsSeedSummary> {
  const h = await loadHistory<PostingsSeedSummary>('postings_seed_summary')
  return h.data
}

export async function loadPostings(): Promise<PostingsData> {
  const h = await loadHistory<PostingsData>('postings')
  return h.data
}

/** Every provider this package's own harvesters can produce, whether or not
 *  its own JSON file has been built yet in this checkout — drives the
 *  "N providers" claims on the seed-list page without silently hiding a
 *  provider that just hasn't run. */
export const KNOWN_PROVIDERS = ['ashby', 'greenhouse', 'lever', 'teamtailor', 'usajobs', 'hn'] as const

export const PROVIDER_LABEL: Record<string, string> = {
  ashby: 'Ashby', greenhouse: 'Greenhouse', lever: 'Lever', teamtailor: 'Teamtailor',
  usajobs: 'USAJOBS (U.S. federal)', hn: 'Hacker News "Who is hiring?"',
}

/** Whichever provider a posting comes from, is compensation a real
 *  structured field this provider ever fills in for anyone (Ashby,
 *  Greenhouse, Lever, USAJOBS, HN), or a provider whose own data never
 *  carried one in this pipeline's own harvest (Teamtailor, SmartRecruiters,
 *  Workable — see NEEDS-DECISION.md) — shown on the seed-list page so
 *  "0 postings have pay" reads as "this source doesn't publish it" rather
 *  than looking like a bug. */
export const PROVIDER_HAS_COMPENSATION_FIELD: Record<string, boolean> = {
  ashby: true, greenhouse: true, lever: true, usajobs: true, hn: true, teamtailor: false,
}

/** Each provider's own license_note, as recorded in data/provenance.json at
 *  harvest time (scripts/src_postings_*.py) — restated here, not re-derived,
 *  so the page names the same basis the harvester itself recorded. USAJOBS
 *  is deliberately NOT called "public domain": 17 U.S.C. §105 means no US
 *  copyright ever attached, a different legal basis than a rights-holder's
 *  own CC0 waiver, and collapsing the two would misstate it. */
export const PROVIDER_LICENSE: Record<string, string> = {
  ashby: "Each company's own postings, published via Ashby's own public, unauthenticated job-board API — no Ashby-specific license terms apply beyond the postings being intentionally public.",
  greenhouse: "Each company's own postings, published via Greenhouse's own public, unauthenticated Job Board API.",
  lever: "Each company's own postings, published via Lever's own public, unauthenticated postings API.",
  teamtailor: "Each company's own postings, published via Teamtailor's own public, unauthenticated JSON Feed — no Teamtailor-specific license terms apply.",
  usajobs: '17 U.S.C. §105 — U.S. federal government works carry no US copyright. NOT CC0: §105 means no copyright ever existed here, a different legal basis than a rights-holder’s own waiver. Attribute as "USAJOBS / U.S. OPM".',
  hn: "Public Hacker News API (hacker-news.firebaseio.com) — each comment is the poster's own public submission to a public forum thread, redistributed here as individual job-posting text.",
}

/** Ashby's and Lever's own public APIs publish no company display name at
 *  all (checked live against real cached responses — not an extraction
 *  bug this pipeline had; see postings_common.py's own record-shape
 *  docstring). Every row from those two providers falls back to the
 *  company_slug (738/738 Ashby companies, 215/215 Lever, confirmed by this
 *  package's own adversarial review) — shown raw and lowercase before this
 *  fix ("3y-health", "airops"). This turns the SAME token into a readable
 *  label without inventing a name the source never published. */
export function fmtCompany(company: string | null, slug: string): string {
  if (company) return company
  return slug
    .split(/[-_]+/)
    .filter(Boolean)
    .map((w) => (w.length <= 3 && w === w.toLowerCase() ? w.toUpperCase() : w[0]!.toUpperCase() + w.slice(1)))
    .join(' ')
}

export function fmtCompensation(c: Compensation | null): string {
  if (!c) return ''
  const fmt = (v: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: c.currency, maximumFractionDigits: 0, notation: v >= 1000 ? 'compact' : 'standard' }).format(v)
  const period = { year: '/yr', month: '/mo', hour: '/hr' }[c.period]
  return `${fmt(c.min)}–${fmt(c.max)}${period}`
}
