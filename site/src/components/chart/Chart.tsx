/* React's half of the chart kit.
 *
 * React owns the host element and decides WHICH transition a config change
 * deserves; the engine owns the contents and runs it. Keeping the frame loop
 * out of React is what lets a morph hold 60 fps without a render per frame.
 *
 * The draw-in fires once, on first visibility, and is remembered per chart id —
 * so switching theme, re-rendering, or changing the palette redraws the chart
 * without replaying the animation.
 */

import { useEffect, useRef, type MutableRefObject } from 'react'
import { makeChart, type ChartCfg, type ChartHandle } from './engine'

/** Which transition a config change earns.
 *  `morph` — same shape, new values. `fade` — different geometry.
 *  `track` — direct manipulation; same scales, no teardown. */
export type Transition = 'morph' | 'fade' | 'track'

interface Props {
  cfg: ChartCfg
  transition?: Transition
  /** Stable across the chart's life. Draw-in happens once per id, per session. */
  id: string
  /** A table or sentence conveying the same data, for readers who cannot see it. */
  children?: React.ReactNode
  className?: string
  /** The engine, for callers that drive it directly — the rebase handle needs
   *  the live scales to turn a pointer position into a year. Assigned when the
   *  engine exists, which is not the same moment this component mounts. */
  handleRef?: MutableRefObject<ChartHandle | null>
  /** Fired after the first build, when scales exist and can be read. */
  onReady?: () => void
}

const drawn = new Set<string>()

export function Chart({ cfg, transition = 'morph', id, children, className, handleRef, onReady }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const chart = useRef<ChartHandle | null>(null)
  const built = useRef(false)
  const latest = useRef(cfg)
  latest.current = cfg
  const ready = useRef(onReady)
  ready.current = onReady

  // Build on first visibility, so the draw-in happens where it can be seen and
  // charts below the fold cost nothing until they are approached.
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const engine = makeChart(host)
    chart.current = engine
    if (handleRef) handleRef.current = engine

    const first = () => {
      if (built.current) return
      built.current = true
      // noDraw when this chart has already drawn itself once this session.
      engine.build(latest.current, drawn.has(id))
      drawn.add(id)
      ready.current?.()
    }

    const stop = () => {
      engine.destroy()
      if (handleRef) handleRef.current = null
    }

    if (typeof IntersectionObserver !== 'function') {
      first()
      return stop
    }
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue
        first()
        io.disconnect()
      }
    }, { rootMargin: '-40px' })
    io.observe(host)
    return () => { io.disconnect(); stop() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // Config changes after the first build take the transition React chose.
  useEffect(() => {
    const engine = chart.current
    if (!engine || !built.current) return
    if (transition === 'track') engine.updateSeries(cfg)
    else if (transition === 'fade') engine.fade(cfg)
    else engine.morph(cfg)
    // `transition` is how to move, not what to move — a change to it alone
    // should not re-run anything.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg])

  return (
    <div className={className}>
      <div className="chart" ref={hostRef} />
      {children}
    </div>
  )
}

export type { ChartCfg, Series, Pt, Axis, SeriesMode } from './engine'
