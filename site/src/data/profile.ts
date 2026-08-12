/* Package 10 — the profile, the position, and the estimate.
 *
 * "The site does not estimate a person. It locates them." Two numbers, two
 * different kinds of claim, enforced by which component renders them:
 *
 *   POSITION  a rank within a country's own published distribution
 *             (P10/P25/median/P75/P90 from wage_distribution.json, already
 *             resolved by scripts/build_wage_distribution.py — this module
 *             re-derives NOTHING from raw salary_*.json). Sourced, so a
 *             <Figure>, always the published median (P50) — never
 *             personalised by years of experience. An earlier version of
 *             this module personalised Spain's own position by ranking an
 *             INE tenure-band figure against Spain's IT-specific percentile
 *             table; an independent review (finding F2/F3, tier 7 of this
 *             package's own adversarial review) found that INE's tenure
 *             cross is for a BROADER occupational population (CNO-11
 *             "Scientific and intellectual technicians and professionals",
 *             mean ~14% above Spain's own IT-specific median) — ranking a
 *             different population's figure against this one's percentile
 *             table produced a position that could disagree with the
 *             estimate computed from the very same inputs, and dressed a
 *             genuinely modelled number in <Figure>'s "official" confidence.
 *             Removed rather than patched: there is no IT-specific tenure
 *             cross to rank against instead, so the honest fix is to not
 *             personalise the position at all. See NEEDS-DECISION.md #20.
 *
 *   ESTIMATE  a country's own median, shifted by the universal experience
 *             gradient (data/processed/experience_gradient.json, built
 *             from Spain's tenure cross — see that file's own module
 *             docstring for why Spain and not Sweden/Norway's age crosses).
 *             A model, so a <Derived>, never a <Figure> — the SAME
 *             population mismatch above applies here too, but is far less
 *             misleading on a component that already discloses "this is a
 *             method, not a source" and already carries the relative-shift
 *             assumption in its own chain (see _shiftEstimate's own
 *             "not IT-specific" chain step, added alongside this fix).
 *             Available for every country with at least a quartile spread
 *             to clamp against — absent for central-tendency-only/mean-only
 *             countries (nothing to clamp), matching the position's own
 *             absence there.
 *
 * Both functions also refuse (return not-ok) when scripts/crosswalk.py's own
 * comparability verdict (row.crosswalk.comparable) is false — an earlier
 * version of this module checked only distribution shape, so a country the
 * crosswalk itself had refused (the Netherlands: "no ISCO-08 correspondence
 * at all for this occupation") still rendered a full position and estimate.
 * Caught by the same adversarial review (finding F1) as the population-
 * mismatch above: this module consumes crosswalk.py's verdict, the same
 * "never re-derive the rule, never skip the check" discipline
 * build_wage_distribution.py's own docstring establishes.
 *
 * Both are pure functions over already-resolved data (wage_distribution.json,
 * experience_gradient.json) — no fetch, no re-derivation of crosswalk.py or
 * normalise.py's own verdicts, the same discipline explore.ts and compute.ts
 * already hold to for every other computed number on this site.
 */

import { loadHistory } from './store'
import type { WageCountry, WageStats } from './explore'

export interface Profile {
  /** A shared_keys registry key from data/occupations.json, e.g. "isco08:2512". */
  occupation: string
  yearsProfessional: number
  /** Where they are now — optional. Highlights the matching row in the
   *  position/estimate table (site/src/routes/Position.tsx's CountryRow).
   *  NOT joined into Tier 4's pay-vs-cost panel, which reads its own cities
   *  from the shared Selection instead — an earlier version of this comment
   *  claimed it fed that join; it never did (finding F17, adversarial
   *  review). Kept here rather than wiring a real join under review-driven
   *  time pressure: the two features solve different problems (a profile's
   *  home country vs. a shortlist of candidate cities to compare), and
   *  conflating them would need its own design decision, not a quick patch. */
  country?: string
}

/* ------------------------------------------------------------ gradient --- */

export interface GradientPoint {
  years: number; upper_edge_years_exclusive: number | null; band_label: string
  eur_year: number; premium_pct: number
}
export interface ContextPoint {
  years_midpoint_approx: number; band_label: string; premium_pct: number
  sek_month?: number; nok_month?: number
}
export interface ExperienceGradient {
  gradient: {
    curve: GradientPoint[]
    meta: { source: string; year: number; total_eur_year: number; measures: string }
    interpolation: string
  }
  context: {
    se_age: { curve: ContextPoint[]; meta: { source: string; year: number; measures: string } }
    no_age: { curve: ContextPoint[]; meta: { source: string; quarter: string; measures: string } }
  }
}

export async function loadExperienceGradient(): Promise<ExperienceGradient> {
  const h = await loadHistory<ExperienceGradient>('experience_gradient')
  return h.data
}

