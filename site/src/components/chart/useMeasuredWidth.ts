/* How wide was this actually drawn?
 *
 * SwarmField has asked that question since it was built — it packs dots into
 * lanes and needs real pixels to do it. NEEDS-DECISION #84 needs the same
 * number in the two SVG plots, for a different reason: to work out what a
 * font-size written in user units becomes on the glass. Extracted here rather
 * than copied a third time, so the site has one width mechanism.
 *
 * `clientWidth`, not `getBoundingClientRect().width`, deliberately: it is what
 * SwarmField measured before this file existed, so moving it here moves no
 * dots. It is an integer, which on a 720-unit viewBox is a scale error under
 * 0.2% — four hundredths of a pixel on a 12px floor.
 *
 * A CALLBACK ref, not a ref object read in an effect (package 46). The effect
 * ran once, on mount, and SwarmField does not always render the element on
 * mount: land on Home at ?ask=stay and it draws country bars instead, so the
 * effect found no element and never looked again. Switching to a swarm
 * question then drew the field at the fallback width forever — 1000px on a
 * 390px phone, which is how that question pushed the page off the screen.
 * A callback ref is called whenever the element appears or goes, so the
 * observer follows the element rather than the first render.
 */
import { useCallback, useRef, useState } from 'react'

export function useMeasuredWidth<T extends HTMLElement>(fallback: number) {
  const [width, setWidth] = useState(fallback)
  const observer = useRef<ResizeObserver | null>(null)

  const ref = useCallback((el: T | null) => {
    observer.current?.disconnect()
    observer.current = null
    if (!el) return
    // Read once whether or not ResizeObserver exists: SwarmField's fallback
    // is 0 (it draws nothing until measured), so a browser without one must
    // still get a width rather than an empty field. Called during commit,
    // like a layout effect, so the corrected render lands before paint.
    setWidth(el.clientWidth || fallback)
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth || fallback))
    ro.observe(el)
    observer.current = ro
  }, [fallback])

  return [ref, width] as const
}

/* #84, the rule: `userUnits = max(declared, 12 / scale)`.
 *
 * A plot draws into a fixed viewBox at `width: 100%; height: auto`, so text
 * inside it is in user units and the browser multiplies it by
 * (rendered width / viewBox width) before painting. A declared 12 is 16.3px on
 * a 1440 desktop and 5.1px on a 390 phone. The same declaration, a third of the
 * size, on the screen least able to spare it.
 *
 * Returned as a multiplier because `--text-2xs` IS the site's floor (12px, and
 * tokens.css says so), which makes `max(12, 12/s)` exactly `12 * max(1, 1/s)`.
 * Expressing it this way keeps the token as the single source of the number and
 * keeps the arithmetic out of CSS.
 *
 * Above scale 1 it returns exactly 1, so every desktop width is untouched — not
 * approximately untouched. That is the property the screenshot diff checks.
 */
export function textBoost(width: number, viewBoxWidth: number) {
  const scale = width / viewBoxWidth
  return scale > 0 && scale < 1 ? 1 / scale : 1
}
