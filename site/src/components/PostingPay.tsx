/* The one way a job posting's pay is rendered.
 *
 * NATIVE IS THE SOURCE OF TRUTH AND THE DEFAULT. A salary advertised in pounds
 * is exact in pounds and needs no exchange rate at all. Until package 17 the
 * site converted everything to USD and a posting whose currency had no
 * same-year rate simply lost its figure — 88-92% of the annual-pay
 * advertisements for GB, CA, DE and FR, almost all of them dated this year.
 * That is now impossible by construction: this component renders the native
 * range first and never has a code path that withholds it.
 *
 * A CONVERTED FIGURE IS A <Derived>, NOT A <Figure>. docs/DESIGN.md is explicit:
 * <Figure> is for a number an office published, <Derived> for one this site
 * calculated. A currency conversion is a calculation, so the converted view
 * carries an ordered method — the native figure, the rate, the year the rate
 * came from — rather than a source chip. That is also where the ESTIMATE lives:
 * where no same-year rate exists the site reaches up to
 * normalise.MAX_FX_GAP_YEARS (2) and the method card says which year it used
 * and why. There is no separate "estimate component" because there does not
 * need to be one; the honest place for "this used the 2025 rate" is the method.
 *
 * The visible marker is a small superscript on the figure itself, in the same
 * register as the instability "≈" — it marks the NUMBER, not a footnote
 * somewhere else on the page, and it resolves on tap like everything else.
 */

import { Derived } from './Derived'
import type { Compensation } from '../data/postings'

/** Currencies the site can convert into. `native` is not a currency — it is the
 *  instruction to leave every figure in whatever the employer advertised. */
export const DISPLAY_CURRENCIES = ['native', 'USD', 'EUR', 'GBP', 'CAD', 'AUD'] as const
export type DisplayCurrency = (typeof DISPLAY_CURRENCIES)[number]

export const DISPLAY_CURRENCY_LABEL: Record<DisplayCurrency, string> = {
  native: 'As advertised',
  USD: 'US dollars',
  EUR: 'Euros',
  GBP: 'Pounds',
  CAD: 'Canadian dollars',
  AUD: 'Australian dollars',
}

const PERIOD: Record<Compensation['period'], string> = { year: '/yr', month: '/mo', hour: '/hr' }

function money(v: number, currency: string): string {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency, maximumFractionDigits: 0,
      notation: v >= 10_000 ? 'compact' : 'standard',
    }).format(v)
  } catch {
    // An unmapped currency code still renders — as the number and the code,
    // never as nothing. This is the path a currency with no rate at all takes.
    return `${Math.round(v).toLocaleString()} ${currency}`
  }
}

export function fmtRange(min: number, max: number, currency: string, period: Compensation['period']) {
  return min === max
    ? `${money(min, currency)}${PERIOD[period]}`
    : `${money(min, currency)}–${money(max, currency)}${PERIOD[period]}`
}

/** One display currency's whole rate series, as `display_fx.rates[code]` ships
 *  it. The series — not one rate — because a posting is converted at the rate
 *  for ITS OWN year. */
export interface CrossRate {
  rate: number
  year: number
  by_year: Record<string, number>
}

/** The client half of `normalise.fx_rate_within`, and deliberately the same
 *  rule: exact year if there is one, otherwise the nearest within `maxGap`,
 *  preferring the past on a tie, and never silently exact when it reached.
 *
 *  This exists because the USD→display leg is a conversion like any other. The
 *  first version of this component applied one 2025 rate to every posting
 *  whatever its year, which put a 2016 listing 15.4% out at a nine-year gap
 *  with no marker — the exact failure the native→USD leg was rebuilt to
 *  prevent, reintroduced one line below it. */
function rateWithin(series: Record<string, number> | undefined, year: number, maxGap: number) {
  if (!series) return null
  const exact = series[String(year)]
  if (exact != null) return { rate: exact, year, gap: 0, estimated: false }
  if (maxGap <= 0) return null
  let best: { rate: number; year: number; gap: number } | null = null
  for (const [ys, r] of Object.entries(series)) {
    const y = Number(ys)
    const gap = Math.abs(y - year)
    if (gap > maxGap) continue
    if (!best || gap < best.gap || (gap === best.gap && y < best.year)) best = { rate: r, year: y, gap }
  }
  return best ? { ...best, estimated: true } : null
}