/** Piecewise-linear interpolation between the gradient's own real points,
 *  clamped at both ends — never extrapolated past what Spain's tenure cross
 *  actually measured. Mirrors the SAME clamp discipline distributionPosition()
 *  below applies to percentiles: a number this pipeline did not measure does
 *  not get invented past the edge of what it did measure. */
export function gradientPremiumPct(years: number, curve: GradientPoint[]): { pct: number; clamped: 'low' | 'high' | null } {
  const pts = [...curve].sort((a, b) => a.years - b.years)
  if (years <= pts[0]!.years) return { pct: pts[0]!.premium_pct, clamped: years < pts[0]!.years ? 'low' : null }
  const last = pts[pts.length - 1]!
  if (years >= last.years) return { pct: last.premium_pct, clamped: years > last.years ? 'high' : null }
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i]!, b = pts[i + 1]!
    if (years >= a.years && years <= b.years) {
      const t = (years - a.years) / (b.years - a.years)
      return { pct: a.premium_pct + t * (b.premium_pct - a.premium_pct), clamped: null }
    }
  }
  return { pct: pts[0]!.premium_pct, clamped: null } // unreachable given the bounds checks above
}

/* --------------------------------------------------------- percentiles --- */

const PCT_FIELDS: { field: keyof WageStats; pct: number }[] = [
  { field: 'p10', pct: 10 }, { field: 'p25', pct: 25 }, { field: 'median', pct: 50 },
  { field: 'p75', pct: 75 }, { field: 'p90', pct: 90 },
]

/** The real, published (percentile, value) points a country's own table
 *  offers — whichever of p10/p25/median/p75/p90 are non-null, in order.
 *  Never invents a point the source did not publish. */
export function knownPercentilePoints(stats: WageStats): { pct: number; value: number }[] {
  return PCT_FIELDS
    .filter((f) => stats[f.field] != null)
    .map((f) => ({ pct: f.pct, value: stats[f.field] as number }))
}

/** scripts/crosswalk.py's own comparability verdict, checked before either
 * function below does anything else — a country the crosswalk itself
 * refused (e.g. the Netherlands: "no ISCO-08 correspondence at all for this
 * occupation") must never render a position or an estimate, regardless of
 * whether it happens to publish a real percentile spread. Consumes the
 * verdict `resolve_country()` already computed; never re-derives it.
 * Finding F1, adversarial review — see this module's own header comment. */
function _notComparable(row: WageCountry): string | null {
  if (row.crosswalk.comparable) return null
  return row.crosswalk.reason ?? `${row.country}'s occupation match was refused by the crosswalk`
}

export interface RankResult { pct: number; clamped: 'low' | 'high' | null }

/** Where `value` ranks among a country's own real published percentile
 *  points, by linear interpolation between the two nearest ones. Clamps
 *  (does not extrapolate) past the lowest/highest point this table
 *  actually publishes — the work order's own "P1-P99" clamp language,
 *  applied to whatever bounds THIS table really has, not an invented P1/P99
 *  no source here publishes. */
export function rankWithinDistribution(value: number, points: { pct: number; value: number }[]): RankResult | null {
  if (points.length < 2) return null // nothing to interpolate against — position/estimate are absent here
  const pts = [...points].sort((a, b) => a.value - b.value)
  if (value <= pts[0]!.value) return { pct: pts[0]!.pct, clamped: value < pts[0]!.value ? 'low' : null }
  const last = pts[pts.length - 1]!
  if (value >= last.value) return { pct: last.pct, clamped: value > last.value ? 'high' : null }
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i]!, b = pts[i + 1]!
    if (value >= a.value && value <= b.value) {
      const t = (value - a.value) / (b.value - a.value)
      return { pct: a.pct + t * (b.pct - a.pct), clamped: null }
    }
  }
  return null
}

/* ------------------------------------------------------------ estimate --- */

export interface EstimateStep { op: string; detail: string }
export type EstimateResult =
  | { ok: true; value: number; currency: string; chain: EstimateStep[]; clamped: 'low' | 'high' | null }
  | { ok: false; reason: string }

/** The shared core: shift `stats`'s own central figure by the universal
 *  gradient, clamped to `stats`'s own published bounds. Used for both the
 *  native-currency estimate (Tier 3's own displayed number) and the
 *  USD-annual estimate (Tier 4's stabilityOf() override) — same math,
 *  different currency's own percentile table, never a client-side FX
 *  conversion of one into the other (that would re-derive normalise.py's
 *  own job; the USD combo is already resolved by build_wage_distribution.py). */
