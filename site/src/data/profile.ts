/* Package 10 built the profile, the position, and the estimate. Package 11
 * fixed the position: package 10's own remediation of finding F2/F3
 * (Spain's position ranked a broader-population tenure cross against its
 * own IT-specific table) over-corrected by removing personalisation
 * EVERYWHERE, not just where it was unsound. The position went from
 * "wrong for one country" to "ignores its only input for all fifteen" — the
 * years control moved the estimate while the position sat frozen at P50,
 * always, for everyone.
 *
 * "The site does not estimate a person. It locates them." Two numbers, two
 * different kinds of claim, enforced by which component renders them:
 *
 *   POSITION  a rank within a country's own published distribution
 *             (P10/P25/median/P75/P90 from wage_distribution.json, already
 *             resolved by scripts/build_wage_distribution.py — this module
 *             re-derives NOTHING from raw salary_*.json). Personalised by
 *             years of experience ONLY where a country's own experience
 *             cross shares the SAME population as its own distribution —
 *             same statistical office, same classification, same
 *             occupation depth. Verified before this module was rewritten,
 *             not assumed (see build_experience_gradient.py's own module
 *             docstring for the full account): Sweden (SCB, SSYK 2512) and
 *             Norway (SSB, STYRK-08 2512) both qualify. Spain does not —
 *             INE's own tenure cross is for CNO-11's BROADER "Scientific
 *             and intellectual technicians and professionals" category,
 *             the exact mismatch finding F2/F3 (package 10) found and
 *             fixed, just for the position specifically, not for every
 *             country's estimate. Every other country has no cross at all.
 *             Where personalised, this is real arithmetic over one
 *             country's own real numbers — not a citation, so it renders
 *             through <Figure>'s own extended `steps` disclosure, not
 *             <Derived>'s naive register (see this module's header comment
 *             continuation below on why <Figure>, not <Derived>). Where NOT
 *             personalised, it is the plain published median, same as
 *             package 10 shipped for every country.
 *
 *   ESTIMATE  a country's own median, shifted by THAT COUNTRY'S OWN
 *             experience cross — never a different country's curve.
 *             Package 10 shipped one universal curve (Spain's tenure cross)
 *             applied to all thirteen comparable countries; retired
 *             entirely (see build_experience_gradient.py). A country with
 *             no cross of its own gets the published median as its
 *             "estimate" too — unadjusted, chain-disclosed as such, NEVER
 *             borrowed from elsewhere. A model, so always a <Derived>,
 *             never a <Figure> — even the unadjusted-median case, because
 *             the reason it is unadjusted is itself something to disclose,
 *             not imply.
 *
 * WHY THE PERSONALISED POSITION IS STILL <Figure>, NOT <Derived>: the
 * work order's own plan (phase-4-salary-and-cv-plan.md §3.4) puts the
 * position in the "actual" register and the estimate in "naive" — "same
 * grammar, same never-blend contract". A personalised SE/NO position is
 * built entirely from ONE country's own real, published numbers (an age
 * band's own salary figure, that same country's own percentile table) —
 * no cross-country borrowing, no synthesised figure, the same "two real
 * numbers from one office, one arithmetic rank-finding step" package 10's
 * FIRST design (before F2/F3) argued for Spain, which held for the
 * ARCHITECTURE even though Spain's own POPULATION premise was wrong.
 * Rendering it through <Figure> keeps that argument intact for the two
 * countries where the premise actually holds. <Figure>'s own `steps` field
 * (added this package) is what lets it show the arithmetic gate 1 asks
 * for without borrowing <Derived>'s "this is a model" register for a
 * number that is not a model — every input is a real, sourced figure.
 *
 * YEARS OF EXPERIENCE IS NOT AGE: SE's and NO's own crosses bucket by age,
 * the profile form collects years of professional experience — genuinely
 * different axes. _computeShift() converts one to the other via
 * ASSUMED_CAREER_START_AGE, a real, disclosed, single-constant assumption
 * (see its own doc comment below for the bug this fixed and NEEDS-DECISION
 * #24 for the full account) — not a silent step folded into the shift
 * arithmetic.
 *
 * Both functions also refuse (return not-ok) when scripts/crosswalk.py's
 * own comparability verdict (row.crosswalk.comparable) is false — a
 * country the crosswalk itself refused (the Netherlands: "no ISCO-08
 * correspondence at all for this occupation") must never render a position
 * or an estimate, regardless of whether it happens to publish a real
 * percentile spread. Finding F1, package 10's adversarial review.
 *
 * COHERENCE (this package's own tier 1.4): position and estimate must
 * agree about WHETHER a country personalises, always — never one moving
 * while the other sits frozen. Enforced structurally, not by convention:
 * both computePosition() and computeEstimate() ask the exact same
 * question (_countryGradient(row, gradient)) of the exact same data, so
 * there is no code path where they could disagree about eligibility. Where
 * personalised, both derive from the SAME shifted value (_computeShift) —
 * the position ranks it, the estimate states it — removing finding F3's
 * OTHER problem (a discrete-band position and a continuously-interpolated
 * estimate could each move independently, disagreeing about the same
 * profile even when the population matched).
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
   *  from the shared Selection instead. */
  country?: string
}

