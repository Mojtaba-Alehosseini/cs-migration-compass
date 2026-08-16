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
  min: number
  max: number
  currency: string
  period: 'year' | 'month' | 'hour'
  raw_text: string
  confidence: 'structured' | 'parsed_text'
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
  occupation: { occupation_key: string; confidence: 'high' | 'medium' | 'low' } | null
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