function _shiftEstimate(
  countryLabel: string, stats: WageStats, currency: string,
  years: number, gradient: ExperienceGradient,
): EstimateResult {
  const points = knownPercentilePoints(stats)
  if (points.length < 2) {
    return { ok: false, reason: `${countryLabel} publishes only a distribution too narrow to shift within or `
      + 'clamp against (need at least two of p10/p25/median/p75/p90)' }
  }
  const central = stats.median ?? stats.mean
  if (central == null) return { ok: false, reason: `${countryLabel} has no median or mean to shift` }

  const gRaw = gradientPremiumPct(years, gradient.gradient.curve)
  // Rounded to the same precision the chain step displays, THEN used for the
  // actual arithmetic — not the other way around. An earlier version
  // computed `raw` from the full-precision premium but displayed a
  // toFixed(3) multiplier, so hand-multiplying the two shown numbers never
  // reproduced the shown result (5,100 x 0.657 displayed as 3,350.19, but
  // 5,100 x 0.657 is actually 3,350.70) — on a site whose own stated bar is
  // "reproducible by hand from the cited tables", the one component built
  // to show its own working failed that bar. Finding F15, adversarial
  // review. The rounding this introduces into the estimate itself (at most
  // a few hundredths of a percent) is immaterial next to a number that is
  // already a disclosed model, not a measurement.
  const pct = Math.round(gRaw.pct * 10) / 10
  const multiplier = 1 + pct / 100
  const raw = central * multiplier

  const lo = points[0]!, hi = points[points.length - 1]!
  let value = raw
  let clamped: 'low' | 'high' | null = null
  if (raw < lo.value) { value = lo.value; clamped = 'low' }
  else if (raw > hi.value) { value = hi.value; clamped = 'high' }

  const gradientPts = gradient.gradient.curve
  const gradientEdge = gRaw.clamped === 'low' ? gradientPts[0] : gradientPts[gradientPts.length - 1]
  const chain: EstimateStep[] = [
    { op: 'gradient', detail: `${years} years -> ${pct >= 0 ? '+' : ''}${pct.toFixed(1)}% `
      + `(Spain's own INE tenure cross, ${gradient.gradient.meta.year}, "Scientific and intellectual `
      + 'technicians and professionals" — a broader population than this occupation; the SHAPE of the '
      + 'tenure-pay relationship is assumed to transfer, the absolute wage level is not — see the '
      + "gradient's own method card)"
      + (gRaw.clamped
        ? ` — held at the ${gRaw.clamped === 'low' ? 'lowest' : 'highest'} band this pipeline models `
          + `("${gradientEdge?.band_label}", ${gradientEdge?.years} years): INE's own tenure bands are `
          + `modelled at each band's own midpoint, so ${years} years is ${gRaw.clamped === 'low' ? 'below' : 'above'} `
          + 'that reference point even though it may fall inside the band itself — not extrapolated further'
        : '') },
    { op: 'shift', detail: `${central.toLocaleString()} x ${multiplier.toFixed(3)} = ${raw.toLocaleString(undefined, { maximumFractionDigits: 2 })}` },
  ]
  if (clamped) {
    chain.push({ op: 'clamp', detail: `clamped to ${countryLabel}'s own published ${clamped === 'low' ? 'P' + lo.pct : 'P' + hi.pct} `
      + `(${value.toLocaleString()}) — the shifted figure landed outside what this country's own table measures, `
      + 'so this pipeline does not report a number past the edge of real data' })
  }

  return { ok: true, value, currency, chain, clamped }
}

/** Tier 3. The occupation's own published central figure (native currency),
 *  shifted by the universal experience gradient. Always a model — this
 *  function's own result must only ever be rendered through <Derived>,
 *  never <Figure>. Refuses first on crosswalk comparability (finding F1) —
 *  before ever looking at the distribution shape. */
export function computeEstimate(profile: Profile, row: WageCountry, gradient: ExperienceGradient): EstimateResult {
  const refused = _notComparable(row)
  if (refused) return { ok: false, reason: refused }
  return _shiftEstimate(row.country, row.native.value, row.native.currency, profile.yearsProfessional, gradient)
}

/** Tier 4 support: the same shift, in annual USD, reading a USD combo
 *  build_wage_distribution.py already resolved (year-matched FX,
 *  normalise.py's own conversion) — never a client-side currency
 *  conversion of the native estimate. Prefers regular_pay (matching the
 *  wage panel's own default basis) but falls back to total_earnings when
 *  a country's own composition can't express regular_pay at all — Spain
 *  (bonus included by construction, no subtractable component) is exactly
 *  this case, and Spain contains Valencia, this site's own established
 *  instability canary (compute.ts's own docstring); without the fallback,
 *  Tier 4's own worked example would never be reachable through a real
 *  profile. The fallback is disclosed as its own chain step, never silent —
 *  a total_earnings-based estimate is a real, different number (bonus
 *  included) from what regular_pay would have shown. Returns null only
 *  when NEITHER basis is available (comparison_basis() refused both, or
 *  the country has no distribution at all). */
