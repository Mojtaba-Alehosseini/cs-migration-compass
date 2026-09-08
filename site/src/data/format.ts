/* Number and label formatting.
 *
 * One rule underpins all of it: a null NEVER formats as a number. It formats as
 * "no data", and callers pair that with a reason wherever they can. */

export const NO_DATA = 'no data'

const usd0 = new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', maximumFractionDigits: 0,
})

export function money(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return NO_DATA
  return usd0.format(v)
}

/** Compact money for dense cells: $104k, $1.2m. */
export function moneyShort(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return NO_DATA
  const abs = Math.abs(v)
  const sign = v < 0 ? '−' : ''
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1)}m`
  if (abs >= 1_000) return `${sign}$${Math.round(abs / 1_000)}k`
  return `${sign}$${Math.round(abs)}`
}

export function num(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return NO_DATA
  return v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return NO_DATA
  return `${v.toFixed(digits)}%`
}

/** Years-to-home. Long horizons are rounded because false precision on a
 *  40-year projection is theatre, and the impossible case says so in words.
 *
 *  Package 16 — the one-decimal form is gone. docs/DATA-FITNESS.md §2: the
 *  inputs are rounded to $10/month and $100/m², the quantity is a ratio whose
 *  denominator is a DIFFERENCE of two large numbers, and it is the most skewed
 *  field in the dataset (skew 6.38, excess kurtosis 41.1). "22.6 yrs" asserted
 *  a tenth of a year that no input could support. It now reads "~23 yrs", and
 *  `yearsRange` states the band where one rounding step moves it visibly. */
export function years(v: number | null | undefined, never = false): string {
  if (never) return 'never on this salary'
  if (v == null || !Number.isFinite(v)) return NO_DATA
  if (v >= 100) return '100+ yrs'
  // Rounding to a whole year is right at 23 years (±2%) and wrong at 1.2
  // (±42%, and it reads "1 yrs"). Below two years the year is no longer the
  // natural unit, so say it in months — which is a real precision the inputs
  // support, not a decimal place invented to look exact.
  if (v < 2) {
    const months = Math.round(v * 12)
    return months <= 1 ? '~1 month' : `~${months} months`
  }
  return `~${Math.round(v)} yrs`
}

/** Strip the leading "~" where a stronger approximation mark (the unstable "≈")
 *  is already rendered beside the figure. Stacking both read "≈~5 yrs". */
export function dropApprox(s: string): string {
  // Both marks, because the home question emits "≈never" as well as "~5 yrs"
  // — so the table rendered "≈≈never" for Milan, which is the exact stacking
  // this function exists to prevent.
  if (s.startsWith('~')) return s.slice(1)
  return s.startsWith('≈') ? s.slice(1) : s
}

/** The band a years-to-home figure occupies under one rounding step of its own
 *  inputs. Collapses to the point form when rounding hides nothing. */
export function yearsRange(range: [number, number] | null | undefined,
                           fallback: number | null | undefined, never = false): string {
  if (never) return 'never on this salary'
  if (!range) return years(fallback, never)
  const [lo, hi] = range
  if (lo >= 100) return '100+ yrs'
  const [rlo, rhi] = [Math.round(lo), Math.round(hi)]
  if (rlo === rhi) return years(fallback ?? lo)
  if (hi >= 100) return `~${rlo}–100+ yrs`
  return `~${rlo}–${rhi} yrs`
}

/** "~2 → ~5 yrs", or an honest phrase when there is no path at all. */
export function residencyRange(pr: number | null, citizenship: number | null): string {
  if (pr == null && citizenship == null) return 'no permanent path'
  if (pr == null) return `citizenship ~${citizenship} yrs`
  if (citizenship == null) return `~${pr} yrs to residency · no citizenship path`
  if (citizenship <= pr) return `~${pr} yrs`
  return `~${pr} → ~${citizenship} yrs`
}

/** Ranks are always shown with their denominator: "#17 of 147", never "6.882". */
export function rankOf(rank: number | null | undefined, of: number | null | undefined): string {
  if (rank == null) return NO_DATA
  if (of == null) return `#${rank}`
  return `#${rank} of ${of}`
}