/* ------------------------------------------------------------ gradient --- */

export interface GradientPoint {
  /** An AGE, not years of professional experience — an approximation of
   *  the band's own centre, not a measurement. See this module's own
   *  header comment, each curve's own meta.proxy_caveat, and
   *  ASSUMED_CAREER_START_AGE below for how a years-of-experience value
   *  gets onto this same axis. */
  age_midpoint_approx: number
  band_label: string
  premium_pct: number
}
export interface CountryGradientMeta {
  source: string
  proxy_caveat: string
  /** Which of a country's own central-tendency figures this curve's own
   *  premiums are relative to — SCB's SE cross publishes band MEANS only
   *  ("tot", confirmed equal to dispersion_by_year's own mean_sek_month);
   *  SSB's NO cross is median-relative throughout. Shifting the WRONG
   *  measure by the OTHER's relative premium is finding F1 (adversarial
   *  review): SE's own premiums, applied to the median instead of the
   *  mean, ranked every personalised position about 6 points too low
   *  against what SCB's own band figures rank to directly. See
   *  _centralFor() below, the single place this is consulted. */
  premium_basis: 'mean' | 'median'
  /** WHICH PAY BASIS the premium was measured on — a different axis from
   *  premium_basis above, which is the central STATISTIC. Both must match
   *  the figure being shifted, and until package 25 neither this field nor
   *  any equivalent existed, which is exactly why NEEDS-DECISION #58
   *  (finding F13) could sit open: Norway's USD estimate shifted
   *  AvtaltManedslonn (basic salary) by a premium SSB measured on
   *  Manedslonn (total earnings), and nothing in the data said so.
   *
   *  Read from each office's own returned table metadata, cited in
   *  pay_basis_source, and required by build_experience_gradient.py — a
   *  curve added without one fails the build rather than being applied. */
  pay_basis: 'regular_pay' | 'total_earnings'
  pay_basis_source: string
  year?: number
  quarter?: string
  vintage_note?: string
}
export interface CountryGradient {
  curve: GradientPoint[]
  meta: CountryGradientMeta
}
export interface ExperienceGradient {
  /** Keyed by ISO2 (e.g. "SE", "NO") — a country with no entry here has no
   *  experience/age/tenure cross this pipeline trusts to personalise from.
   *  Package 10 shipped one universal curve under a different shape
   *  entirely (gradient.curve, applied to every country); retired. */
  by_country: Record<string, CountryGradient>
  interpolation: string
}

export async function loadExperienceGradient(): Promise<ExperienceGradient> {
  const h = await loadHistory<ExperienceGradient>('experience_gradient')
  return h.data
}

/** scripts/build_experience_gradient.py's own by_country map, keyed by this
 *  row's ISO2 prefix — the ONE question both computePosition() and
 *  computeEstimate() ask to decide personalisation, so they can never
 *  disagree about whether a country qualifies (this module's own header
 *  comment, "coherence"). Returns null for every country except SE/NO. */
function _countryGradient(row: WageCountry, gradient: ExperienceGradient): CountryGradient | null {
  const iso = row.country.split('-')[0]!
  return gradient.by_country[iso] ?? null
}

