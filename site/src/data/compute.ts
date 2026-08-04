/* The site's arithmetic, in one file.
 *
 * These functions mirror data/metrics.json and scripts/build_site_data.py exactly.
 * They exist on the client because the budget is user-editable: the user changes
 * rent, and savings and years-to-home have to move with it. Every function
 * returns null rather than a fallback when an input is missing — a plausible
 * wrong number is worse than an honest gap. */

import type { Band, City, Computed, Country, Lens } from './types'

/** A user's edits to the assumptions behind a city's numbers.
 *  Anything left undefined falls back to the city's own figures. */
export interface Budget {
  rentUsd?: number
  livingUsd?: number
  /** Global multipliers, applied when no absolute override is set. */
  rentFactor?: number
  livingFactor?: number
}

export const HOME_M2 = 90

export function effectiveRent(city: City, b: Budget = {}): number | null {
  if (b.rentUsd != null) return b.rentUsd
  const base = city.rent_1br_outside_usd_month
  if (base == null) return null
  return base * (b.rentFactor ?? 1)
}

export function effectiveLiving(city: City, b: Budget = {}): number | null {
  if (b.livingUsd != null) return b.livingUsd
  const base = city.col_single_no_rent_usd_month
  if (base == null) return null
  return base * (b.livingFactor ?? 1)
}

export function grossFor(city: City, band: Band): number | null {
  return city.salary_usd_year[band] ?? null
}

export function netFor(city: City, band: Band): number | null {
  const gross = grossFor(city, band)
  if (gross == null || city.net_pct == null) return null
  return gross * (city.net_pct / 100)
}

export function savingsPerYear(city: City, band: Band, b: Budget = {}): number | null {
  const net = netFor(city, band)
  const rent = effectiveRent(city, b)
  const living = effectiveLiving(city, b)
  if (net == null || rent == null || living == null) return null
  return net - 12 * (rent + living)
}

/** Years to buy a 90 m² flat outside the centre.
 *  null when uncomputable OR when savings are <= 0 — in that case the answer is
 *  "never on this income", which the UI states in words rather than as a number
 *  like 2,314 that invites a reader to treat it as a real duration. */
export function yearsToHome(city: City, band: Band, b: Budget = {}): number | null {
  const savings = savingsPerYear(city, band, b)
  const perM2 = city.apt_price_outside_usd_m2
  if (savings == null || perM2 == null || savings <= 0) return null
  return (HOME_M2 * perM2) / savings
}

export function m2PerYear(city: City, band: Band, b: Budget = {}): number | null {
  const savings = savingsPerYear(city, band, b)
  const perM2 = city.apt_price_outside_usd_m2
  if (savings == null || perM2 == null) return null
  return Math.max(savings, 0) / perM2
}

/** True when the city has the inputs but simply cannot save anything. */
export function isNeverAffordable(city: City, band: Band, b: Budget = {}): boolean {
  const savings = savingsPerYear(city, band, b)
  return savings != null && savings <= 0 && city.apt_price_outside_usd_m2 != null
}

/** Which inputs are missing, for the "no data, and here's why" copy. */
export function missingInputs(city: City, band: Band): string[] {
  const missing: string[] = []
  if (grossFor(city, band) == null) missing.push('salary')
  if (city.net_pct == null) missing.push('tax rate')
  if (city.rent_1br_outside_usd_month == null) missing.push('rent')
  if (city.col_single_no_rent_usd_month == null) missing.push('living costs')
  if (city.apt_price_outside_usd_m2 == null) missing.push('apartment price')
  return missing
}

/** The salary lens: gross -> net -> what's actually left after living. */
export function salaryByLens(city: City, band: Band, lens: Lens, b: Budget = {}): number | null {
  if (lens === 'gross') return grossFor(city, band)
  if (lens === 'net') return netFor(city, band)
  return savingsPerYear(city, band, b)
}

export const LENS_LABEL: Record<Lens, string> = {
  gross: 'Gross, per year',
  net: 'After tax, per year',
  after: 'After tax, rent and living costs',
}

export const BAND_LABEL: Record<Band, string> = {
  new_grad: 'Starting out',
  mid: '3–5 years in',
  senior: 'Senior',
}

/** How a mid-level developer compares with the national average wage.
 *  Returns null unless we genuinely have the OECD figure — this powers the
 *  "1.8× the national average" line, which must never be asserted without it. */
export function devVsNationalAverage(
  city: City,
  band: Band,
  nationalAverageUsd: number | null,
): number | null {
  const gross = grossFor(city, band)
  if (gross == null || nationalAverageUsd == null || nationalAverageUsd <= 0) return null
  return gross / nationalAverageUsd
}

