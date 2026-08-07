/* The five plain-language questions the dot field answers.
 *
 * Structure follows the approved field mockup: a plain question, a quiet
 * sub-line, an axis with a direction hint, a tick grid, and a formatter. Scales
 * are tuned to the REAL range across all 73 cities, which is wider than the
 * 30-city sample the mockup was drawn from.
 *
 * Every value comes from compute.ts or straight off the city record, so what the
 * field shows and what a profile page shows cannot drift apart.
 *
 * A question never ranks anything. Ordering along an axis is the axis, not a
 * verdict, and the site says so.
 */

import type { City, Country } from './types'
import { savingsPerYear, yearsToHome } from './compute'
import { money, moneyShort, num } from './format'

export type QuestionKind = 'swarm' | 'country'

/* A hand-picked partner metric — the approved presets, not free pairing.
 *
 * A partner is a whole axis, not just a number: it carries its own ticks and
 * its own plain-words title, because a y-axis with dots but no ruler is the
 * same as no y-axis at all. */
export interface SecondAxis {
  id: string
  /** Short name for the preset chip: "vs apartment price". */
  label: string
  /** The axis title, read straight after an up arrow:
   *  "↑ apartment price per m²". Always phrased so that up = more of this. */
  axisLabel: string
  hint: string
  value: (city: City, country: Country | undefined) => number | null
  /** value -> 0..100 up the field. 0 is the bottom of the plot. */
  scale: (v: number) => number
  ticks: [number, string][]
  fmt: (v: number | null) => string
}

export interface Question {
  id: string
  q: string
  sub: string
  kind: QuestionKind
  axisL: string
  axisR: string
  dir: string
  /** Plain-words name of the x metric, for the scatter axis title. */
  xLabel: string
  value: (city: City, country: Country | undefined) => number | null
  /** value -> 0..100 position across the field */
  scale: (v: number) => number
  ticks: [number, string][]
  fmt: (v: number | null) => string
  /** Values at or above this are pinned to the far end and labelled. */
  cap?: number
  /** Approved partners for this question. Absent = no second axis at all,
   *  which is why the PR/citizenship bars never offer the toggle. */
  secondAxes?: SecondAxis[]
}

/* Years-to-home is piecewise: linear to 30 years, then compressed, because a
   handful of cities run to four figures and would otherwise flatten everything
   else against the left edge. */
export function xYears(v: number): number {
  if (v >= 130) return 95
  if (v <= 30) return 4 + ((v - 2) / 28) * 70
  return 74 + ((v - 30) / 100) * 18
}

const clamp = (v: number) => Math.max(2, Math.min(97, v))

