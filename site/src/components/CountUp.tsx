/* Number count-up.
 *
 * Motion discipline: this is the one decorative-ish effect on the home screen,
 * and it exists because the numbers ARE the hero. It respects
 * prefers-reduced-motion by rendering the final value immediately, and it never
 * blocks input — it is pure render state, no layout thrash. */

import { useEffect, useRef, useState } from 'react'

const prefersReduced = () =>
  typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

export function useCountUp(target: number | null, duration = 700): number | null {
  const [value, setValue] = useState<number | null>(target)
  const fromRef = useRef<number>(target ?? 0)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    if (target == null) { setValue(null); return }
    if (prefersReduced()) { setValue(target); fromRef.current = target; return }

    const from = fromRef.current
    const delta = target - from
    if (delta === 0) { setValue(target); return }

    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      // easeOutCubic — settles rather than stopping dead
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(from + delta * eased)
      if (t < 1) rafRef.current = requestAnimationFrame(tick)
      else fromRef.current = target
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [target, duration])

  return value
}

interface Props {
  value: number | null
  format: (v: number | null) => string
  duration?: number
}

export function CountUp({ value, format, duration }: Props) {
  const animated = useCountUp(value, duration)
  return <span className="tnum">{format(animated)}</span>
}