export function asOfLabel(asOf: string | undefined): string {
  if (!asOf) return 'date unknown'
  const [y, m] = asOf.split('-')
  if (!m) return y ?? asOf
  const month = new Date(Number(y), Number(m) - 1, 1)
    .toLocaleString('en-US', { month: 'short' })
  return `${month} ${y}`
}

export const CONFIDENCE_LABEL = {
  official: 'Official',
  index: 'Research',
  crowd: 'Crowd',
} as const

export const CONFIDENCE_MARK = {
  official: '●',
  index: '◐',
  crowd: '○',
} as const

export const CONFIDENCE_MEANING = {
  official: 'From a government, central bank, statistics office or the UN.',
  index: 'From a large published yearly study or index.',
  crowd: 'Reported by individuals on sites like Numbeo or levels.fyi.',
} as const

/** Turn a source URL into something a human recognises. */
/** The real registrable host, no `www.` — the ONLY thing safe to match a
 *  source's identity against. Package 27: `city.sources.find(s =>
 *  s.includes('talent.com'))` matched `gulftalent.com` too (it contains the
 *  substring), so Dubai and Abu Dhabi displayed a citation named "talent.com"
 *  that linked to a different company. `.includes()` on a URL string is
 *  never safe for this — only the parsed hostname is. */
export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

/** The first URL in `sources` whose host is one of `hosts`, checked in the
 *  order `hosts` lists them — so a caller that prefers `bls.gov` over
 *  `api.bls.gov` when both exist just lists `bls.gov` first. Exact-host
 *  match only (see hostOf()); never a substring test. */
export function sourceUrlByHost(sources: string[], hosts: string[]): string | undefined {
  for (const h of hosts) {
    const hit = sources.find((s) => hostOf(s) === h)
    if (hit) return hit
  }
  return undefined
}

export function sourceName(url: string): string {
  const host = hostOf(url)
  if (!host) return url
  const known: Record<string, string> = {
    'numbeo.com': 'Numbeo',
    'levels.fyi': 'levels.fyi',
    'talent.com': 'talent.com',
    'payscale.com': 'PayScale',
    'expatistan.com': 'Expatistan',
    'bls.gov': 'US Bureau of Labor Statistics',
    'api.bls.gov': 'US Bureau of Labor Statistics',
    'api.worldbank.org': 'World Bank',
    'ec.europa.eu': 'Eurostat',
    'oecd.org': 'OECD',
    'sdmx.oecd.org': 'OECD',
    'stats.bis.org': 'BIS',
    'un.org': 'UN DESA',
    'population.un.org': 'UN Population Division',
    'worldhappiness.report': 'World Happiness Report',
    'files.worldhappiness.report': 'World Happiness Report',
    'rsf.org': 'Reporters Without Borders',
    'mipex.eu': 'MIPEX',
    'ef.com': 'EF Education First',
    'en.wikipedia.org': 'Wikipedia',
    'fhfa.gov': 'FHFA',
    'housepriceindex.ca': 'Teranet–National Bank',
    'publicdata.landregistry.gov.uk': 'HM Land Registry',
    'imf.org': 'IMF',
    // Package 27 — city salary-band sources, once matched by host instead of
    // guessed by whichever URL sat first in an unordered array.
    'gulftalent.com': 'GulfTalent',
    'indeed.com': 'Indeed',
    'au.indeed.com': 'Indeed',
    'it.indeed.com': 'Indeed',
    'seek.com.au': 'SEEK',
    'au.seek.com': 'SEEK',
    'ziprecruiter.com': 'ZipRecruiter',
    'glassdoor.com': 'Glassdoor',
    'glassdoor.es': 'Glassdoor España',
    'keepcoding.io': 'KeepCoding',
    'stepstone.de': 'StepStone',
    'techpays.com': 'TechPays',
  }
  return known[host] ?? host
}