export const QUESTIONS: Question[] = [
  {
    id: 'home',
    q: 'Where can you actually buy a home?',
    sub: 'years to a 90 m² place — mid-level salary, single, your assumptions editable',
    kind: 'swarm',
    axisL: '2 yrs',
    axisR: '≈never',
    dir: '← faster',
    xLabel: 'years to a home',
    cap: 130,
    value: (c) => yearsToHome(c, 'mid'),
    scale: xYears,
    ticks: [[2, '2'], [5, '5'], [10, '10'], [20, '20'], [30, '30'], [130, '30+']],
    fmt: (v) =>
      v == null ? 'no data' : v >= 130 ? '≈never' : v >= 30 ? `${Math.round(v)} yrs` : `${v.toFixed(1)} yrs`,
    secondAxes: [{
      id: 'price_m2',
      label: 'apartment price',
      axisLabel: 'apartment price per m²',
      hint: 'separates a cheap city from an impossible one',
      value: (c) => c.apt_price_outside_usd_m2,
      // Real range across the 73 cities: $1,300–$8,900 per m².
      scale: (v) => clamp(((v - 1000) / 8200) * 100),
      ticks: [[2000, '$2k'], [4000, '$4k'], [6000, '$6k'], [8000, '$8k']],
      fmt: (v) => (v == null ? 'no data' : `${money(v)}/m²`),
    }],
  },
  {
    id: 'pay',
    q: 'Who pays the most?',
    sub: 'gross mid-level developer salary · USD per year · two-tier where noted',
    kind: 'swarm',
    axisL: '$30k',
    axisR: '$280k',
    dir: 'more →',
    xLabel: 'gross salary',
    value: (c) => c.salary_usd_year.mid,
    scale: (v) => clamp(4 + ((v - 30000) / 250000) * 91),
    ticks: [[50000, '$50k'], [100000, '$100k'], [150000, '$150k'], [200000, '$200k'], [250000, '$250k']],
    fmt: (v) => (v == null ? 'no data' : moneyShort(v)),
    secondAxes: [{
      id: 'monthly_cost',
      label: 'total monthly cost',
      axisLabel: 'rent + living costs, per month',
      hint: 'rent and living costs combined',
      value: (c) =>
        c.rent_1br_outside_usd_month == null || c.col_single_no_rent_usd_month == null
          ? null
          : c.rent_1br_outside_usd_month + c.col_single_no_rent_usd_month,
      // Real range: $1,650–$4,620 a month.
      scale: (v) => clamp(((v - 1500) / 3300) * 100),
      ticks: [[2000, '$2k'], [3000, '$3k'], [4000, '$4k']],
      fmt: (v) => (v == null ? 'no data' : `${money(v)}/mo`),
    }],
  },
  {
    id: 'left',
    q: "What's left at the end of a year?",
    sub: 'take-home pay minus rent minus living costs · computed, formula shown',
    kind: 'swarm',
    axisL: '$0',
    axisR: '$150k',
    dir: 'keep more →',
    xLabel: 'money kept per year',
    value: (c) => savingsPerYear(c, 'mid'),
    scale: (v) => clamp(4 + (Math.max(v, 0) / 150000) * 91),
    ticks: [[25000, '$25k'], [50000, '$50k'], [75000, '$75k'], [100000, '$100k'], [125000, '$125k']],
    fmt: (v) => (v == null ? 'no data' : moneyShort(v)),
    secondAxes: [{
      id: 'happiness',
      label: 'happiness',
      // Named for the direction, because the numbers run the other way: the
      // axis is inverted so #1 sits at the top, and the ticks say so.
      axisLabel: 'happier — world happiness rank',
      hint: 'money against how people rate their lives',
      value: (_c, k) => k?.enriched.happiness?.rank ?? k?.indices.whr_rank ?? null,
      // Real range across the 15 countries: #1–#41.
      scale: (v) => clamp(100 - ((v - 1) / 46) * 100),
      ticks: [[1, '#1'], [10, '#10'], [20, '#20'], [30, '#30'], [40, '#40']],
      fmt: (v) => (v == null ? 'no data' : `#${num(v)}`),
    }],
  },
  {
    id: 'stay',
    q: 'Time to PR & citizenship?',
    sub: 'typical years, country level — real cases vary; exact ranges on each country page',
    kind: 'country',
    axisL: 'arrival',
    axisR: '20 yrs',
    dir: '← sooner',
    xLabel: 'years to residency',
    value: (_c, k) => k?.pr_years_typical ?? null,
    scale: (v) => clamp((v / 20) * 100),
    ticks: [],
    fmt: (v) => (v == null ? 'no path' : `~${v} yrs to residency`),
    // No secondAxes, so the toggle never appears here: these are two-stage
    // country bars, and there is nothing for a second axis to scatter.
  },
  {
    id: 'sun',
    q: 'Where does the sun shine?',
    sub: 'sunshine hours per year · climate normals',
    kind: 'swarm',
    axisL: '1,400 h',
    axisR: '3,900 h',
    dir: 'sunnier →',
    xLabel: 'sunshine hours a year',
    value: (c) => c.climate.sunshine_hours_yr,
    // Widened from the mockup: the full 73-city range is 1,400-3,872.
    scale: (v) => clamp(4 + ((v - 1400) / 2500) * 91),
    ticks: [[1800, '1,800'], [2400, '2,400'], [3000, '3,000'], [3600, '3,600']],
    fmt: (v) => (v == null ? 'no data' : `${num(v)} h`),
    // The only question with two approved partners: the seasonal switch is a
    // choice between them, so it lives in the preset chip rather than in a
    // second button the reader has to connect to the first.
    secondAxes: [
      {
        id: 'winter_low',
        label: 'winter low',
        axisLabel: 'winter average low',
        hint: 'sunshine against how cold it actually gets',
        value: (c) => c.climate.winter_avg_low_c,
        // Real range: −14.3 °C to +16.1 °C.
        scale: (v) => clamp(((v + 16) / 34) * 100),
        ticks: [[-10, '−10°'], [-5, '−5°'], [0, '0°'], [5, '5°'], [10, '10°'], [15, '15°']],
        fmt: (v) => (v == null ? 'no data' : `${num(v, 1)} °C`),
      },
      {
        id: 'summer_high',
        label: 'summer high',
        axisLabel: 'summer average high',
        hint: 'sunshine against how hot it actually gets',
        value: (c) => c.climate.summer_avg_high_c,
        // Real range: 18.6 °C to 43.4 °C.
        scale: (v) => clamp(((v - 17) / 28) * 100),
        ticks: [[20, '20°'], [25, '25°'], [30, '30°'], [35, '35°'], [40, '40°']],
        fmt: (v) => (v == null ? 'no data' : `${num(v, 1)} °C`),
      },
    ],
  },
]

/* Selection colours: six distinct, then one shared colour for everyone after,
   exactly as approved. Six is where distinct hues stop being tellable apart. */
export const PICK_COLORS = [
  'var(--pick-1)', 'var(--pick-2)', 'var(--pick-3)',
  'var(--pick-4)', 'var(--pick-5)', 'var(--pick-6)',
]
export const PICK_REST = 'var(--pick-rest)'

export function pickColor(index: number): string {
  return PICK_COLORS[index] ?? PICK_REST
}

/* Cities whose labels survive collision-hiding, so the field always keeps a few
   fixed reference points a reader can orient by. */
export const ANCHORS = new Set([
  'detroit', 'sf_bay_area', 'berlin', 'toronto', 'milan', 'london', 'sydney',
])
