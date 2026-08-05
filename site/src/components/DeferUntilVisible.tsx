/* Render a heavy panel only once it is near the viewport.
 *
 * Explore stacks three chart-heavy panels, and mounting all of them on load
 * costs about half a second of blocked main thread for charts nobody has
 * scrolled to yet. This defers the work without deferring the layout: the
 * placeholder reserves the panel's height, so nothing jumps when the real
 * content swaps in.
 *
 * Falls back to rendering immediately where IntersectionObserver is missing,
 * which is the correct failure direction — slower, never blank.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Height held open while waiting. Match the real panel to avoid a shift. */
  minHeight: number
  /** Start rendering this far before the panel scrolls into view. */
  rootMargin?: string
  label?: string
}

export function DeferUntilVisible({ children, minHeight, rootMargin = '300px', label }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [show, setShow] = useState(() => typeof IntersectionObserver === 'undefined')

  useEffect(() => {
    if (show) return
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShow(true)
          io.disconnect()
        }
      },
      { rootMargin },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [show, rootMargin])

  return (
    <div ref={ref} style={{ minHeight: show ? undefined : minHeight }}>
      {show ? children : (
        <div className="panel" style={{ height: minHeight, display: 'flex', alignItems: 'center' }} aria-busy="true">
          <span className="kicker">{label ?? 'Loading…'}</span>
        </div>
      )}
    </div>
  )
}