/** Staleness, per data/metrics.json. Returns null when as_of is unparseable. */
export function monthsOld(asOf: string | undefined, today = new Date()): number | null {
  if (!asOf) return null
  const [y, m] = asOf.split('-')
  const year = Number(y)
  const month = m ? Number(m) : 1
  if (!Number.isFinite(year) || !Number.isFinite(month)) return null
  return (today.getFullYear() - year) * 12 + (today.getMonth() + 1 - month)
}

export function isStale(asOf: string | undefined, limitMonths: number): boolean {
  const age = monthsOld(asOf)
  return age != null && age > limitMonths
}

/** Composite scoring for the opt-in weights tool.
 *  When a place is missing a metric, its weight is REDISTRIBUTED across the
 *  metrics that are present, and the amount redistributed is reported so the UI
 *  can disclose it. A composite that quietly treats missing as zero is a lie. */
export interface WeightedInput {
  value: number | null
  weight: number
  /** true when a higher raw value should score better */
  higherIsBetter: boolean
  /** min/max across all compared places, for normalisation */
  min: number
  max: number
}

export interface CompositeResult {
  score: number | null
  usedWeight: number
  missingWeight: number
  missingKeys: string[]
}

export function composite(inputs: Record<string, WeightedInput>): CompositeResult {
  let total = 0
  let used = 0
  let missing = 0
  const missingKeys: string[] = []

  for (const [key, i] of Object.entries(inputs)) {
    total += i.weight
    if (i.value == null || i.max === i.min) {
      missing += i.weight
      missingKeys.push(key)
      continue
    }
    const t = (i.value - i.min) / (i.max - i.min)
    const normalised = i.higherIsBetter ? t : 1 - t
    used += normalised * i.weight
  }

  const availableWeight = total - missing
  if (availableWeight <= 0) {
    return { score: null, usedWeight: 0, missingWeight: missing, missingKeys }
  }
  return {
    score: used / availableWeight,
    usedWeight: availableWeight,
    missingWeight: missing,
    missingKeys,
  }
}

/** Naive extrapolation — deliberately dumb, and labelled as such wherever drawn.
 *  Fits the average annual change of the last `window` points and extends it.
 *  This is NOT a forecast and must never be merged with an institutional one. */
export function naiveExtrapolate(
  points: { year: number; value: number }[],
  toYear: number,
  window = 10,
): { year: number; value: number }[] {
  if (points.length < 2) return []
  const sorted = [...points].sort((a, b) => a.year - b.year)
  const recent = sorted.slice(-window)
  const first = recent[0]
  const last = recent[recent.length - 1]
  if (!first || !last || last.year === first.year) return []

  const slope = (last.value - first.value) / (last.year - first.year)
  const out: { year: number; value: number }[] = []
  for (let y = last.year + 1; y <= toYear; y++) {
    out.push({ year: y, value: last.value + slope * (y - last.year) })
  }
  return out
}

/** Apply a country trend to a city's current value.
 *  The result MUST be rendered with the label
 *  "city estimate = current value x country trend" — see §2c of the brief. */
export function applyCountryTrend(
  cityCurrentValue: number,
  countrySeries: { year: number; value: number }[],
): { year: number; value: number; isCityEstimate: true }[] {
  if (countrySeries.length === 0) return []
  const sorted = [...countrySeries].sort((a, b) => a.year - b.year)
  const latest = sorted[sorted.length - 1]
  if (!latest || latest.value === 0) return []
  return sorted.map((p) => ({
    year: p.year,
    value: cityCurrentValue * (p.value / latest.value),
    isCityEstimate: true as const,
  }))
}

export function computedOrLive(city: City, band: Band, b: Budget): Computed {
  const hasEdits =
    b.rentUsd != null || b.livingUsd != null || b.rentFactor != null || b.livingFactor != null
  if (!hasEdits) return city.computed[band]
  return {
    gross_usd: grossFor(city, band),
    net_usd: netFor(city, band),
    monthly_rent_usd: effectiveRent(city, b),
    monthly_living_usd: effectiveLiving(city, b),
    savings_usd_year: savingsPerYear(city, band, b),
    years_to_home: yearsToHome(city, band, b),
    m2_per_year: m2PerYear(city, band, b),
    missing_inputs: city.computed[band].missing_inputs,
  }
}

export function countryOf(city: City, countries: Country[]): Country | undefined {
  return countries.find((c) => c.id === city.country)
}
