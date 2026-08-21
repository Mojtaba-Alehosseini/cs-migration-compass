/* Explore's data layer.
 *
 * One place where a processed dataset becomes the series a chart draws, so the
 * shaping rules are stated once and can be checked against the files.
 *
 * The annualisation rules below are not interchangeable, and each was chosen by
 * the source rather than by taste:
 *
 *   BIS, FHFA   quarterly index → the LAST quarter of each year. An index level
 *               is a point in time; averaging four of them invents a quarter
 *               that never happened.
 *   Teranet, UK monthly price   → the MEAN of the year's months. These are
 *               transaction prices, so the year's average is the real quantity.
 *   UN WPP      every second year — 111 annual points per country is more
 *               resolution than a 110-year line can show, and the file is large.
 *
 * Nothing here repairs, fills or smooths. A gap stays a gap.
 */

import { loadHistory } from './store'

export type Pair = [number, number]

const byYear = <T,>(rows: T[], year: (r: T) => number) => {
  const m = new Map<number, T[]>()
  for (const r of rows) {
    const y = year(r)
    const list = m.get(y)
    if (list) list.push(r)
    else m.set(y, [r])
  }
  return m
}

const lastPerYear = <T,>(rows: T[], year: (r: T) => number, value: (r: T) => number, dp = 1): Pair[] =>
  [...byYear(rows, year).entries()]
    .map(([y, rs]) => [y, round(value(rs[rs.length - 1]!), dp)] as Pair)
    .sort((a, b) => a[0] - b[0])

const meanPerYear = <T,>(rows: T[], year: (r: T) => number, value: (r: T) => number, dp = 1): Pair[] =>
  [...byYear(rows, year).entries()]
    .map(([y, rs]) => [y, round(rs.reduce((s, r) => s + value(r), 0) / rs.length, dp)] as Pair)
    .sort((a, b) => a[0] - b[0])

const round = (v: number, dp: number) => {
  const f = 10 ** dp
  return Math.round(v * f) / f
}

/* ---------------------------------------------------------------- money --- */

export interface MoneyData {
  /** GDP per person, nominal US$, by country. */
  gdp: Record<string, Pair[]>
  /** OECD projected REAL growth %, projection years only. */
  eo: Record<string, Pair[]>
  eoChip: string
  /** p25 / median / p75 / n / thin, by country and experience band. */
  so: Record<string, Record<'ng' | 'mid' | 'sr', [number, number, number, number, boolean] | null>>
}

type WBRow = { year: number; value: number }
type EORow = { year: number; value: number; is_projection: boolean }

export async function loadMoney(): Promise<MoneyData> {
  const [wb, eo, so] = await Promise.all([
    loadHistory<Record<string, Record<string, WBRow[]>>>('world_bank'),
    loadHistory<Record<string, Record<string, EORow[]>>>('oecd_economic_outlook'),
    loadHistory<{ by_country_experience: Record<string, Record<string, Record<string, {
      median_usd: number | null; p25_usd: number | null; p75_usd: number | null
      n: number; thin_sample: boolean
    }>>> }>('stackoverflow_survey'),
  ])

  const gdp: Record<string, Pair[]> = {}
  for (const [cc, block] of Object.entries(wb.data)) {
    const rows = block.gdp_per_capita_usd ?? []
    if (rows.length) gdp[cc] = rows.map((r) => [r.year, Math.round(r.value)] as Pair)
  }

  // Only the projected years. The OECD's own history is not redrawn here — the
  // World Bank line already holds the past, and two histories of the same thing
  // on one chart is exactly the blending the forecast grammar forbids.
  const eoOut: Record<string, Pair[]> = {}
  for (const [cc, block] of Object.entries(eo.data)) {
    const rows = (block.real_gdp_growth_pct ?? []).filter((r) => r.is_projection)
    if (rows.length) eoOut[cc] = rows.map((r) => [r.year, round(r.value, 2)] as Pair)
  }

  const soOut: MoneyData['so'] = {}
  const BANDS = { ng: 'new_grad', mid: 'mid', sr: 'senior' } as const
  for (const [cc, waves] of Object.entries(so.data.by_country_experience ?? {})) {
    const wave = waves['2024']
    if (!wave) continue
    const entry = {} as MoneyData['so'][string]
    for (const [short, long] of Object.entries(BANDS)) {
      const b = wave[long]
      entry[short as keyof typeof BANDS] = b && b.median_usd != null
        ? [b.p25_usd ?? b.median_usd, b.median_usd, b.p75_usd ?? b.median_usd, b.n, b.thin_sample]
        : null
    }
    soOut[cc] = entry
  }

  return {
    gdp,
    eo: eoOut,
    eoChip: String(eo.meta.attribution_chip ?? 'OECD Economic Outlook'),
    so: soOut,
  }
}