/** A `wages.absent[].reason` as a reader should see it.
 *
 *  The committed string carries two developer breadcrumbs: a machine-ish
 *  `no-series — ` prefix and a trailing `, per src_salary_it.py`. Both are
 *  real provenance and stay in the data; neither belongs in a sentence read
 *  aloud to someone asking why Italy has no table. Package 24 stripped them
 *  inside /work's own row and nowhere else, so the raw form kept rendering
 *  in the coverage map and its absence footnote — found by reading the
 *  page's own text back, not by reading the components (package 25,
 *  assertion class 3). One helper, so the next render site cannot forget.
 */
export function readableAbsentReason(reason: string | undefined): string | undefined {
  return reason
    ?.replace(/^no-series\s*[—-]\s*/i, '')
    .replace(/,?\s*per\s+\S+\.py\s*$/i, '')
    .trim()
}

/** Countries with a real occupation-level experience/age/tenure cross that
 *  does NOT share the same population as their own wage distribution —
 *  named specifically, not lumped in with the majority that has no cross
 *  at all. Only Spain currently: NEEDS-DECISION.md #20's own account. */
const _MISMATCHED_POPULATION_REASON: Record<string, string> = {
  ES: "Spain's own INE tenure cross exists (broader_category_context in salary_es.json) but measures "
    + 'a BROADER occupational population (CNO-11 "Scientific and intellectual technicians and '
    + 'professionals") than this occupation\'s own distribution — not the same population, so not used '
    + 'to personalise position or estimate. See NEEDS-DECISION.md #20.',
}

/** The reason shown when a country does not personalise — distinguishes
 *  "a cross exists but is the wrong population" (Spain) from "no cross
 *  exists at all" (everyone else), rather than one generic sentence for
 *  both real, different causes. */
function _noExperienceCrossReason(row: WageCountry): string {
  return _MISMATCHED_POPULATION_REASON[row.country.split('-')[0]!]
    ?? `${row.country} has no occupation x experience/age cross of its own in this pipeline — the `
      + 'published median is shown, not personalised to your years of experience.'
}

/** Tier 5 (coverage map) support: the experience axis specifically — does
 *  `row` personalise, and if not, why. Reuses _countryGradient so the
 *  coverage map can never drift from what computePosition()/
 *  computeEstimate() actually do (the SAME discipline that keeps position
 *  and estimate coherent applies to describing them, not just computing
 *  them — gate 7, package 11, echoing finding F6 from package 10's own
 *  coverage map, where the tier label and its own stated reason could
 *  contradict each other because they were computed two different ways). */
export function experienceCoverageFor(row: WageCountry, gradient: ExperienceGradient): { personalised: boolean; detail: string } {
  const cg = _countryGradient(row, gradient)
  if (cg) return { personalised: true, detail: `personalised via ${cg.meta.source}` }
  return { personalised: false, detail: _noExperienceCrossReason(row) }
}

/** Piecewise-linear interpolation between a country's own real points,
 *  clamped at both ends — never extrapolated past what that country's own
 *  cross actually measured. Mirrors the SAME clamp discipline
 *  rankWithinDistribution() below applies to percentiles. Takes an AGE
 *  (see ASSUMED_CAREER_START_AGE below for how one gets here from years of
 *  professional experience), not years directly. */
export function gradientPremiumPct(age: number, curve: GradientPoint[]): { pct: number; clamped: 'low' | 'high' | null } {
  const pts = [...curve].sort((a, b) => a.age_midpoint_approx - b.age_midpoint_approx)
  if (age <= pts[0]!.age_midpoint_approx) {
    return { pct: pts[0]!.premium_pct, clamped: age < pts[0]!.age_midpoint_approx ? 'low' : null }
  }
  const last = pts[pts.length - 1]!
  if (age >= last.age_midpoint_approx) {
    return { pct: last.premium_pct, clamped: age > last.age_midpoint_approx ? 'high' : null }
  }
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i]!, b = pts[i + 1]!
    if (age >= a.age_midpoint_approx && age <= b.age_midpoint_approx) {
      const t = (age - a.age_midpoint_approx) / (b.age_midpoint_approx - a.age_midpoint_approx)
      return { pct: a.premium_pct + t * (b.premium_pct - a.premium_pct), clamped: null }
    }
  }
  return { pct: pts[0]!.premium_pct, clamped: null } // unreachable given the bounds checks above
}

