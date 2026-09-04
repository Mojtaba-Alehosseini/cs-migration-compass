/* The metric registry.
 *
 * One definition per metric, consumed by Compare, the scatter builder and the
 * weights tool, so a metric behaves identically everywhere and only has to be
 * described once. Themes match the seven groups in the brief.
 *
 * `direction` exists so composite tools know which way is "better" — it is NOT
 * used to rank anything by default. Nothing in this file decides an ordering. */

import type { Band, City, Confidence, Country } from './types'
import { m2PerYear, savingsPerYear, yearsToHome, netFor } from './compute'
import { money, moneyShort, num, pct, rankOf, years, NO_DATA, sourceName, sourceUrlByHost } from './format'

export type ThemeKey = 'money' | 'visa' | 'jobs' | 'housing' | 'people' | 'life' | 'climate'

/** A tick label, given the value and the distance to the next tick. */
export type TickFormat = (v: number, step: number) => string

/** How many decimals a step of this size needs before two neighbouring ticks
 *  round to the same string. */
const decimalsFor = (step: number) =>
  Math.min(6, Math.max(0, Math.ceil(-Math.log10(Math.abs(step || 1)) + 1e-9)))

/** Money on an axis. Compact only where the step is coarse enough to survive
 *  it — at a $500 step, "$1k" and "$1k" would be two different places. */
const moneyTick: TickFormat = (v, step) =>
  Math.abs(step) >= 1000
    ? `${v < 0 ? '−' : ''}$${num(Math.abs(v) / 1000, decimalsFor(step / 1000))}k`
    : money(v)

const yearsTick: TickFormat = (v, step) => `${num(v, decimalsFor(step))} yrs`
const rankTick: TickFormat = (v, step) => `#${num(v, decimalsFor(step))}`

export const THEMES: { key: ThemeKey; label: string; blurb: string }[] = [
  { key: 'money', label: 'Money', blurb: 'Pay, tax, what is left at the end of a year' },
  { key: 'visa', label: 'Visas & staying', blurb: 'Getting in, staying, becoming a citizen' },
  { key: 'jobs', label: 'Finding work', blurb: 'How many tech jobs exist and who is hiring' },
  { key: 'housing', label: 'Homes & rent', blurb: 'Rent, purchase prices, years to own' },
  { key: 'people', label: 'People like you', blurb: 'Who already moved there, and from where' },
  { key: 'life', label: 'Daily life', blurb: 'Happiness, safety, health, press freedom' },
  { key: 'climate', label: 'Weather', blurb: 'Sun, summer heat, winter cold, rain' },
]

export interface MetricDef {
  key: string
  label: string
  /** Full plain-language statement for headers and tooltips. */
  hint: string
  theme: ThemeKey
  /** null when the place genuinely has no value for it. */
  value: (city: City, country: Country | undefined, band: Band) => number | null
  /** How ONE figure reads. May clamp, bucket or return words — "100+ yrs",
   *  "free", "usually yes" are all correct for a single datum. */
  format: (v: number | null) => string
  /** How an AXIS TICK reads, which is a different job. A formatter that clamps
   *  or buckets makes two ticks say the same thing, and an axis whose labels are
   *  not injective describes nothing.
   *
   *  It is given the axis STEP as well as the value, because precision is a
   *  property of the spacing, not of the number: `$1k` is a fine label when
   *  ticks are 50,000 apart and a collision when they are 500 apart. Defaults to
   *  plain numeric; override only where the unit genuinely carries meaning. */
  tickFormat?: TickFormat
  /** Ticks are not allowed below this. Ranks start at #1: there is no #0. */
  axisFloor?: number
  /** False for categorical metrics. The distance between "rarely" and "often"
   *  is not a number, so they cannot honestly occupy a continuous axis. */
  axisEligible?: boolean
  direction: 'higher_better' | 'lower_better' | 'neutral'
  confidence: Confidence
  /** Which source the figure comes from, for the popover. */
  source?: (city: City, country: Country | undefined) => { name: string; url?: string; what?: string }
  /** Default headline metrics shown before the user adds anything. */
  headline?: boolean
  unit?: string
}