/* ---------------------------------------------------------------- wages --- */

/** Mirrors scripts/build_wage_distribution.py's output shape exactly — types
 *  only, no logic. crosswalk.compare() and every normalise.py conversion ran
 *  at build time, in Python; nothing here re-derives a rate, a subtraction or
 *  a comparability verdict. See that script's own module docstring and
 *  crosswalk.py:33-38 ("package 9 must call this function rather than
 *  re-deriving the rule in the UI"). */

// 'quartile-only' added tier 7 (adversarial review finding F14): Denmark/
// Norway/Netherlands publish p25/median/p75 but not p10/p90 — a real
// spread, genuinely different from 'central-tendency-only' (Australia/
// Ireland: a median with no spread published at all).
export type Distribution = 'full' | 'quartile-only' | 'central-tendency-only' | 'mean-only'

export interface WageStats {
  mean: number | null; median: number | null
  p10: number | null; p25: number | null; p75: number | null; p90: number | null
}

export interface ChainStep { op: string; detail: string }

export type CrosswalkVerdict =
  | { comparable: true; depth: number; shared_key: string; degraded_by: string | null }
  | { comparable: false; reason: string }

/** Package 14, Tier 1 — the SET-WIDE sibling of CrosswalkVerdict above.
 *  `crosswalk` (above) is pairwise against the single reference occupation
 *  and is still correct for a country page's own "how does my code relate
 *  to the reference" disclosure. `chart_comparable` is the separate answer
 *  to "does the multi-country COMPARISON chart show this row" — resolved
 *  once, set-wide, in scripts/crosswalk.py's resolve_set(); the two can
 *  disagree (Ireland is crosswalk.comparable at 1-digit, but
 *  chart_comparable: false once the panel's own quorum resolves to
 *  4-digit — see WagePanel.tsx). */
export type ChartComparability =
  | { comparable: true; depth: number; own_depth: number; degraded: boolean; degraded_by: string | null }
  | { comparable: false; reason: string }

export type Combo =
  | { ok: true; value: WageStats; chain: ChainStep[]; currency: string; chain_field: keyof WageStats }
  | { ok: false; reason: string }

export type CurrencyMode = 'native' | 'usd'
export type Basis = 'regular_pay' | 'total_earnings'
export const comboKey = (currency: CurrencyMode, basis: Basis) => `${currency}_${basis}` as const

export interface WageCountry {
  country: string          // ISO2, or "CA-21231"/"CA-21232" for Canada's two NOC codes — see NEEDS-DECISION #12
  source_id: string
  national_code: string
  native: {
    currency: string; period: 'hour' | 'month' | 'year'; year: number
    value: WageStats; n_employees: number | null; distribution: Distribution
    /** Set only for Qatar: this pipeline's own weighted average of PSA's
     *  separately-published Male/Female series — a real derivation, not a
     *  value the source itself published. null for every other country. */
    weighting_note: string | null
    /** Set only for Germany: this native figure is regular_pay annualised
     *  at extraction (x12 of Destatis's own real monthly table) — not the
     *  annual figure Destatis itself publishes. null for every other
     *  country. Same disclosure class as weighting_note above, under its
     *  own name (a unit conversion, not a weighting) — finding F6,
     *  package 11's adversarial review. */
    annualised_note: string | null
    /** Set only for Denmark (package 10, tier 0.2): proof this native figure
     *  (DST's STAND concept) reconciles with DST's own separately-published
     *  MDRSNIT monthly headline. null for every other country. */
    mdrsnit_check: {
      stand_dkk_hour: number; computed_monthly: number
      published_mdrsnit: number; residual_pct: number
    } | null
  }
  crosswalk: CrosswalkVerdict
  chart_comparable: ChartComparability
  combos: Record<string, Combo>  // keyed by comboKey()
}