export interface EstimateStep { op: string; detail: string }

/** A real, disclosed assumption, not a measurement: SE's and NO's own
 *  crosses are bucketed by AGE, but the profile form collects years of
 *  professional experience — a genuinely different axis (someone with 2
 *  years of experience is not 2 years old). Converting one to the other
 *  needs SOME assumption; this pipeline uses the standard labour-economics
 *  convention for "potential experience" (age minus years of schooling
 *  minus six), fixed at a bachelor's degree finishing at 22 — the same
 *  single constant for every profile, not tuned per country or per
 *  education level this pipeline does not collect. Caught before shipping:
 *  an earlier version of this file treated years_midpoint_approx (an AGE
 *  band's own centre, e.g. 21, 29.5, 39.5...) as if it were directly on
 *  the SAME numeric axis as yearsProfessional (e.g. 2, 8, 20) — every
 *  realistic years-of-experience value is below the youngest age band's
 *  own midpoint, so every profile clamped to the identical lowest-band
 *  premium regardless of years, which is exactly what gate 1 says must not
 *  happen ("three different percentiles"). Found by running the gate 1
 *  check live, not by inspection. */
export const ASSUMED_CAREER_START_AGE = 22

/** The one figure a country's own gradient premium is relative to — reads
 *  `cg.meta.premium_basis` rather than defaulting to "median if present",
 *  because that default is exactly what produced finding F1: SE's own
 *  premiums are mean-relative, so shifting the median by them compares two
 *  differently-based numbers. Falls back to the other measure only when
 *  the matching one is genuinely absent from this table. The single call
 *  site both computePosition() and _shiftEstimate() go through — same
 *  coherence discipline as _countryGradient() itself. */
function _centralFor(stats: WageStats, cg: CountryGradient): number | null {
  if (cg.meta.premium_basis === 'mean') return stats.mean ?? stats.median ?? null
  return stats.median ?? stats.mean ?? null
}

/** The shared arithmetic: convert `years` to an assumed age, shift
 *  `central` by `cg`'s own premium at that age. Used identically by the
 *  estimate (which states the shifted value) and the position (which
 *  ranks it) — the SAME shift, not two independently computed numbers
 *  that happen to both depend on years. Rounds the premium to the same
 *  precision it displays, THEN uses that rounded value for the arithmetic
 *  — not the other way around (finding F15, package 10's adversarial
 *  review: an earlier version computed the raw value from full-precision
 *  premium but displayed a rounded multiplier, so hand-multiplying the two
 *  shown numbers never reproduced the shown result). */