/** Labels for a LIST of sources, disambiguated only where two of them collide.
 *
 *  sourceName() maps a URL to a label by HOST, which is right for a table with
 *  one row per source and wrong for a citation line that prints several. The
 *  UAE page ended "Wikipedia · Wikipedia · Wikipedia · worldpopulationreview" —
 *  three links, three different articles (visa policy, nationality law, the
 *  Golden Visa), one word. Six of fifteen country pages and 28 of 73 city
 *  pages printed a repeated label.
 *
 *  Only the colliding ones grow a suffix, so a list with no collision reads
 *  exactly as it did. The suffix is the page's own last path segment, which is
 *  what Wikipedia, gov.uk, migri.fi and nyidanmark.dk all put the document
 *  title in — never invented, and never a number the site does not have. */
export function sourceNames(urls: string[]): string[] {
  const base = urls.map(sourceName)
  const count = new Map<string, number>()
  for (const b of base) count.set(b, (count.get(b) ?? 0) + 1)
  return urls.map((u, i) => {
    const b = base[i] ?? u
    if ((count.get(b) ?? 0) < 2) return b
    /* Disambiguate on the part of the path that actually DIFFERS from the
     * others sharing this label — not simply the last segment.
     *
     * The last segment is right for Wikipedia (/wiki/H-1B_visa) and wrong for
     * levels.fyi, where three genuinely different pages — all levels, entry
     * level, senior — end in the SAME segment (new-york-city-area) and differ
     * in the middle. Taking the last segment there printed the same label
     * three times and claimed to have disambiguated it. */
    const siblings = urls.filter((_, j) => base[j] === b)
    const detail = distinguishingPart(u, siblings)
    /* Parentheses, NOT " · ". The citation line joins its items with " · ", so
     * a label containing one splits in the reader's eye exactly where it must
     * not: "Wikipedia · Second Trump travel ban · Wikipedia · H 1B visa" reads
     * as four sources where there are two. */
    return detail ? `${b} (${detail})` : b
  })
}

/** The part of `url`'s path that tells it apart from `siblings`, as human text.
 *
 *  The LAST segment first, because that is where a document's title lives —
 *  /wiki/H-1B_visa, /oes/2025/may/oessrcma.htm. Only if the siblings share it
 *  does this look further up, for the first position where this URL's own
 *  segment is unique among them: levels.fyi puts three genuinely different
 *  pages (all levels, entry level, senior) under the same final segment.
 *
 *  UNIQUE among the siblings, not merely DIFFERENT from one of them — the
 *  difference matters: /t/x/levels/entry-level/... and /t/x/levels/senior/...
 *  both differ from /t/x/locations/... at the same index, and taking that
 *  index printed "levels" twice and called it disambiguated. */
function distinguishingPart(url: string, siblings: string[]): string {
  const segs = pathSegments(url)
  if (!segs.length) return ''
  const others = siblings.filter((s) => s !== url).map(pathSegments)
  const last = segs.length - 1
  const uniqueAt = (i: number) => others.every((o) => o[i] !== segs[i])
  if (uniqueAt(last)) {
    const t = humanise(segs[last] ?? '')
    if (t) return t
  }
  for (let i = 0; i < segs.length; i++) {
    if (!uniqueAt(i)) continue
    const t = humanise(segs[i] ?? '')
    if (t) return t
  }
  return ''
}

function pathSegments(url: string): string[] {
  try {
    return new URL(url).pathname.split('/').filter(Boolean)
  } catch {
    return []
  }
}

/** A path segment as something a reader recognises, or '' if it is an opaque
 *  id rather than a title. */
function humanise(seg: string): string {
  let t: string
  try {
    t = decodeURIComponent(seg)
  } catch {
    t = seg
  }
  t = t
    .replace(/\.(html?|php|aspx?|pdf|csv|xlsx?|shtml|json|txt)$/i, '')
    .replace(/[_-]+/g, ' ')
    .trim()
    // A source URL that carries its own parenthesised note — one BLS entry
    // does — would otherwise print inside a second pair of them. AFTER trim:
    // that segment decodes with a leading space, so stripping first left the
    // opening bracket in place and printed "((OEWS series ...".
    .replace(/^\(+|\)+$/g, '')
    .trim()
  if (!t || /^\d+$/.test(t)) return ''
  return t.length > 38 ? `${t.slice(0, 37)}…` : t
}

export function cityPath(id: string) { return `/city/${id}` }
export function countryPath(id: string) { return `/country/${id}` }
