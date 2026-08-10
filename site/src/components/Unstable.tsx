/* The marker for a figure that is smaller than its own error bars.
 *
 * One rule, one marker, every surface. The number is never suppressed — we do
 * not hide numbers, we name what is wrong with them — so this sits beside the
 * figure in the warning language the rest of the site already uses, at the same
 * weight as any other caveat rather than as an alarm.
 *
 * The rule itself lives in compute.ts; this only draws it.
 */

import { stabilityOf, instabilityNote } from '../data/compute'
import type { Band, City } from '../data/types'
import type { Budget } from '../data/compute'

/** A small "≈" beside the figure: this is an order of magnitude, not a count. */
export function UnstableMark({ city, band, budget }: { city: City; band: Band; budget?: Budget }) {
  if (stabilityOf(city, band, budget) !== 'unstable') return null
  return (
    <span
      className="unstable-mark"
      role="img"
      aria-label="Rounding-limited: this figure is smaller than the rounding on its own inputs"
      title="Smaller than the rounding on its own inputs — read it as “effectively out of reach”"
    >≈</span>
  )
}

/** The plain-words line, for a source card or a footnote. */
export function useInstabilityNote(city: City, band: Band, budget?: Budget): string | null {
  return instabilityNote(city, band, budget)
}
