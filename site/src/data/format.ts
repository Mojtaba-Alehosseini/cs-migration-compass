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
 *  40-year projection is theatre, and the impossible case says so in words. */
export function years(v: number | null | undefined, never = false): string {
  if (never) return 'never on this salary'
  if (v == null || !Number.isFinite(v)) return NO_DATA
  if (v >= 100) return '100+ yrs'
  if (v >= 30) return `${Math.round(v)} yrs`
  return `${v.toFixed(1)} yrs`
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
export function sourceName(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '')
    const known: Record<string, string> = {
      'numbeo.com': 'Numbeo',
      'levels.fyi': 'levels.fyi',
      'talent.com': 'talent.com',
      'payscale.com': 'PayScale',
      'expatistan.com': 'Expatistan',
      'bls.gov': 'US Bureau of Labor Statistics',
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
    }
    return known[host] ?? host
  } catch {
    return url
  }
}

export function cityPath(id: string) { return `/city/${id}` }
export function countryPath(id: string) { return `/country/${id}` }
