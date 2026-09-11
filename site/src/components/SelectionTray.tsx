/* The selection tray: what you have picked, docked to the bottom of the page.
 *
 * ONE of these, used by Compare and by Home. It was two — Compare's
 * `SelectionTray` against the `.tray` class, and Home's own inline rebuild of
 * the same slab — and the cost of that is on the record: when package 43 fixed
 * the tray's contrast (--ink-3 is text-on-paper and this slab is --ink-1, so
 * the city names measured 1.64:1 in light and 1.28:1 in dark), the fix landed
 * on the class and could not reach Home, which kept rendering the identical
 * defect at 3.52:1 and 2.76:1. It was found by an instrument, after an
 * adversarial review, after the fix had already shipped.
 *
 * What varies between the two pages is the CONTENT, so that is what the props
 * carry: the word for a place, the mark inside each chip (Compare wears the
 * country's flag, Home wears the selection colour that keys its charts), and
 * the actions, which are the page's own and arrive as children. What does NOT
 * vary — the slab, the count, the chip, the slide-in, the inverted text
 * colours — belongs to `.tray` in base.css and is written once.
 */
import type { ReactNode } from 'react'

export interface TrayCity { id: string; name: string }

export function SelectionTray({ cities, noun = ['place', 'places'], mark, onRemove, children }: {
  cities: TrayCity[]
  /** Singular and plural. Compare counts "places", Home counts "cities". */
  noun?: [string, string]
  /** What sits inside each chip before the name. */
  mark?: (city: TrayCity, index: number) => ReactNode
  /** Given, each chip gets a remove button. Home's tray has none by design. */
  onRemove?: (id: string) => void
  /** The page's own actions. */
  children?: ReactNode
}) {
  /* `.show` rather than unmounting: the tray SLIDES, and an element that is
     not in the DOM cannot animate into it. base.css flips `visibility` with
     it so the buttons of an empty tray stay out of the tab order and out of
     the accessibility tree — being off-screen is not being hidden. */
  return (
    <div className={`tray${cities.length ? ' show' : ''}`} aria-live="polite">
      <span className="cnt">{cities.length} {cities.length === 1 ? noun[0] : noun[1]}</span>
      <div className="chips">
        {cities.map((c, i) => (
          <span key={c.id} className="tchip">
            {mark?.(c, i)}
            {c.name}
            {onRemove && (
              <button onClick={() => onRemove(c.id)} aria-label={`Remove ${c.name}`}>✕</button>
            )}
          </span>
        ))}
      </div>
      {children}
    </div>
  )
}