interface Props {
  comp: Compensation | null
  display: DisplayCurrency
  /** Cross-rate series for display currencies other than USD, keyed by code.
   *  Absent means only native and USD are offered, which is the honest
   *  fallback: the site will not invent a EUR figure it cannot source a rate
   *  for, and will not reach across a decade to find one. */
  crossRates?: Record<string, CrossRate>
  /** How far the USD→display leg may reach for a rate. Ships in the payload as
   *  `display_fx.max_gap_years` so the client cannot drift from the server's
   *  ceiling; the default is the strict one, not the generous one. */
  maxGapYears?: number
}

export function PostingPay({ comp, display, crossRates, maxGapYears = 0 }: Props) {
  if (!comp) return <span className="nodata">not stated</span>

  const native = fmtRange(comp.min, comp.max, comp.currency, comp.period)

  // Native, or a posting already advertised in the requested currency: no
  // calculation happened, so this is a plain figure with no method to show.
  if (display === 'native' || display === comp.currency) {
    return <span className="tnum">{native}</span>
  }

  const usd = comp.usd
  if (!usd) {
    // No rate at all for this currency. The native figure still renders — that
    // is the whole point — with a quiet note rather than a blank cell.
    return (
      <span className="tnum">
        {native}{' '}
        <span className="nodata" style={{ fontSize: 'var(--text-2xs)' }}>
          (no {display} rate for {comp.currency})
        </span>
      </span>
    )
  }

  // The posting's own year is what BOTH legs are matched against.
  const wantYear = usd.fx_year_requested ?? usd.fx_year
  const cross = display === 'USD'
    ? { rate: 1, year: wantYear, gap: 0, estimated: false }
    : rateWithin(crossRates?.[display]?.by_year, wantYear, maxGapYears)

  if (!cross) {
    // No rate for this currency within reach of this posting's year. The native
    // figure still renders; what is refused is the invented one.
    return (
      <span className="tnum">
        {native}{' '}
        <span className="nodata" style={{ fontSize: 'var(--text-2xs)' }}>
          (no {display} rate for {wantYear})
        </span>
      </span>
    )
  }

  const lo = usd.min * cross.rate
  const hi = usd.max * cross.rate
  const estimated = Boolean(usd.estimated) || cross.estimated

  const reached = [
    usd.estimated ? `${comp.currency}→USD at the ${usd.fx_year} rate` : null,
    cross.estimated ? `USD→${display} at the ${cross.year} rate` : null,
  ].filter(Boolean).join(' and ')

  const chain = [
    {
      op: 'advertised',
      detail: comp.min === comp.max
        ? `${native} — the employer's own figure, unchanged`
        : `${native} — the employer's own figure, unchanged. The steps below trace the `
          + `bottom of that range; the top converts the same way.`,
    },
    // A USD-advertised posting has no first leg. Rendering "USD → USD at the
    // 2016 rate of 1 — the rate for this posting's own year" is a step that
    // describes nothing, and a method chain with a no-op step in it teaches the
    // reader to skim the steps.
    ...(comp.currency === 'USD' ? [] : [{
      op: 'fx_convert',
      detail: usd.estimated
        ? `${comp.currency} → USD at the ${usd.fx_year} rate of ${usd.fx_rate}. `
          + `No ${usd.fx_year_requested} rate is published yet, so the ${usd.fx_year} rate was `
          + `used — a gap of ${usd.fx_gap_years} year${usd.fx_gap_years === 1 ? '' : 's'}. `
          + `This makes the converted figure an ESTIMATE; the figure above it, in `
          + `${comp.currency}, is exact.`
        : `${comp.currency} → USD at the ${usd.fx_year} rate of ${usd.fx_rate} — the rate for `
          + `this posting's own year.`,
    }]),
    ...(display === 'USD' ? [] : [{
      op: 'fx_convert',
      detail: cross.estimated
        ? `USD → ${display} at the ${cross.year} rate of ${cross.rate}. No ${wantYear} rate is `
          + `published, so the ${cross.year} rate was used — a gap of ${cross.gap} `
          + `year${cross.gap === 1 ? '' : 's'}. A second conversion is a conversion: it reaches `
          + `no further than the first is allowed to, and it says so when it reaches.`
        : `USD → ${display} at the ${cross.year} rate of ${cross.rate} — the rate for this `
          + `posting's own year.`,
    }]),
  ]

  return (
    <Derived
      chain={chain}
      native={{ value: comp.min, currency: comp.currency, period: comp.period, year: wantYear }}
      result={{ value: lo, currency: display }}
    >
      <span className="tnum">
        {fmtRange(lo, hi, display, comp.period)}
        {estimated && (
          <sup
            className="fx-estimate"
            aria-label={`Estimated: no ${wantYear} rate is published, so this was converted `
              + `${reached}`}
            title={`Converted ${reached} — no ${wantYear} rate is published`}
          >≈</sup>
        )}
      </span>
    </Derived>
  )
}