const numbeo = (city: City, what: string) => ({
  name: 'Numbeo',
  url: sourceUrlByHost(city.sources, ['numbeo.com']) ?? 'https://www.numbeo.com/cost-of-living/',
  what,
})

/** Which real source this city's own "Developer salary" band traces to —
 *  read from `salary_usd_year.primary_source`, itself hand-set once per city
 *  from that city's own `note` (see SalaryPrimarySource in types.ts), never
 *  guessed at render time. Package 26 found this card hardcoded to "talent.com
 *  + PayScale" for every city regardless of what the record actually says;
 *  package 27 traced all 73 notes and found the true picture is far more
 *  varied — PayScale nationally for most Nordic/UK/Ireland cities, talent.com
 *  for Canada, levels.fyi for most of Germany and the US metros it covers, BLS
 *  or Indeed where levels.fyi's own metro page was unreachable, Indeed+SEEK
 *  for four Australian cities, and a genuine multi-source triangulation
 *  (Glassdoor, KeepCoding, TechPays, and others) everywhere none of those is
 *  clearly dominant — see NEEDS-DECISION #59. A city whose record does not
 *  support a single named source says so ("Compiled estimate") rather than
 *  naming one anyway. */
export function citySalarySource(city: City): { name: string; url?: string; what: string } {
  const what = city.salary_usd_year.note ?? 'Market-wide band for this city.'
  const src = city.salary_usd_year.primary_source
  switch (src) {
    case 'payscale_nolink':
      return { name: 'PayScale', what }
    case 'payscale_linked':
      return { name: 'PayScale', url: sourceUrlByHost(city.sources, ['payscale.com']), what }
    case 'talentcom_nolink':
      return { name: 'talent.com', what }
    case 'levelsfyi_linked':
      // Package 27's own adversarial review: 4 of these 21 cities' own
      // salary_levels_fyi.source is a bare, unresolved stub
      // ("…/locations/", no city slug) — src_levels_fyi.py tried every
      // route pattern it knows and recorded WHY in unavailable_reason
      // rather than substitute a guess, but citySalarySource() was reading
      // .source unconditionally, so the citation still offered a link that
      // does not resolve to this city's own page. Only offer the link when
      // a route genuinely resolved.
      return {
        name: 'levels.fyi',
        url: city.salary_levels_fyi?.unavailable_reason ? undefined : city.salary_levels_fyi?.source,
        what,
      }
    case 'bls_linked':
      return { name: sourceName('https://bls.gov'), url: sourceUrlByHost(city.sources, ['bls.gov', 'api.bls.gov']), what }
    case 'indeed_linked':
      return { name: 'Indeed', url: sourceUrlByHost(city.sources, ['indeed.com', 'au.indeed.com', 'it.indeed.com']), what }
    case 'indeed_seek_linked':
      // Indeed backs new_grad and senior, SEEK backs mid — both real, only one
      // URL field to offer, and Indeed covers two of the three bands. `what`
      // (the note) names both explicitly either way.
      return { name: 'Indeed + SEEK', url: sourceUrlByHost(city.sources, ['indeed.com', 'au.indeed.com', 'it.indeed.com']), what }
    case 'compiled':
    default:
      return { name: 'Compiled estimate', what }
  }
}

/** Package 27, Tier 2: `Compare.tsx`'s fallback used to link `country.sources[0]`
 *  or `city.sources[0]` for any metric with no source of its own — whichever URL
 *  a country's own harvesters happened to append first, regardless of the
 *  metric asking. For Norway that was a private immigration-law firm's blog
 *  post about SALARY THRESHOLDS, linked under a "Norway — official sources"
 *  label on the VISA-timeline card. The GulfTalent defect in a different
 *  costume: a position in an unordered array standing in for a recorded
 *  relationship.
 *
 *  Read all 15 countries' own `sources[]` by hand (not pattern-matched) for a
 *  genuine government immigration-authority domain. 8 have one: this is that
 *  record, not a guess — `sourceUrlByHost()` below still only returns a URL
 *  if the exact host is actually present for that country, so a wrong or
 *  stale entry here fails safe (no link) rather than pointing anywhere false.
 *  The other 7 (Canada, Germany, Italy, Spain, Sweden, UAE, Qatar) never had
 *  an official source captured at all — every visa/salary-threshold URL on
 *  their own record is a law firm, immigration consultancy or news write-up,
 *  confirmed by reading each one, not assumed absent. */