export interface WageDistribution {
  reference: { country: string; national_code: string; note: string }
  /** Package 14, Tier 1 — the resolved set-wide depth every chart-comparable
   *  row below shares, and the full, named reason for every row that isn't
   *  one of them (a superset of the old zero-correspondence-only list). */
  resolved_comparison: {
    depth: number | null; shared_key: string | null; note: string
    excluded: { country: string; reason: string }[]
  }
  countries: WageCountry[]
  absent: { country: string; reason: string }[]
}

/** Package 12, tier 0 (closes NEEDS-DECISION #12): Canada is the only country
 *  with two rows for the same shared occupation key — NOC 2021 splits
 *  isco08:2512 along a professional-engineering-licensure axis ISCO-08 does
 *  not itself draw (data/occupations.json's own mapping.note is the same
 *  fact, written for a crosswalk-maintainer audience; this is the
 *  reader-facing version, shared so every row that renders "21231" or
 *  "21232" explains itself the same way instead of drifting). Verified
 *  against noc.esdc.gc.ca's own unit-group profiles, not just carried over
 *  from the crosswalk note: 21231's own profile states licensing "required
 *  to approve engineering drawings and reports and to practise as a
 *  Professional Engineer (P.Eng.)"; 21232's profile states no such
 *  requirement, only a computer-science-or-equivalent credential. */
export const CA_NOC_DISTINCTION: Record<string, string> = {
  'CA-21231': 'NOC 2021’s "engineer" track: covers roles where practising as a licensed '
    + 'Professional Engineer (P.Eng., provincial/territorial registration) applies to part of the '
    + 'work — architecture, systems design, drawings and reports a P.Eng. must sign off on. '
    + 'ISCO-08 does not draw this line at all; one code (2512) covers both.',
  'CA-21232': 'NOC 2021’s general "developer/programmer" track: a computer science or software '
    + 'engineering credential, no professional engineering licence required. The closer match for '
    + 'most "software developer" job titles outside Canada.',
}

export async function loadWages(): Promise<WageDistribution> {
  const wd = await loadHistory<WageDistribution>('wage_distribution')
  return wd.data
}

/** Package 14, Tier 2 (external audit Finding 2, HIGH) — the reference-year
 *  spread across whichever rows a wage-panel toggle actually shows a bar
 *  for. Pure and exported (not inline in WagePanel.tsx) specifically so
 *  the >3-year disclosure rule has a real unit test against a synthetic
 *  spread — Tier 1's own set-wide crosswalk fix (resolve_set()) already
 *  excludes every country whose vintage gap was the widest (Ireland 2022,
 *  Spain 2018) from the live chart's own comparable set, so the live site
 *  currently has nothing wide enough to trigger this on screen; the logic
 *  itself is still real and still runs every time the toggle changes. */
export function computeYearSpread(
  rows: { country: string; year: number }[],
): { spread: number; oldest: { country: string; year: number }; newest: { country: string; year: number } } | null {
  if (rows.length < 2) return null
  const oldest = rows.reduce((a, b) => (b.year < a.year ? b : a))
  const newest = rows.reduce((a, b) => (b.year > a.year ? b : a))
  return { spread: newest.year - oldest.year, oldest, newest }
}

/* ----------------------------------------------------------------- jobs --- */

export interface JobsData {
  /** ICT specialists as a share of employment. `EU27` is the benchmark. */
  ict: Record<string, Pair[]>
  /** Postings index, x = decimal year. */
  indeed: Record<string, Pair[]>
  /** How many metros the file holds, so the page can say what it is not drawing. */
  metrosAvailable: number
}