export function computeEstimateUsdYear(profile: Profile, row: WageCountry, gradient: ExperienceGradient): EstimateResult | null {
  if (_notComparable(row)) return null
  const regular = row.combos['usd_regular_pay']
  if (regular && regular.ok) {
    const result = _shiftEstimate(row.country, regular.value, regular.currency, profile.yearsProfessional, gradient)
    return result.ok ? result : null
  }
  const total = row.combos['usd_total_earnings']
  if (total && total.ok) {
    const result = _shiftEstimate(row.country, total.value, total.currency, profile.yearsProfessional, gradient)
    if (!result.ok) return null
    return { ...result, chain: [
      { op: 'basis_fallback', detail: `${row.country}'s own composition cannot express regular_pay (see its `
        + 'pay_composition.json entry) — this figure is total_earnings instead, which INCLUDES the irregular '
        + 'bonus regular_pay would have excluded. A real, different number, not a silent substitute.' },
      ...result.chain,
    ] }
  }
  return null
}

/* ------------------------------------------------------------- position --- */

export type PositionResult =
  | { ok: true; pct: 50; n: number | null; sourceLabel: string; year: number }
  | { ok: false; reason: string }

/** Tier 2. Always the published median (P50) — real, sourced, genuinely
 *  unmodelled, for every country the crosswalk accepts. `profile` is
 *  accepted for a uniform call signature with computeEstimate() but is
 *  not otherwise consulted.
 *
 *  An earlier version personalised Spain's own position by ranking an INE
 *  tenure-band figure against Spain's IT-specific percentile table. Removed
 *  (adversarial review findings F2/F2b/F3 — see this module's own header
 *  comment for the full reasoning): INE's tenure cross measures a broader
 *  occupational population than the one being ranked against, which could
 *  produce a position that disagreed with the estimate computed from the
 *  same inputs, and rendered a genuinely modelled number through <Figure>'s
 *  "official" confidence rather than <Derived>'s disclosed one. There is no
 *  IT-specific tenure cross to rank against instead — Spain's own estimate
 *  (computeEstimate, always a <Derived>) still uses the gradient; only the
 *  position stopped pretending the gradient could sourced it. */
export function computePosition(_profile: Profile, row: WageCountry, _gradient: ExperienceGradient): PositionResult {
  const refused = _notComparable(row)
  if (refused) return { ok: false, reason: refused }
  const points = knownPercentilePoints(row.native.value)
  if (points.length < 2) {
    return { ok: false, reason: `${row.country} publishes only a ${row.native.distribution.replace(/-/g, ' ')} — `
      + 'no spread to place a position within' }
  }
  return { ok: true, pct: 50, n: row.native.n_employees, sourceLabel: `${row.source_id} published median`,
    year: row.native.year }
}

/* --------------------------------------------------------- url mirror --- */

export const DEFAULT_OCCUPATION = 'isco08:2512'
export const DEFAULT_YEARS = 5

/** Reads the profile from the URL's own query params (?occupation, ?years,
 *  ?country) — the SAME idiom Compare.tsx's own `update()` uses for its
 *  scalar params (band/lens/view), not the list-reconciliation dance its
 *  `places` param needs, because a profile has no growing/shrinking list to
 *  reconcile: three scalars, read fresh on every render, written with
 *  `{ replace: true }` so editing the form doesn't cost a back-button press
 *  per keystroke. A shared link is therefore just a URL, the same
 *  guarantee every other shareable state on this site already has. */
export function profileFromParams(params: URLSearchParams): Profile {
  // Number(null) is 0, not NaN, and Number('') is ALSO 0, not NaN — reading
  // the raw string first and checking for both absence and emptiness (not
  // just non-finiteness) is what stops a missing or blank ?years param from
  // silently becoming "0 years experience" instead of DEFAULT_YEARS. The
  // `== null` check alone (an earlier version of this function) caught a
  // missing param but not `?years=` (present, empty) — caught by the
  // adversarial review (finding F21) constructing exactly that URL.
  const raw = params.get('years')
  const years = raw == null || raw === '' ? DEFAULT_YEARS : Number(raw)
  return {
    occupation: params.get('occupation') || DEFAULT_OCCUPATION,
    yearsProfessional: Number.isFinite(years) && years >= 0 ? years : DEFAULT_YEARS,
    country: params.get('country') || undefined,
  }
}

export function profileToParams(profile: Profile): Record<string, string | null> {
  return {
    occupation: profile.occupation === DEFAULT_OCCUPATION ? null : profile.occupation,
    years: profile.yearsProfessional === DEFAULT_YEARS ? null : String(profile.yearsProfessional),
    country: profile.country || null,
  }
}