const OFFICIAL_IMMIGRATION_HOST: Partial<Record<string, string>> = {
  AU: 'immi.homeaffairs.gov.au',
  US: 'travel.state.gov',
  GB: 'gov.uk',
  IE: 'enterprise.gov.ie',
  NL: 'ind.nl',
  DK: 'nyidanmark.dk',
  NO: 'udi.no',
  FI: 'migri.fi',
  // Package 27's own adversarial review: Migrationsverket is Sweden's real,
  // singular immigration authority (work permits, residence, citizenship —
  // not narrowly the one citizenship-news article `sources[]` happens to
  // carry). Missing here originally for no principled reason — Norway's own
  // `udi.no` entry is equally narrow (a citizenship-testing page) and was
  // included; Sweden should have been treated the same way.
  SE: 'migrationsverket.se',
}

/** Shared by salary_net and net_pct — both read the same per-city flat tax
 *  scalar (see NEEDS-DECISION #22's own overstatement caveat), so both carry
 *  the identical citation rather than one having it and the other falling
 *  through to a guessed source for what is, underneath, the same number. */
function taxSource(country: Country | undefined) {
  return {
    name: 'OECD Taxing Wages + national calculators',
    // NEEDS-DECISION #22 — net_pct is ONE flat scalar per city, calibrated
    // against that city's own published MID-band salary. Real income tax
    // is progressive: a higher gross salary is taxed at a higher EFFECTIVE
    // rate, so the share that survives as net actually FALLS as salary
    // rises above the band this rate was calibrated against — applying
    // the mid-calibrated (higher) survival share to a higher gross
    // therefore OVERSTATES what a real progressive system would leave
    // them, never understates it. Adversarial review, package 21: the
    // first version of this note stated the direction backwards
    // ("understates"), the exact opposite of what a rising effective tax
    // rate implies. Not shipped as a fix (modelling real bracket
    // schedules for fifteen countries is a genuine harvesting effort);
    // disclosed here instead, on every figure this scalar feeds.
    what: `${country?.tax.net_note ?? 'Single person at a mid-level developer salary.'} A single flat `
      + `rate for the whole city, calibrated at the mid-level salary — real tax is progressive, `
      + `so this OVERSTATES the true net figure the further a salary sits above what this rate `
      + `was calibrated against (a real progressive system would keep less, not more).`,
  }
}

function countryImmigrationSource(country: Country | undefined, what: string | undefined) {
  const host = country ? OFFICIAL_IMMIGRATION_HOST[country.id] : undefined
  const url = host && country ? sourceUrlByHost(country.sources, [host]) : undefined
  return {
    name: url ? `${country?.name} — official immigration authority` : 'Compiled — no official source captured',
    url,
    what,
  }
}

