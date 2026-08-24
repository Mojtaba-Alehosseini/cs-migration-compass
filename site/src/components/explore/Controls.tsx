/* Explore's control vocabulary: one segment and one picker per chart, never
 * more. A chart that grows a third control has stopped being an instrument and
 * started being a dashboard.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { Flag } from '../Flag'
import { useCountUp } from '../CountUp'
import { useToast } from '../Toast'
import { downloadCsv } from '../../lib/export'

/* ------------------------------------------------------- segmented control */

interface SegProps<T extends string> {
  options: [T, string][]
  value: T
  onChange: (v: T) => void
  label: string
}

/** The thumb slides between options; buttons act on pointer-down, so the
 *  control has already responded by the time a finger lifts. */
export function Seg<T extends string>({ options, value, onChange, label }: SegProps<T>) {
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

  return (
    <div className="seg" ref={el} role="group" aria-label={label}>
      {thumb && <span className="thumb" aria-hidden="true" style={{ left: thumb.left, width: thumb.width }} />}
      {options.map(([k, l]) => (
        <button
          key={k}
          type="button"
          aria-pressed={k === value}
          onPointerDown={() => { if (k !== value) onChange(k) }}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onChange(k) } }}
        >
          {l}
        </button>
      ))}
    </div>
  )
}

/* ---------------------------------------------------------- series picker */

export interface PickItem {
  k: string
  /** Country code for the flag; omit for a non-country series. */
  cc?: string
  label: string
}

interface PickerProps {
  items: PickItem[]
  active: string[]
  /** Takes an updater, not a value: two taps inside one frame must both land,
   *  and a value computed from a stale render would silently drop one. */
  onChange: (update: (cur: string[]) => string[]) => void
  cap?: number
  label: string
}

/** Flag chips. Capped, and never emptied — a chart with no series is not a
 *  state anyone asked for. */
export function Picker({ items, active, onChange, cap = 6, label }: PickerProps) {
  const toast = useToast()
  return (
    <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap' }} role="group" aria-label={label}>
      {items.map((it) => {
        const on = active.includes(it.k)
        return (
          <button
            key={it.k}
            type="button"
            className="pick"
            aria-pressed={on}
            onClick={() => {
              if (on) {
                if (active.length <= 1) { toast('Keep at least one'); return }
                onChange((cur) => (cur.length <= 1 ? cur : cur.filter((k) => k !== it.k)))
              } else {
                if (active.length >= cap) { toast(`${cap} series is the cap — remove one first`); return }
                onChange((cur) => (cur.includes(it.k) || cur.length >= cap ? cur : [...cur, it.k]))
              }
            }}
          >
            {it.cc && <Flag cc={it.cc} size={12} />}
            {it.label}
          </button>
        )
      })}
    </span>
  )
}

/* ----------------------------------------------------------------- hero */

export interface HeroStat {
  value: number | null
  format: (v: number) => string
  label: string
  source: string
}

function Stat({ stat }: { stat: HeroStat }) {
  const v = useCountUp(stat.value, 900)
  return (
    <div className="hstat">
      <div className="v tnum">{v == null ? '—' : stat.format(v)}</div>
      <div className="l">{stat.label}</div>
      <div className="s">{stat.source}</div>
    </div>
  )
}

/** Three numbers computed from the data, never written by hand. */
export function Hero({ stats }: { stats: HeroStat[] }) {
  return (
    <div className="hero">
      {stats.map((s, i) => <Stat key={`${s.label}-${i}`} stat={s} />)}
    </div>
  )
}

/* ------------------------------------------------------------ chart chrome */

/** The footer every chart carries: confidence, the caveat, and the data itself. */
export function ChartFoot({ children, csv }: {
  children: ReactNode
  csv?: { name: string; rows: Record<string, unknown>[] }
}) {
  const toast = useToast()
  return (
    <div className="cfoot">
      {children}
      {csv && (
        <button className="csv" onClick={() => {
          downloadCsv(csv.name, csv.rows)
          toast('CSV saved — empty cells mean no data, never zero')
        }}>⤓ CSV</button>
      )}
    </div>
  )
}

/** A chart's numbers as a table, for anyone who cannot read the drawing.
 *  In the DOM and reachable — not behind a control a screen reader must find. */
export function ChartTable({ caption, head, rows }: {
  caption: string
  head: string[]
  rows: (string | number | null)[][]
}) {
  return (
    <details className="chart-table">
      <summary>{caption}</summary>
      <table>
        <thead><tr>{head.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{r.map((c, j) => <td key={j}>{c ?? 'no data'}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

/** A hole in the data, with its reason and where it is tracked. Never a blank
 *  panel: a visitor cannot tell a deliberate absence from a broken pipeline. */
export function Gap({ title, children, where, span = 's2', level = 3 }: {
  title: string
  children: ReactNode
  where?: ReactNode
  span?: string
  /** Heading level for this gap's title. Default 3, which is right when a Gap
   *  sits directly under a panel's <h2>. On /work a Gap sits INSIDE a country
   *  section's <h4> column, where an <h3> reads to a screen reader navigating
   *  by heading as the start of a new top-level section rather than a note
   *  about the column it is in — Italy rendered h3, h4, h3, h4 down one
   *  section. axe does not flag a level DECREASE, so nothing caught it.
   *  Adversarial review, package 17. */
  level?: 3 | 4 | 5
}) {
  const H = `h${level}` as 'h3' | 'h4' | 'h5'
  return (
    <div className={`gap ${span}`}>
      <H>{title}</H>
      {children}
      {where && <div className="where">{where}</div>}
    </div>
  )
}

/* --------------------------------------------------------------- loading */

/** Panels reserve the height they will occupy, so arriving data does not shove
 *  the page — the layout shift that cost Explore its performance score. */
export function ChartSkeleton({ height }: { height: number }) {
  return <div style={{ height, display: 'grid', placeItems: 'center' }} aria-busy="true">
    <span className="kicker">Loading…</span>
  </div>
}

/** A theme's loading state holds the SHAPE of the theme, not one placeholder
 *  panel. Standing in with a single panel and then expanding to three moves
 *  every row below it — measured at 289 px of shift on Money and Homes, which
 *  is most of what those routes lost on Lighthouse.
 *
 *  The numbers are the loaded panels' own measured heights; PANEL_CHROME is the
 *  padding and border this component adds around the reserved box, so the
 *  placeholder ends up exactly the size of the thing it stands in for. */
const PANEL_CHROME = 34

/** The space a chart will occupy, reserved exactly: its SVG is
 *  `width: 100%; height: auto` over a fixed viewBox, so the same aspect ratio
 *  reserves the same height at any viewport width.
 *
 *  Reserving the chart alone is not enough for a panel whose picker only learns
 *  its chips from the data — those wrap to a second row and move everything
 *  below. Panels like that reserve their whole height through ThemeSkeleton
 *  instead; this is for the ones whose chrome is fixed. */
export function ChartPlaceholder({ w = 940, h = 270 }: { w?: number; h?: number }) {
  return <div className="chart" style={{ aspectRatio: `${w} / ${h}` }} aria-busy="true" />
}

export function ThemeSkeleton({ panels }: { panels: [string, number][] }) {
  return (
    <>
      {panels.map(([span, panelHeight], i) => (
        <div key={i} className={`panel ${span}`}>
          <ChartSkeleton height={panelHeight - PANEL_CHROME} />
        </div>
      ))}
    </>
  )
}
