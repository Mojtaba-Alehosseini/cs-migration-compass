/* The segmented control — one of them, for the whole site.
 *
 * Package 43, judgement call J1. This lived in components/explore/Controls.tsx
 * and Explore was the only screen that used it. Everywhere else asking "pick
 * one of these" grew its own: Compare hand-rolled a <div className="seg"> with
 * bare buttons, /city/* had a local tabStyle() with a green fill and square
 * corners, /openings styled its List/Map pair as two chips. The same question —
 * WHICH EXPERIENCE BAND? — was asked on Compare and on a city page in two
 * visibly different controls.
 *
 * Moved here so a route can use it without importing Explore's bundle, and
 * given the one capability the hand-rolled versions had that this did not: an
 * option can be disabled with its own reason. A city with no senior figure
 * must still SHOW that the band exists and say why it is unavailable —
 * dropping the option would be quieter and less honest.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'


interface SegProps<T extends string> {
  options: [T, string][]
  value: T
  onChange: (v: T) => void
  label: string
  /** Options a reader can see but not choose, each with the reason. */
  disabled?: Partial<Record<T, string>>
}

/** The thumb slides between options; buttons act on pointer-down, so the
 *  control has already responded by the time a finger lifts. */
export function Seg<T extends string>({ options, value, onChange, label, disabled }: SegProps<T>) {
  const el = useRef<HTMLDivElement>(null)
  const [thumb, setThumb] = useState<{ left: number; width: number } | null>(null)

  const place = useCallback(() => {
    const root = el.current
    const on = root?.querySelector<HTMLButtonElement>('[aria-pressed="true"]')
    if (on) setThumb({ left: on.offsetLeft, width: on.offsetWidth })
  }, [])

  useLayoutEffect(place, [place, value])
  useEffect(() => {
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  }, [place])

  /* onPointerDown AND onClick, with a guard so a real press does not fire both.
   *
   * Pointer-down alone is faster — the control has already responded by the
   * time a finger lifts — but a synthesized click has no pointer events before
   * it, and that is exactly how a screen reader activates a button, and how
   * element.click() works. This component inherited pointer-down-only from
   * Explore, where it had been for nineteen packages; the moment it took over
   * /compare, /city/* and /openings, it took three controls that had worked on
   * click and made them unreachable that way. The figure inventory caught it:
   * st-openings-map contributed 0 marks against a floor of 1, because the
   * state's own setup clicks the control and nothing happened. */
  const lastPointer = useRef(0)
  const choose = (k: T, why: string | undefined, viaPointer: boolean) => {
    if (why != null) return
    // A timestamp, not a flag. A flag that is only cleared by the click it is
    // waiting for stays set forever if that click never arrives — press a
    // button, drag off it, release — and then swallows the NEXT synthesized
    // click, which is the screen reader's. A real click follows its own
    // pointerdown within a few hundred milliseconds; nothing else does.
    if (viaPointer) lastPointer.current = Date.now()
    else if (Date.now() - lastPointer.current < 700) return
    if (k !== value) onChange(k)
  }

  return (
    <div className="seg" ref={el} role="group" aria-label={label}>
      {thumb && <span className="thumb" aria-hidden="true" style={{ left: thumb.left, width: thumb.width }} />}
      {options.map(([k, l]) => {
        const why = disabled?.[k]
        return (
          <button
            key={k}
            type="button"
            aria-pressed={k === value}
            disabled={why != null}
            title={why}
            onPointerDown={() => choose(k, why, true)}
            onClick={() => choose(k, why, false)}
            onKeyDown={(e) => {
              // Through choose() like the other two, so the keyboard cannot be
              // the one path that re-selects the option already selected —
              // onChange writes the URL on /compare, and setting a value to
              // itself is a history entry for nothing.
              // preventDefault stops the browser's own click for Enter/Space,
              // so this path cannot double-fire with onClick above.
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(k, why, false) }
            }}
          >
            {l}
          </button>
        )
      })}
    </div>
  )
}