export const METRICS: MetricDef[] = [
  // ---------------- Money ----------------
  {
    key: 'salary_gross',
    label: 'Developer salary',
    hint: 'What a developer earns per year, before tax',
    theme: 'money',
    headline: true,
    value: (c, _k, band) => c.salary_usd_year[band],
    format: money,
    tickFormat: moneyTick,
    direction: 'higher_better',
    confidence: 'crowd',
    source: (c) => citySalarySource(c),
  },
  {
    key: 'salary_levels_fyi',
    label: 'Top-employer pay',
    hint: 'Median total compensation at large, known employers — base plus stock plus bonus',
    theme: 'money',
    value: (c) => c.salary_levels_fyi?.median_total_comp_usd ?? null,
    format: money,
    tickFormat: moneyTick,
    direction: 'higher_better',
    confidence: 'crowd',
    source: (c) => ({
      name: 'levels.fyi',
      url: c.salary_levels_fyi?.source,
      what: 'Total compensation (base + stock + bonus) against a market BASE-pay band — partly a definition difference, not purely an employer premium. Correlated with the market band (r = 0.90) but NOT interchangeable: 1.22x high on average, 95% limits 0.79x-1.89x. Never blended with it.',
    }),
  },
  {
    key: 'salary_net',
    label: 'Take-home pay',
    hint: 'Per year, after that country’s real tax and social contributions',
    theme: 'money',
    value: (c, _k, band) => netFor(c, band),
    format: money,
    tickFormat: moneyTick,
    direction: 'higher_better',
    confidence: 'official',
    source: (_c, k) => taxSource(k),
  },
  {
    key: 'savings',
    label: 'Kept after rent and living',
    hint: 'What is actually left at the end of a year, after tax, rent and living costs',
    theme: 'money',
    headline: true,
    value: (c, _k, band) => savingsPerYear(c, band),
    format: money,
    tickFormat: moneyTick,
    direction: 'higher_better',
    confidence: 'crowd',
  },
  {
    key: 'net_pct',
    label: 'Share of pay you keep',
    hint: 'How much of the gross salary survives tax',
    theme: 'money',
    value: (c) => c.net_pct,
    format: (v) => pct(v),
    direction: 'higher_better',
    confidence: 'official',
    source: (_c, k) => taxSource(k),
  },

  // ---------------- Visas & staying ----------------
  {
    key: 'pr_years',
    label: 'Years to permanent residency',
    hint: 'Typical time from arriving to being allowed to stay for good',
    theme: 'visa',
    headline: true,
    value: (_c, k) => k?.pr_years_typical ?? null,
    format: (v) => (v == null ? 'no permanent path' : `~${num(v, v && v % 1 ? 1 : 0)} yrs`),
    // The tilde means "typically, for this country". A scale point is exact, so
    // it does not carry one.
    tickFormat: yearsTick,
    direction: 'lower_better',
    confidence: 'official',
    source: (_c, k) => countryImmigrationSource(k, 'Typical time to permanent residency.'),
  },
  {
    key: 'citizenship_years',
    label: 'Years to citizenship',
    hint: 'Typical time from arriving to being eligible for a passport',
    theme: 'visa',
    value: (_c, k) => k?.citizenship_years_typical ?? null,
    format: (v) => (v == null ? 'no citizenship path' : `~${num(v)} yrs`),
    tickFormat: yearsTick,
    direction: 'lower_better',
    confidence: 'official',
    source: (_c, k) => countryImmigrationSource(k, 'Typical time to citizenship eligibility.'),
  },
  {
    key: 'tuition',
    label: 'Master’s tuition',
    hint: 'A year of an international master’s, if you come as a student',
    theme: 'visa',
    value: (_c, k) => k?.visa.study_pathway?.masters_tuition_intl_usd_yr ?? null,
    format: (v) => (v === 0 ? 'free' : money(v)),
    // "free" is a fact about a country, not a point on a scale.
    tickFormat: moneyTick,
    direction: 'lower_better',
    confidence: 'official',
    source: (_c, k) => countryImmigrationSource(k, k?.visa.study_pathway?.note ?? 'International master’s tuition, per year.'),
  },
  {
    key: 'post_study_months',
    label: 'Stay-back after studying',
    hint: 'Months you may stay to look for work after graduating',
    theme: 'visa',
    value: (_c, k) => k?.visa.study_pathway?.post_study_visa_months ?? null,
    format: (v) => (v == null ? NO_DATA : `${num(v)} months`),
    direction: 'higher_better',
    confidence: 'official',
    source: (_c, k) => countryImmigrationSource(k, 'Post-study work-search visa length.'),
  },

  // ---------------- Finding work ----------------
  {
    key: 'ict_specialists',
    label: 'IT specialists employed',
    hint: 'How many people work in IT nationally — the size of the job market',
    theme: 'jobs',
    value: (_c, k) => (k?.enriched.ict_specialists?.thousands ?? null),
    format: (v) => (v == null ? NO_DATA : `${num(v * 1000)}`),
    direction: 'higher_better',
    confidence: 'official',
    source: () => ({
      name: 'Eurostat',
      url: 'https://ec.europa.eu/eurostat/databrowser/view/isoc_sks_itspt',
      what: 'Employed ICT specialists. EU/EFTA only — other countries show no data rather than a substitute.',
    }),
  },
  {
    key: 'ict_share',
    label: 'IT share of all jobs',
    hint: 'What proportion of everyone working is in IT',
    theme: 'jobs',
    // Same field as ict_specialists above — share_pct sits on the identical
    // enriched.ict_specialists object, not a second dataset, so it carries
    // the same citation rather than falling through to a guessed one.
    value: (_c, k) => k?.enriched.ict_specialists?.share_pct ?? null,
    format: (v) => pct(v, 1),
    direction: 'higher_better',
    confidence: 'official',
    source: () => ({
      name: 'Eurostat',
      url: 'https://ec.europa.eu/eurostat/databrowser/view/isoc_sks_itspt',
      what: 'Employed ICT specialists as a share of total employment. EU/EFTA only.',
    }),
  },

  // ---------------- Homes & rent ----------------
  {
    key: 'rent_outside',
    label: 'Rent, 1-bed outside centre',
    hint: 'Monthly rent for a one-bedroom flat away from the centre',
    theme: 'housing',
    headline: true,
    value: (c) => c.rent_1br_outside_usd_month,
    format: (v) => money(v),
    tickFormat: moneyTick,
    direction: 'lower_better',
    confidence: 'crowd',
    source: (c) => numbeo(c, 'Crowd-reported rents. Solid in big cities, thin in small ones.'),
  },
  {
    key: 'rent_centre',
    label: 'Rent, 1-bed in the centre',
    hint: 'Monthly rent for a one-bedroom flat in the city centre',
    theme: 'housing',
    value: (c) => c.rent_1br_center_usd_month,
    format: (v) => money(v),
    tickFormat: moneyTick,
    direction: 'lower_better',
    confidence: 'crowd',
    source: (c) => numbeo(c, 'Crowd-reported rents.'),
  },
  {
    key: 'living_costs',
    label: 'Living costs, excluding rent',
    hint: 'Food, transport, phone and everything else for one person per month',
    theme: 'housing',
    value: (c) => c.col_single_no_rent_usd_month,
    format: (v) => money(v),
    tickFormat: moneyTick,
    direction: 'lower_better',
    confidence: 'crowd',
    source: (c) => numbeo(c, 'Single person, excluding rent.'),
  },
  {
    key: 'total_monthly',
    label: 'Total monthly cost',
    hint: 'Rent plus living costs — the real monthly number',
    theme: 'housing',
    value: (c) =>
      c.rent_1br_outside_usd_month == null || c.col_single_no_rent_usd_month == null
        ? null
        : c.rent_1br_outside_usd_month + c.col_single_no_rent_usd_month,
    format: (v) => money(v),
    tickFormat: moneyTick,
    direction: 'lower_better',
    confidence: 'crowd',
  },
  {
    key: 'apt_m2',
    label: 'Apartment price per m²',
    hint: 'What a square metre costs to buy, outside the centre',
    theme: 'housing',
    value: (c) => c.apt_price_outside_usd_m2,
    format: (v) => money(v),
    tickFormat: moneyTick,
    direction: 'lower_better',
    confidence: 'crowd',
    source: (c) => numbeo(c, 'Purchase price per square metre, outside the centre.'),
  },
  {
    key: 'years_to_home',
    label: 'Years to own a 90 m² flat',
    hint: 'How long your savings take to buy a home outright',
    theme: 'housing',
    headline: true,
    value: (c, _k, band) => yearsToHome(c, band),
    format: (v) => years(v),
    // `years()` clamps at "100+ yrs", which is right for one city and fatal for
    // a scale: with a 0–2,500 domain it made five of six ticks identical.
    tickFormat: yearsTick,
    direction: 'lower_better',
    confidence: 'crowd',
  },
  {
    key: 'm2_per_year',
    label: 'Square metres bought per year',
    hint: 'How much of a flat a year of saving actually buys',
    theme: 'housing',
    value: (c, _k, band) => m2PerYear(c, band),
    format: (v) => (v == null ? NO_DATA : `${num(v, 1)} m²`),
    direction: 'higher_better',
    confidence: 'crowd',
  },

  // ---------------- People like you ----------------
  {
    key: 'foreign_born',
    label: 'People born abroad',
    hint: 'Share of the population that moved there from another country',
    theme: 'people',
    headline: true,
    value: (_c, k) => k?.enriched.foreign_born?.share_pct ?? null,
    format: (v) => pct(v, 1),
    direction: 'neutral',
    confidence: 'official',
    source: (_c, k) => ({
      name: 'UN DESA ÷ World Bank',
      url: 'https://www.un.org/development/desa/pd/content/international-migrant-stock',
      what: k?.enriched.foreign_born?.formula,
    }),
  },
  {
    key: 'iranian_born',
    label: 'Iranian-born residents',
    hint: 'How many people born in Iran already live there',
    theme: 'people',
    value: (_c, k) => k?.enriched.iranian_born?.count ?? null,
    format: (v) => (v == null ? NO_DATA : num(v)),
    direction: 'neutral',
    confidence: 'official',
    source: () => ({
      name: 'UN DESA migrant stock 2024',
      url: 'https://www.un.org/development/desa/pd/content/international-migrant-stock',
      what: 'Origin-by-destination matrix, 2024 reference year.',
    }),
  },
  {
    key: 'english_work',
    label: 'English at work',
    hint: 'Whether you can realistically work in English',
    theme: 'people',
    value: (_c, k) => {
      const v = k?.language.english_work
      return v === 'high' ? 3 : v === 'medium' ? 2 : v === 'low' ? 1 : null
    },
    format: (v) => (v === 3 ? 'usually yes' : v === 2 ? 'often, depends on the employer' : v === 1 ? 'rarely' : NO_DATA),
    // Three named categories dressed as 1/2/3. A tick at 1.5 means nothing and
    // the gap between "rarely" and "often" is not a distance, so this metric
    // does not belong on a continuous axis at all. See docs/LIMITATIONS.md.
    axisEligible: false,
    direction: 'higher_better',
    confidence: 'official',
  },

  // ---------------- Daily life ----------------
  {
    key: 'happiness_rank',
    label: 'Happiness rank',
    hint: 'Where the country lands when residents rate their own lives',
    theme: 'life',
    value: (_c, k) => k?.enriched.happiness?.rank ?? k?.indices.whr_rank ?? null,
    format: (v) => (v == null ? NO_DATA : `#${num(v)}`),
    // There is no rank #0, so the axis is not allowed to draw one.
    tickFormat: rankTick,
    axisFloor: 1,
    direction: 'lower_better',
    confidence: 'index',
    source: (_c, k) => ({
      name: 'World Happiness Report',
      url: 'https://worldhappiness.report/',
      what: k?.enriched.happiness
        ? `${rankOf(k.enriched.happiness.rank, k.enriched.happiness.of)} in ${k.enriched.happiness.year}.`
        : undefined,
    }),
  },
  {
    key: 'peace_rank',
    label: 'Peacefulness rank',
    hint: 'Global Peace Index position — lower is more peaceful',
    theme: 'life',
    value: (_c, k) => k?.indices.gpi_rank ?? null,
    format: (v) => (v == null ? NO_DATA : `#${num(v)} of 163`),
    tickFormat: rankTick,
    axisFloor: 1,
    direction: 'lower_better',
    confidence: 'index',
    // Every country's own `sources[]` carries a third-party ranking
    // aggregator for this (statranker.org), never the index's own publisher —
    // same lesson as happiness_rank above: a single well-known index has one
    // real citation regardless of country, not whatever aggregator a search
    // happened to surface.
    source: () => ({
      name: 'Global Peace Index',
      url: 'https://www.visionofhumanity.org/maps/',
      what: 'Institute for Economics & Peace — 2026 edition.',
    }),
  },
  {
    key: 'healthcare',
    label: 'Healthcare score',
    hint: 'How residents rate the health system',
    theme: 'life',
    value: (_c, k) => k?.indices.numbeo_healthcare_index ?? null,
    format: (v) => (v == null ? NO_DATA : num(v, 1)),
    direction: 'higher_better',
    confidence: 'crowd',
    source: () => ({
      name: 'Numbeo',
      url: 'https://www.numbeo.com/health-care/rankings_by_country.jsp',
      what: 'Crowd-reported healthcare quality index, by country.',
    }),
  },
  {
    key: 'hdi',
    label: 'Human Development Index',
    hint: 'The UN’s combined measure of health, education and income',
    theme: 'life',
    value: (_c, k) => k?.indices.hdi ?? null,
    format: (v) => (v == null ? NO_DATA : v.toFixed(3)),
    direction: 'higher_better',
    confidence: 'index',
    // Same lesson again: every country's sources[] carries Wikipedia's own
    // list page for this, not UNDP's — the actual publisher.
    source: () => ({
      name: 'UNDP Human Development Reports',
      url: 'https://hdr.undp.org/data-center/human-development-index',
      what: 'UN Development Programme — combined health, education and income index.',
    }),
  },

  // ---------------- Weather ----------------
  {
    key: 'sunshine',
    label: 'Hours of sunshine a year',
    hint: 'Total annual sunshine — the winter-darkness question',
    theme: 'climate',
    value: (c) => c.climate.sunshine_hours_yr,
    format: (v) => (v == null ? NO_DATA : `${num(v)} h`),
    direction: 'higher_better',
    confidence: 'official',
  },
  {
    key: 'summer_high',
    label: 'Typical summer high',
    hint: 'Average daytime high in the warmest months',
    theme: 'climate',
    value: (c) => c.climate.summer_avg_high_c,
    format: (v) => (v == null ? NO_DATA : `${num(v, 1)} °C`),
    direction: 'neutral',
    confidence: 'official',
  },
  {
    key: 'winter_low',
    label: 'Typical winter low',
    hint: 'Average overnight low in the coldest months',
    theme: 'climate',
    value: (c) => c.climate.winter_avg_low_c,
    format: (v) => (v == null ? NO_DATA : `${num(v, 1)} °C`),
    direction: 'neutral',
    confidence: 'official',
  },
  {
    key: 'rainy_days',
    label: 'Rainy days a year',
    hint: 'How many days a year see rain',
    theme: 'climate',
    value: (c) => c.climate.rainy_days_yr,
    format: (v) => (v == null ? NO_DATA : `${num(v)} days`),
    direction: 'lower_better',
    confidence: 'official',
  },
  {
    key: 'tehran_hours',
    label: 'Flight time from Tehran',
    hint: 'Typical door-to-door hours, including stops',
    theme: 'climate',
    value: (c) => c.tehran_travel?.typical_hours ?? null,
    format: (v) => (v == null ? NO_DATA : `${num(v)} h`),
    direction: 'lower_better',
    confidence: 'index',
  },
]

export const METRIC_BY_KEY = new Map(METRICS.map((m) => [m.key, m]))

/** Plain numeric, the default for every axis: no clamping, no bucketing, no
 *  words — the three things that make two ticks say the same thing — and
 *  enough decimals for the step it is given. */
export const numericTick: TickFormat = (v, step) => num(v, decimalsFor(step))

/** How a tick on THIS metric's axis should read. */
export function tickFormatFor(metric: MetricDef): TickFormat {
  return metric.tickFormat ?? numericTick
}

/** Metrics that can honestly occupy a continuous axis. A categorical metric is
 *  excluded here rather than formatted around. */
export const AXIS_METRICS = METRICS.filter((m) => m.axisEligible !== false)

export const HEADLINE_KEYS = METRICS.filter((m) => m.headline).map((m) => m.key)

export function metricsByTheme(theme: ThemeKey): MetricDef[] {
  return METRICS.filter((m) => m.theme === theme)
}

/** Compact formatter used in dense chart axes. */
export function compactFor(metric: MetricDef): (v: number | null) => string {
  if (metric.format === money) return moneyShort
  return metric.format
}
