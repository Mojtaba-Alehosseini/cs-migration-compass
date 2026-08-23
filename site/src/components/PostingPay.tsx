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

/** Can this posting be shown in `want`? Native always can. */
export function canShowIn(c: Compensation, want: DisplayCurrency): boolean {
  if (want === 'native' || want === c.currency) return true
  return Boolean(c.usd)          // everything else routes through USD
}

interface Props {
  comp: Compensation | null
  display: DisplayCurrency
  /** Cross-rates for display currencies other than USD, keyed by code. Absent
   *  means only native and USD are offered, which is the honest fallback: the
   *  site will not invent a EUR figure it cannot source a rate for. */
  crossRates?: Record<string, number>
}

export function PostingPay({ comp, display, crossRates }: Props) {
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

  const rate = display === 'USD' ? 1 : crossRates?.[display]
  if (!rate) {
    return (
      <span className="tnum">
        {native}{' '}
        <span className="nodata" style={{ fontSize: 'var(--text-2xs)' }}>(no {display} rate)</span>
      </span>
    )
  }

  const lo = usd.min * rate
  const hi = usd.max * rate
  const estimated = Boolean(usd.estimated)

  const chain = [
    { op: 'advertised', detail: `${native} — the employer's own figure, unchanged` },
    {
      op: 'fx_convert',
      detail: estimated
        ? `${comp.currency} → USD at the ${usd.fx_year} rate of ${usd.fx_rate}. `
          + `No ${usd.fx_year_requested} rate is published yet, so the ${usd.fx_year} rate was `
          + `used — a gap of ${usd.fx_gap_years} year${usd.fx_gap_years === 1 ? '' : 's'}. `
          + `This makes the converted figure an ESTIMATE; the figure above it, in `
          + `${comp.currency}, is exact.`
        : `${comp.currency} → USD at the ${usd.fx_year} rate of ${usd.fx_rate} — the rate for `
          + `this posting's own year.`,
    },
    ...(display === 'USD' ? [] : [{
      op: 'fx_convert',
      detail: `USD → ${display} at ${rate}.`,
    }]),
  ]

  return (
    <Derived
      chain={chain}
      native={{ value: comp.min, currency: comp.currency, period: comp.period,
                year: usd.fx_year_requested ?? usd.fx_year }}
      result={{ value: (lo + hi) / 2, currency: display }}
    >
      <span className="tnum">
        {fmtRange(lo, hi, display, comp.period)}
        {estimated && (
          <sup
            className="fx-estimate"
            aria-label={`Estimated: converted at the ${usd.fx_year} rate because no `
              + `${usd.fx_year_requested} rate is published yet`}
            title={`Converted at the ${usd.fx_year} rate — no ${usd.fx_year_requested} rate `
              + `is published yet`}
          >≈</sup>
        )}
      </span>
    </Derived>
  )
}