function _computeShift(central: number, years: number, cg: CountryGradient): { raw: number; chain: EstimateStep[] } {
  const assumedAge = years + ASSUMED_CAREER_START_AGE
  const gRaw = gradientPremiumPct(assumedAge, cg.curve)
  const pct = Math.round(gRaw.pct * 10) / 10
  const multiplier = 1 + pct / 100
  const raw = central * multiplier

  const pts = [...cg.curve].sort((a, b) => a.age_midpoint_approx - b.age_midpoint_approx)
  const edge = gRaw.clamped === 'low' ? pts[0] : pts[pts.length - 1]
  const chain: EstimateStep[] = [
    { op: 'age_proxy', detail: `${years} years of experience -> assumed age ~${assumedAge} `
      + `(career start at ${ASSUMED_CAREER_START_AGE}, a stated assumption — see ASSUMED_CAREER_START_AGE)` },
    { op: 'gradient', detail: `age ~${assumedAge} -> ${pct >= 0 ? '+' : ''}${pct.toFixed(1)}% (${cg.meta.source}`
      + (cg.meta.year ? `, ${cg.meta.year}` : cg.meta.quarter ? `, ${cg.meta.quarter}` : '') + ')'
      + (gRaw.clamped
        ? ` — held at the ${gRaw.clamped === 'low' ? 'lowest' : 'highest'} band this curve models `
          + `("${edge?.band_label}", ~${edge?.age_midpoint_approx} years old): not extrapolated further`
        : '') },
    { op: 'proxy', detail: cg.meta.proxy_caveat },
  ]
  if (cg.meta.premium_basis === 'mean') {
    chain.push({ op: 'basis', detail: `${cg.meta.source.split(',')[0]} publishes each band's own MEAN, not `
      + `median — the figure being shifted here is this country's own mean (${central.toLocaleString()}), `
      + 'not the median, so the premium and the figure it applies to are on the same basis' })
  }
  chain.push({ op: 'shift', detail: `${central.toLocaleString()} x ${multiplier.toFixed(3)} = ${raw.toLocaleString(undefined, { maximumFractionDigits: 2 })}` })
  if (cg.meta.vintage_note) chain.push({ op: 'vintage', detail: cg.meta.vintage_note })
  return { raw, chain }
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

export type EstimateResult =
  | { ok: true; value: number; currency: string; chain: EstimateStep[]; clamped: 'low' | 'high' | null; personalised: boolean }
  | { ok: false; reason: string }

/** The shared core: shift `stats`'s own central figure by `row`'s OWN
 *  experience cross (never another country's), clamped to `stats`'s own
 *  published bounds. Falls back to the unadjusted published median —
 *  disclosed as such, its own chain step naming why — when `row` has no
 *  cross of its own. Used for both the native-currency estimate (Tier 3's
 *  own displayed number) and the USD-annual estimate (Tier 4's
 *  stabilityOf() override) — same math, different currency's own
 *  percentile table, never a client-side FX conversion of one into the
 *  other (that would re-derive normalise.py's own job). */
function _shiftEstimate(
  row: WageCountry, stats: WageStats, currency: string,
  profile: Profile, gradient: ExperienceGradient,
): EstimateResult {
  const points = knownPercentilePoints(stats)
  if (points.length < 2) {
    return { ok: false, reason: `${row.country} publishes only a distribution too narrow to shift within or `
      + 'clamp against (need at least two of p10/p25/median/p75/p90)' }
  }

  const cg = _countryGradient(row, gradient)
  if (!cg) {
    const central = stats.median ?? stats.mean
    if (central == null) return { ok: false, reason: `${row.country} has no median or mean to shift` }
    return { ok: true, value: central, currency, personalised: false,
      chain: [{ op: 'no_experience_cross', detail: _noExperienceCrossReason(row) }], clamped: null }
  }
  const central = _centralFor(stats, cg)
  if (central == null) return { ok: false, reason: `${row.country} has no ${cg.meta.premium_basis} to shift` }

  const { raw, chain: shiftChain } = _computeShift(central, profile.yearsProfessional, cg)
  const lo = points[0]!, hi = points[points.length - 1]!
  let value = raw
  let clamped: 'low' | 'high' | null = null
  if (raw < lo.value) { value = lo.value; clamped = 'low' }
  else if (raw > hi.value) { value = hi.value; clamped = 'high' }

  const chain = [...shiftChain]
  if (clamped) {
    chain.push({ op: 'clamp', detail: `clamped to ${row.country}'s own published ${clamped === 'low' ? 'P' + lo.pct : 'P' + hi.pct} `
      + `(${value.toLocaleString()}) — the shifted figure landed outside what this country's own table measures, `
      + 'so this pipeline does not report a number past the edge of real data' })
  }

  return { ok: true, value, currency, chain, clamped, personalised: true }
}

/** Tier 3. The occupation's own published central figure (native currency),
 *  shifted by THIS country's own experience cross when one exists — always
 *  a model, so this function's own result must only ever be rendered
 *  through <Derived>, never <Figure>, even in the unpersonalised (median)
 *  case. Refuses first on crosswalk comparability (finding F1) — before
 *  ever looking at the distribution shape. */
export function computeEstimate(profile: Profile, row: WageCountry, gradient: ExperienceGradient): EstimateResult {
  const refused = _notComparable(row)
  if (refused) return { ok: false, reason: refused }
  return _shiftEstimate(row, row.native.value, row.native.currency, profile, gradient)
}

/** Tier 4 support: the same shift, in annual USD, reading a USD combo
 *  build_wage_distribution.py already resolved (year-matched FX,
 *  normalise.py's own conversion) — never a client-side currency
 *  conversion of the native estimate. Prefers the basis the country's own
 *  experience cross was MEASURED on where one exists (NEEDS-DECISION #58,
 *  package 25) and regular_pay otherwise — matching the wage panel's own
 *  default — falling back to the other basis when the preferred one is not
 *  available for that country at all. Spain
 *  (bonus included by construction, no subtractable component) is exactly
 *  this case, and Spain contains Valencia, this site's own established
 *  instability canary (compute.ts's own docstring); without the fallback,
 *  Tier 4's own worked example would never be reachable through a real
 *  profile. The fallback is disclosed as its own chain step, never silent.
 *  Returns null only when NEITHER basis is available (comparison_basis()
 *  refused both, or the country has no distribution at all). */
export function computeEstimateUsdYear(profile: Profile, row: WageCountry, gradient: ExperienceGradient): EstimateResult | null {
  if (_notComparable(row)) return null

  /* NEEDS-DECISION #58 / finding F13, resolved in package 25. When a
   * country personalises, the premium is measured on ONE pay basis and the
   * figure it multiplies must be on the SAME one — otherwise the result is
   * a number no office measured. Norway was exactly this: SSB's 11658 cross
   * is Manedslonn (total earnings, bonus in — its own ContentsCodes say
   * "monthly earnings", never "basic"), while this function preferred
   * usd_regular_pay, which for Norway is AvtaltManedslonn, "Basic monthly
   * salary". A ~3.5% different figure shifted by a premium built on the
   * other one, with the age profile of bonus — the part that actually
   * varies with the premium — unmeasured either way.
   *
   * The basis-matched combo is therefore preferred over the site's usual
   * regular_pay default whenever a gradient exists. Sweden is unaffected:
   * SCB publishes one concept (manadslon, bonus excluded) and its cross and
   * its dispersion are both on it, so the matched combo IS usd_regular_pay.
   * Countries with no gradient keep the old preference exactly — there is
   * no premium to agree with, so nothing to match. */
  const cg = _countryGradient(row, gradient)
  const preferred: string[] = cg
    ? (cg.meta.pay_basis === 'total_earnings'
        ? ['usd_total_earnings', 'usd_regular_pay']
        : ['usd_regular_pay', 'usd_total_earnings'])
    : ['usd_regular_pay', 'usd_total_earnings']

  const matchedKey = preferred[0]!
  const matched = row.combos[matchedKey]
  if (matched && matched.ok) {
    const result = _shiftEstimate(row, matched.value, matched.currency, profile, gradient)
    if (!result.ok) return null
    // Only worth saying when the choice was driven by the premium rather
    // than by the site's default — i.e. Norway.
    if (cg && matchedKey === 'usd_total_earnings') {
      return { ...result, chain: [
        { op: 'basis_match', detail: `${row.country}'s own experience cross is measured on total_earnings `
          + `(${cg.meta.pay_basis_source}) — so the figure shifted here is total_earnings too, rather than `
          + 'the regular_pay this site otherwise prefers. Applying a total-earnings premium to a basic-salary figure '
          + 'would multiply a number by a rate measured on a different one.' },
        ...result.chain,
      ] }
    }
    return result
  }

  // The SECOND entry of the preference list, not a hardcoded key. This read
  // row.combos['usd_total_earnings'] regardless, so a total_earnings-basis
  // gradient whose own combo was unavailable retried the same key and
  // returned null instead of falling back — a dead branch contradicting the
  // ordered list six lines above it (package 25, adversarial review).
  const total = row.combos[preferred[1]!]
  if (total && total.ok) {
    const result = _shiftEstimate(row, total.value, total.currency, profile, gradient)
    if (!result.ok) return null
    return { ...result, chain: [
      { op: 'basis_fallback', detail: `${row.country}'s own composition cannot express ${preferred[0]!.replace('usd_', '')} `
        + `(see its pay_composition.json entry) — this figure is ${preferred[1]!.replace('usd_', '')} instead, a real, `
        + 'different number, not a silent substitute.' },
      ...result.chain,
    ] }
  }
  return null
}

/* ------------------------------------------------------------- position --- */

export type PositionResult =
  | { ok: true; pct: number; n: number | null; sourceLabel: string; year: number; personalised: false; reason: string }
  | { ok: true; pct: number; n: number | null; sourceLabel: string; year: number; personalised: true
      chain: EstimateStep[]; clamped: 'low' | 'high' | null }
  | { ok: false; reason: string }

/** Tier 2. The published median (P50) for every country with no
 *  same-population experience cross of its own — real, sourced, genuinely
 *  unmodelled. For Sweden and Norway specifically (see this module's own
 *  header comment for why exactly these two), the SAME shift the estimate
 *  computes (_computeShift) is ranked against this country's own
 *  percentile table instead of stated directly — real arithmetic over one
 *  country's own real numbers, disclosed via <Figure>'s own `steps` field
 *  in Position.tsx, not hidden behind a bare "P50". */
export function computePosition(profile: Profile, row: WageCountry, gradient: ExperienceGradient): PositionResult {
  const refused = _notComparable(row)
  if (refused) return { ok: false, reason: refused }
  const points = knownPercentilePoints(row.native.value)
  if (points.length < 2) {
    return { ok: false, reason: `${row.country} publishes only a ${row.native.distribution.replace(/-/g, ' ')} — `
      + 'no spread to place a position within' }
  }

  const cg = _countryGradient(row, gradient)
  if (!cg) {
    return { ok: true, pct: 50, n: row.native.n_employees, sourceLabel: `${row.source_name ?? row.source_id} published median`,
      year: row.native.year, personalised: false, reason: _noExperienceCrossReason(row) }
  }
  // A gradient exists but has neither of the figures it needs to shift —
  // an honest failure, not a silent re-interpretation as "not personalised"
  // (that would misattribute the reason: the cross DOES exist here, unlike
  // the branch above). Kept symmetric with _shiftEstimate's own identical
  // check so position and estimate cannot disagree about eligibility even
  // in this edge case (finding F8, adversarial review) — unreached by any
  // of today's 15 countries (SE/NO both publish both measures), a
  // correctness fix for data this pipeline doesn't have yet, not one it does.
  const central = _centralFor(row.native.value, cg)
  if (central == null) {
    return { ok: false, reason: `${row.country} has a ${cg.meta.source} cross but no ${cg.meta.premium_basis} `
      + 'of its own to shift' }
  }

  const { raw, chain: shiftChain } = _computeShift(central, profile.yearsProfessional, cg)
  const rank = rankWithinDistribution(raw, points)! // points.length >= 2, checked above
  const chain = [...shiftChain]
  if (rank.clamped) {
    const edge = points.find((p) => p.pct === rank.pct)!
    chain.push({ op: 'clamp', detail: `clamped to ${row.country}'s own published P${edge.pct} `
      + `(${edge.value.toLocaleString()}) — the shifted figure landed outside what this country's own table `
      + 'measures, so this pipeline does not report a rank past the edge of real data' })
  } else {
    // Finding F4, adversarial review: the chain used to stop at the shifted
    // figure and jump straight to a displayed percentile with no step
    // showing HOW — the interpolation gate 1's own "how this number was
    // calculated" popover claims to show, but never actually did.
    const sorted = [...points].sort((a, b) => a.value - b.value)
    const lo = [...sorted].reverse().find((p) => p.value <= raw)!
    const hi = sorted.find((p) => p.value >= raw)!
    chain.push({ op: 'rank', detail: lo.pct === hi.pct
      ? `${raw.toLocaleString(undefined, { maximumFractionDigits: 2 })} lands exactly on ${row.country}'s own `
        + `published P${lo.pct}`
      : `${raw.toLocaleString(undefined, { maximumFractionDigits: 2 })} falls between ${row.country}'s own `
        + `published P${lo.pct} (${lo.value.toLocaleString()}) and P${hi.pct} (${hi.value.toLocaleString()}) `
        + `-> interpolated to P${rank.pct.toFixed(1)}` })
  }

  return { ok: true, pct: rank.pct, n: row.native.n_employees,
    sourceLabel: `${row.source_name ?? row.source_id} published table, ranked against ${cg.meta.source}`,
    year: row.native.year, personalised: true, chain, clamped: rank.clamped }
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
  // silently becoming "0 years experience" instead of DEFAULT_YEARS.
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