/** The eight the design draws, and the order it draws them in — which is also
 *  the order of the `--m-1…8` palette. */
export const METROS = [
  'austin', 'sf_bay_area', 'new_york', 'seattle', 'denver', 'atlanta', 'boston', 'chicago',
] as const

export const METRO_LABEL: Record<string, string> = {
  austin: 'Austin', sf_bay_area: 'SF Bay', new_york: 'New York', seattle: 'Seattle',
  denver: 'Denver', atlanta: 'Atlanta', boston: 'Boston', chicago: 'Chicago',
}

/** "2020-02" → 2020.083, so months plot on a continuous year axis. */
export const monthToX = (s: string) => {
  const [y, m] = s.split('-')
  return Number(y) + (Number(m) - 1) / 12
}

export async function loadJobs(): Promise<JobsData> {
  const [ict, ind] = await Promise.all([
    loadHistory<{
      countries: Record<string, Record<string, { year: number; value: number }[]>>
      eu27_benchmark: Record<string, { year: number; value: number }[]>
    }>('eurostat_ict_specialists'),
    loadHistory<Record<string, { series: { month: string; index: number }[] }>>('indeed_hiring_lab_job_postings'),
  ])

  const out: Record<string, Pair[]> = {}
  for (const [cc, block] of Object.entries(ict.data.countries ?? {})) {
    const rows = block.ict_share_of_employment_pct ?? []
    if (rows.length) out[cc] = rows.map((r) => [r.year, round(r.value, 1)] as Pair)
  }
  const eu = ict.data.eu27_benchmark?.ict_share_of_employment_pct ?? []
  if (eu.length) out.EU27 = eu.map((r) => [r.year, round(r.value, 1)] as Pair)

  const indeed: Record<string, Pair[]> = {}
  for (const m of METROS) {
    const rows = ind.data[m]?.series ?? []
    if (rows.length) indeed[m] = rows.map((r) => [monthToX(r.month), round(r.index, 1)] as Pair)
  }

  return { ict: out, indeed, metrosAvailable: Object.keys(ind.data).length }
}

/* -------------------------------------------------------------- housing --- */

export interface HousingData {
  bis: Record<string, Pair[]>
  fhfa: Record<'detroit' | 'sf_bay_area', Pair[]>
  teranet: Record<'toronto' | 'vancouver', Pair[]>
  london: Pair[]
}

export async function loadHousing(): Promise<HousingData> {
  const [bis, fhfa, ter, uk] = await Promise.all([
    loadHistory<Record<string, { real_index: { period: string; value: number }[] }>>('bis_property_prices'),
    loadHistory<Record<string, { series: { year: number; quarter: number; index: number }[] }>>('fhfa_hpi_metro'),
    loadHistory<{ cities: Record<string, { series: { date: string; index: number }[] }> }>('teranet_national_bank_hpi'),
    loadHistory<Record<string, { series: { month: string; avg_price_gbp: number | null }[] }>>('uk_hpi'),
  ])

  const bisOut: Record<string, Pair[]> = {}
  for (const [cc, block] of Object.entries(bis.data)) {
    const rows = block.real_index ?? []
    if (rows.length) bisOut[cc] = lastPerYear(rows, (r) => Number(r.period.slice(0, 4)), (r) => r.value)
  }

  const fhfaOut = {} as HousingData['fhfa']
  for (const m of ['detroit', 'sf_bay_area'] as const) {
    const rows = (fhfa.data[m]?.series ?? []).filter((r) => r.year >= 1990)
    fhfaOut[m] = lastPerYear(rows, (r) => r.year, (r) => r.index)
  }

  const terOut = {} as HousingData['teranet']
  for (const c of ['toronto', 'vancouver'] as const) {
    const rows = ter.data.cities?.[c]?.series ?? []
    terOut[c] = meanPerYear(rows, (r) => Number(r.date.slice(0, 4)), (r) => r.index)
  }

  const lonRows = (uk.data.london?.series ?? []).filter((r) => r.avg_price_gbp != null)
  const london = meanPerYear(lonRows, (r) => Number(r.month.slice(0, 4)), (r) => r.avg_price_gbp!, 0)

  return { bis: bisOut, fhfa: fhfaOut, teranet: terOut, london }
}

