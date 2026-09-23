/* Where a source card (<Figure>) or a method card (<Derived>) sits once open
 * — and the theme list, which opens from the footer (Tier 4 of the same
 * package) where it usually has to go up rather than down.
 *
 * Package 46, Tier 1. Both cards were `position: absolute` under their
 * trigger, inside the trigger's own wrapper, so ANY ancestor that hides
 * overflow cut them. /work's estimate column is one: `.wrow-est` clips for
 * its ellipsis, and at desktop widths every source card in that column
 * opened to nothing — 0 of its 141px on screen. A reader clicked "no spread
 * published" and was shown no explanation. Found by the disclosure check
 * (scripts/tests/test_disclosures.mjs), which asks the browser what is
 * painted rather than reasoning about CSS.
 *
 * `position: fixed` escapes every clipping ancestor while the card stays
 * where it is in the DOM. That matters: a portal would move the card to the
 * end of <body>, and Tab from a trigger would no longer land in its own card.
 *
 * What fixed costs is that the card no longer travels with the page, so it
 * is placed from the trigger's rect and re-placed on any scroll (capture, so
 * a scroll inside a scrolling region counts too) and on resize. It opens
 * below the trigger, flips above when there is not room below and there is
 * more above, is kept inside the viewport horizontally, and is capped at the
 * room it has — past which the card scrolls instead of running off screen.
 *
 * The first render is invisible and unplaced so the card can be measured;
 * the layout effect places it before the browser paints, so there is no
 * frame in which it shows in the wrong place.
 */
import { useLayoutEffect, useState, type RefObject } from 'react'

export interface CardPlacement { left: number; top: number; maxHeight: number }

const MARGIN = 8
const GAP = 7

export function useCardPlacement(
  open: boolean,
  trigger: RefObject<HTMLElement | null>,
  card: RefObject<HTMLElement | null>,
  enabled = true,
): CardPlacement | null {
  const [pos, setPos] = useState<CardPlacement | null>(null)

  useLayoutEffect(() => {
    if (!open || !enabled) { setPos(null); return }
    let raf = 0
    const place = () => {
      raf = 0
      const t = trigger.current, c = card.current
      if (!t || !c) return
      const r = t.getBoundingClientRect()
      const vw = window.innerWidth, vh = window.innerHeight
      const w = c.offsetWidth
      const h = c.scrollHeight
      const left = Math.round(Math.max(MARGIN, Math.min(r.left, vw - w - MARGIN)))
      const below = vh - r.bottom - GAP - MARGIN
      const above = r.top - GAP - MARGIN
      let top: number, maxHeight: number
      if (h <= below || below >= above) {
        top = r.bottom + GAP
        maxHeight = Math.max(below, 0)
      } else {
        maxHeight = above
        top = Math.max(MARGIN, r.top - GAP - Math.min(h, above))
      }
      /* Where does (0,0) actually land for this card? The viewport's corner —
       * unless an ancestor carries a transform, filter, perspective or
       * `contain`, in which case `position: fixed` is measured from THAT
       * ancestor instead. Package 46 found every Explore panel holding an
       * identity transform left behind by its entrance animation, which put
       * cards ~100px from their triggers. The animation is fixed; this makes
       * placement right whatever the next ancestor does. (It cannot lift the
       * card out of that ancestor's stacking context — only removing the
       * transform does that, and the disclosure check is what catches it.) */
      const prevL = c.style.left, prevT = c.style.top
      c.style.left = '0px'; c.style.top = '0px'
      const origin = c.getBoundingClientRect()
      c.style.left = prevL; c.style.top = prevT
      const L = Math.round(left - origin.left)
      const T = Math.round(top - origin.top)
      maxHeight = Math.round(maxHeight)
      setPos((p) => (p && p.left === L && p.top === T && p.maxHeight === maxHeight ? p : { left: L, top: T, maxHeight }))
    }
    place()
    const onMove = () => { if (!raf) raf = requestAnimationFrame(place) }
    window.addEventListener('scroll', onMove, { capture: true, passive: true })
    window.addEventListener('resize', onMove)
    return () => {
      if (raf) cancelAnimationFrame(raf)
      window.removeEventListener('scroll', onMove, { capture: true })
      window.removeEventListener('resize', onMove)
    }
  }, [open, enabled, trigger, card])

  return pos
}

/** The style half, shared so the two cards cannot drift apart. */
export function placedCardStyle(pos: CardPlacement | null) {
  return {
    position: 'fixed' as const,
    left: pos?.left ?? 0,
    top: pos?.top ?? 0,
    maxHeight: pos ? pos.maxHeight : undefined,
    overflowY: 'auto' as const,
    visibility: pos ? ('visible' as const) : ('hidden' as const),
    /* No transitions, visibility least of all. Under prefers-reduced-motion
     * tokens.css gives EVERY property a 0.01ms transition, and visibility is
     * animatable: for that sliver the card still computed as hidden, so the
     * focus() that moves a keyboard reader into a <Derived> card silently
     * did nothing — with motion on it worked, with it off it did not
     * (package 46, adversarial review; traced by timing the mutations). A
     * card is placed before it is painted, so it has nothing to animate. */
    transitionProperty: 'none' as const,
  }
}
