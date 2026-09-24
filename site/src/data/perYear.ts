/* Package 47, NEEDS-DECISION #88 — its own module, with type-only imports, so
 * the rule is unit-tested directly (site/tests/perYear.test.ts): profile.ts
 * pulls in store.ts, which reads import.meta.env the moment it loads, and
 * Node's test runner has none. */

import type { WageCountry } from './explore'
import type { EstimateStep } from './profile'

/** Package 47, NEEDS-DECISION #88 — ruled: every row per year, with the
 *  pipeline's own conversion, marked as ours.
 *
 *  Takes an estimate in the row's published period and puts it on a year
 *  with `native.per_year.factor`, which build_wage_distribution.py computed
 *  through normalise.annualise() — so the hours are the pipeline's (Denmark's
 *  37-hour standard week, Canada's LFS hours), never a guessed 2,080. The
 *  estimate itself is untouched: the position is ranked on it, in the
 *  published period, exactly as before.
 *
 *  ROUNDING, stated, and set by what the multiplier is: a figure put on a year
 *  through MEASURED hours is shown to three significant figures, because the
 *  hours are measured to three — CA$56.49 × 39.8 × 52 is CA$116,912 to the
 *  dollar and about CA$117,000 in truth. A multiplier that is a definition —
 *  twelve months, or Denmark's 37-hour standard week, the unit its hourly
 *  figure is defined in — adds no measurement of its own, so that year is
 *  shown to the unit, as the figure it multiplies is.
 *
 *  A row the pipeline could not convert keeps its published period and its
 *  card says why. */
export interface PerYearView {
  /** What the cell shows, after the rounding above. */
  value: number
  /** The period the cell shows — 'year', unless the row could not be converted. */
  period: 'hour' | 'month' | 'year'
  /** Steps to append to the estimate's own chain. Empty for a published-annual row. */
  steps: EstimateStep[]
  /** Monthly rows: what twelve months of the figure count and leave out. */
  concept?: { name: string; office: string; includes?: string; excludes?: string }
}

const _num = (v: number, maxFrac: number) => v.toLocaleString('en-US', { maximumFractionDigits: maxFrac })

export function estimatePerYear(value: number, currency: string, row: WageCountry): PerYearView {
  const period = row.native.period
  const py = row.native.per_year
  if (period === 'year') return { value, period: 'year', steps: [] }
  if (!py || !py.ok) {
    const why = py && !py.ok && py.reason ? py.reason : 'this file carries no conversion for it'
    return { value, period, steps: [{ op: 'per_year_refused', detail: `Not put on a year: ${why}. Shown per `
      + `${period}, as published.` }] }
  }
  const exact = value * py.factor
  if (py.from === 'hour') {
    const defined = py.hours_kind === 'definition'
    const shown = defined ? exact : Number(exact.toPrecision(3))
    const steps: EstimateStep[] = [
      { op: 'per_year', detail: `${_num(value, 2)} ${currency} an hour × ${py.hours_per_week} hours a week × 52 weeks `
        + `= ${_num(exact, defined ? 2 : 0)} ${currency} a year`
        + (defined
          ? ' — the hours are a definition, not a measurement, so nothing is rounded beyond the unit.'
          : ' — shown to three significant figures, because the hours are measured to three.')
        + ' The multiplying is this site\'s; the office publishes an hourly figure.' },
    ]
    if (py.hours_scope) {
      steps.push({ op: 'hours', detail: `The hours (${py.hours_year}): ${py.hours_scope}`
        + (py.hours_flag ? ` Flagged "${py.hours_flag}" by the source.` : '') })
    }
    return { value: shown, period: 'year', steps }
  }
  if (py.from === 'month') {
    const office = py.office ?? 'The office'
    const steps: EstimateStep[] = [
      { op: 'per_year', detail: `${_num(value, 2)} ${currency} a month × 12 = ${_num(exact, 2)} ${currency} a year. `
        + `Twelve times is this site's arithmetic; ${office} publishes a monthly figure.` },
    ]
    if (!py.counts) {
      steps.push({ op: 'per_year_unknown', detail: `What twelve months of ${office}'s figure include could not be `
        + 'established at the source, so this year may leave out pay the source never measured.' })
      return { value: exact, period: 'year', steps }
    }
    return {
      value: exact, period: 'year', steps,
      concept: {
        name: 'What twelve months of it count',
        office: `${office}${py.checked_at_source ? `, checked at the source on ${py.checked_at_source.slice(0, 10)}` : ''}`,
        includes: py.counts,
        excludes: py.leaves_out ?? undefined,
      },
    }
  }
  return { value, period, steps: [] }
}