/* --------------------------------------------------------------- people --- */

export interface PeopleData {
  mipex: Record<string, Pair[]>
  /** [year, millions, isProjection] */
  wpp: Record<string, [number, number, boolean][]>
}

export async function loadPeople(): Promise<PeopleData> {
  const [mip, wpp] = await Promise.all([
    loadHistory<Record<string, { overall: { year: number; score: number }[] }>>('mipex'),
    loadHistory<Record<string, { total_population: { year: number; value: number; is_projection: boolean }[] }>>('un_wpp'),
  ])

  const mipexOut: Record<string, Pair[]> = {}
  for (const [cc, block] of Object.entries(mip.data)) {
    const rows = block.overall ?? []
    if (rows.length) mipexOut[cc] = rows.map((r) => [r.year, round(r.score, 2)] as Pair)
  }

  const wppOut: PeopleData['wpp'] = {}
  for (const [cc, block] of Object.entries(wpp.data)) {
    const rows = block.total_population ?? []
    const sampled = rows.filter((_, i) => i % 2 === 0 || i === rows.length - 1)
    if (sampled.length) {
      wppOut[cc] = sampled.map((r) => [r.year, round(r.value / 1_000_000, 2), r.is_projection])
    }
  }

  return { mipex: mipexOut, wpp: wppOut }
}

/* ----------------------------------------------------------------- life --- */

export interface LifeData {
  /** [year, score, rank] */
  whr: Record<string, [number, number, number][]>
  rsf: Record<string, Pair[]>
  /** How many countries were ranked, per year — a rank without its denominator
   *  is not a fact. */
  whrRankedOf: Record<string, number>
}

export async function loadLife(): Promise<LifeData> {
  const [whr, rsf] = await Promise.all([
    loadHistory<{
      countries: Record<string, { year: number; rank: number; score: number }[]>
      ranked_countries_per_year: Record<string, number>
    }>('world_happiness_report'),
    loadHistory<Record<string, { year: number; score: number }[]>>('rsf_press_freedom'),
  ])

  const whrOut: LifeData['whr'] = {}
  for (const [cc, rows] of Object.entries(whr.data.countries ?? {})) {
    if (rows.length) whrOut[cc] = rows.map((r) => [r.year, r.score, r.rank])
  }

  const rsfOut: Record<string, Pair[]> = {}
  for (const [cc, rows] of Object.entries(rsf.data)) {
    if (rows.length) rsfOut[cc] = rows.map((r) => [r.year, round(r.score, 2)] as Pair)
  }

  return { whr: whrOut, rsf: rsfOut, whrRankedOf: whr.data.ranked_countries_per_year ?? {} }
}

/* ------------------------------------------------------------- naive ext --- */

/** Our own extrapolation: the average slope of the last ten points, extended.
 *  Deliberately dumb, drawn dashed, and labelled "not a forecast" wherever it
 *  appears. It is never merged with an institution's projection. */
export function naiveLine(pts: Pair[], to: number): Pair[] {
  const s = [...pts].sort((a, b) => a[0] - b[0]).slice(-10)
  const f = s[0]
  const l = s[s.length - 1]
  if (!f || !l || l[0] === f[0]) return []
  const k = (l[1] - f[1]) / (l[0] - f[0])
  const out: Pair[] = [[l[0], l[1]]]
  for (let x = l[0] + 1; x <= to; x++) out.push([x, l[1] + k * (x - l[0])])
  return out
}

/** Year-on-year change, in per cent. */
export function yoy(pts: Pair[]): Pair[] {
  const out: Pair[] = []
  for (let i = 1; i < pts.length; i++) {
    out.push([pts[i]![0], (pts[i]![1] / pts[i - 1]![1] - 1) * 100])
  }
  return out
}
