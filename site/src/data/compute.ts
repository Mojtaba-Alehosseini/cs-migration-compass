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
  /** Package 10, tier 4: a user-chosen annual USD salary (e.g. a profile's
   *  own percentile position or estimate), overriding the city's own
   *  published salary_usd_year[band]. Everything downstream — net, savings,
   *  years-to-home, and the stability guard — has to move with it exactly
   *  the way it already moves with a rent/living edit, because a
   *  user-picked percentile in an expensive city is precisely the small-
   *  denominator case the guard exists for, and the numerator is now a
   *  number the user picked rather than one this site vetted. */
  salaryUsdYearOverride?: number
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

export function grossFor(city: City, band: Band, b: Budget = {}): number | null {
  return b.salaryUsdYearOverride ?? city.salary_usd_year[band] ?? null
}

export function netFor(city: City, band: Band, b: Budget = {}): number | null {
  const gross = grossFor(city, band, b)
  if (gross == null || city.net_pct == null) return null
  return gross * (city.net_pct / 100)
}

export function savingsPerYear(city: City, band: Band, b: Budget = {}): number | null {
  const net = netFor(city, band, b)
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

/* ---------------------------------------------------------------------------
 * Is this number bigger than its own error bars?
 *
 * savings_usd_year is a DIFFERENCE of two large numbers, and years-to-home
 * divides by it. Rent and living costs are each published to $10/month, so both
 * moving one step is $240/year. A savings figure smaller than that is the
 * rounding on its inputs, not a measurement — and dividing by it reports a
 * ratio to four significant figures that the inputs cannot support.
 *
 * Milan is the live example: $210 saved a year is $17.50 a month. Move its rent
 * by one step and years-to-home goes 2,314 → 1,080, or disappears entirely.
 *
 * The threshold is not chosen, it is the inputs' own precision. We do not
 * suppress the number — we mark it and say what is wrong with it.
 * ------------------------------------------------------------------------- */

/** One published rounding step on each of rent and living costs, for a year. */
export const SAVINGS_PRECISION_USD_YEAR = 12 * 10 * 2

/** How far years-to-home may move under that perturbation before the figure is
 *  reporting precision it does not have. */
export const STABILITY_TOLERANCE = 0.25

export type Stability = 'stable' | 'unstable'

/** Years-to-home with savings shifted by `delta`, for the perturbation test. */
function yearsToHomeShifted(city: City, band: Band, b: Budget, delta: number): number | null {
  const savings = savingsPerYear(city, band, b)
  const perM2 = city.apt_price_outside_usd_m2
  if (savings == null || perM2 == null) return null
  const shifted = savings + delta
  if (shifted <= 0) return null
  return (HOME_M2 * perM2) / shifted
}

/** Package 16 — docs/DATA-FITNESS.md §2 rules a one-decimal years-to-home
 *  unsupportable: the inputs are rounded to $10/month and $100/m², and the
 *  output is the most skewed field in the dataset (skew 6.38, excess kurtosis
 *  41.1). This returns the interval the figure actually occupies under one
 *  rounding step of its own inputs — the same perturbation the stability flag
 *  uses, reported rather than reduced to a boolean. */
export function yearsToHomeRange(city: City, band: Band, b: Budget = {}): [number, number] | null {
  const base = yearsToHome(city, band, b)
  if (base == null) return null
  const alts: number[] = [base]
  for (const delta of [SAVINGS_PRECISION_USD_YEAR, -SAVINGS_PRECISION_USD_YEAR]) {
    const alt = yearsToHomeShifted(city, band, b, delta)
    if (alt == null) return null      // one step removes the figure entirely
    alts.push(alt)
  }
  return [Math.min(...alts), Math.max(...alts)]
}

/** `'unstable'` when one rounding step on the inputs moves years-to-home by more
 *  than a quarter, or removes it altogether. `null` when there is no figure to
 *  judge. Against the live data this flags exactly Milan and Valencia; the worst
 *  of the other 70 moves 11%. */
export function yearsToHomeStability(city: City, band: Band, b: Budget = {}): Stability | null {
  const base = yearsToHome(city, band, b)
  if (base == null) return null
  for (const delta of [SAVINGS_PRECISION_USD_YEAR, -SAVINGS_PRECISION_USD_YEAR]) {
    const alt = yearsToHomeShifted(city, band, b, delta)
    if (alt == null) return 'unstable'
    if (Math.abs(alt - base) / base > STABILITY_TOLERANCE) return 'unstable'
  }
  return 'stable'
}

/** The three savings-derived metrics share one root cause, so they share one
 *  flag: if years-to-home is unstable here, what the city saves in a year is
 *  too small to divide by, and `m2_per_year` and `savings` inherit that. */
export const UNSTABLE_METRIC_KEYS = new Set(['years_to_home', 'm2_per_year', 'savings'])

/** Read the flag the pipeline already computed, falling back to computing it —
 *  needed when the user has edited the budget and the shipped figure no longer
 *  applies. */
export function stabilityOf(city: City, band: Band, b: Budget = {}): Stability | null {
  const hasEdits =
    b.rentUsd != null || b.livingUsd != null || b.rentFactor != null || b.livingFactor != null
    || b.salaryUsdYearOverride != null
  if (!hasEdits) {
    const shipped = city.computed?.[band]?.years_to_home_stability
    if (shipped) return shipped
  }
  return yearsToHomeStability(city, band, b)
}

/** The sentence that goes on the source card and in the export. Plain words,
 *  the actual figure, and what to do with it. */
export function instabilityNote(city: City, band: Band, b: Budget = {}): string | null {
  if (stabilityOf(city, band, b) !== 'unstable') return null
  const savings = savingsPerYear(city, band, b)
  const amount = savings == null ? 'What is left at the end of a year here' : `What’s left at the end of a year here — $${Math.round(savings).toLocaleString('en-US')} —`
  return `${amount} is smaller than the rounding on its own rent figure. `
    + 'A $20 change in either direction moves this number by thousands of years, or removes it '
    + 'entirely. Read it as “effectively out of reach”, not as a count of years.'
}

/** Which inputs are missing, for the "no data, and here's why" copy.
 *  Takes an optional Budget (package 10, tier 4) so a salary override can
 *  supply the one input a city itself lacks for this band — "salary" is
 *  never reported missing when the caller handed one in directly. */
export function missingInputs(city: City, band: Band, b: Budget = {}): string[] {
  const missing: string[] = []
  if (grossFor(city, band, b) == null) missing.push('salary')
  if (city.net_pct == null) missing.push('tax rate')
  if (city.rent_1br_outside_usd_month == null) missing.push('rent')
  if (city.col_single_no_rent_usd_month == null) missing.push('living costs')
  if (city.apt_price_outside_usd_m2 == null) missing.push('apartment price')
  return missing
}

/** The salary lens: gross -> net -> what's actually left after living. */
export function salaryByLens(city: City, band: Band, lens: Lens, b: Budget = {}): number | null {
  if (lens === 'gross') return grossFor(city, band, b)
  if (lens === 'net') return netFor(city, band, b)
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
    || b.salaryUsdYearOverride != null
  if (!hasEdits) return city.computed[band]
  return {
    gross_usd: grossFor(city, band, b),
    net_usd: netFor(city, band, b),
    monthly_rent_usd: effectiveRent(city, b),
    monthly_living_usd: effectiveLiving(city, b),
    savings_usd_year: savingsPerYear(city, band, b),
    years_to_home: yearsToHome(city, band, b),
    // Recomputed, not carried over: an edited budget can move a figure across
    // the stability line in either direction.
    years_to_home_stability: yearsToHomeStability(city, band, b),
    m2_per_year: m2PerYear(city, band, b),
    missing_inputs: city.computed[band].missing_inputs,
  }
}

export function countryOf(city: City, countries: Country[]): Country | undefined {
  return countries.find((c) => c.id === city.country)
}
