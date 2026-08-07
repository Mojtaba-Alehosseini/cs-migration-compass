/* The flag-dot field — the centrepiece.
 *
 * Every city is a dot wearing its country's flag, placed by its real value on
 * whichever plain question is active. Three render modes share one component
 * because they are one idea seen three ways:
 *
 *   swarm    one axis, collision-packed into lanes, labels auto-hiding
 *   scatter  the same dots gaining a second axis (the approved presets)
 *   country  PR/citizenship as two-stage bars, where dots would say nothing
 *
 * Scatter is a first-class state, not a swarm with the dots nudged upwards: it
 * builds a real y-axis (ticks, values, a plain-words title), drops the
 * swarm-only furniture, re-collides the labels in two dimensions, and sends any
 * city missing EITHER value to the gutter. A dot whose height means nothing is
 * worse than no second axis at all.
 *
 * Cities with no value are never dropped. They park in a "no data" gutter at
 * the edge, which is the whole point of the Oslo sunshine case.
 *
 * Positions are applied as transforms rather than left/top so the swarm→scatter
 * morph is a single compositor-friendly property, and so reduced motion turns it
 * into an instant state change through the duration tokens.
 */

import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Flag, FlagRibbon } from './Flag'
import type { City, Country } from '../data/types'
import type { Question, SecondAxis } from '../data/questions'
import { ANCHORS, pickColor } from '../data/questions'

const LANE_ORDER = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7]
const LANE_H = 32
const MIN_GAP = 19       // px between dots in the same lane
const CROWD_GAP = 34     // px within which a label is hidden
const FIELD_H = 440
const BAR_ROW_H = 29
const GUTTER_X = 87       // swarm ends here when the no-data gutter is showing

/* Scatter insets. The left column carries the y tick values; the top strip
   carries the y-axis title; the bottom band is the one the x tick labels
   already live in. Swarm keeps its full-bleed field, so none of this applies. */
const Y_AXIS_W = 54
const Y_AXIS_W_NARROW = 38
const NARROW = 560
const PLOT_TOP = 22
const PLOT_BOTTOM = 26
const SWARM_TICK_BOTTOM = 18
/* The gutter box is 64px wide with a 6px margin; a dot is 25px wide, so the
   plot has to stop 84px short of the edge for the rightmost mark to clear it. */
const GUTTER_RESERVE = 84

export interface Placed {
  city: City
  value: number
  /** The second-axis value, when a second axis is active. */
  y: number | null
  x: number          // 0-100 on the question's own scale; the plot maps it to px
  lane: number
  crowded: boolean
  labUp: boolean
  capped: boolean
}

interface Props {
  cities: City[]
  countryOf: (c: City) => Country | undefined
  question: Question
  secondAxis: SecondAxis | null
  selected: string[]
  onToggle: (id: string) => void
  intro: boolean
}

interface Box { l: number; r: number; t: number; b: number }

const overlaps = (a: Box, b: Box) => a.l < b.r && b.l < a.r && a.t < b.b && b.t < a.b

/* Label collision in two dimensions.
 *
 * The swarm can pack labels by lane because everything shares one row grid.
 * A scatter has no lanes, so labels are placed greedily: anchors first (they are
 * the fixed reference points a reader orients by and always win), then the rest
 * left to right. Each label tries below its dot, then above; if neither box is
 * free of another label or another dot's mark, it is hidden — hover, focus and
 * selection still bring it back, exactly as in the swarm. */
function collide2D(
  items: { id: string; name: string; x: number; y: number; anchor: boolean }[],
  reserved: Box[] = [],
): Map<string, { show: boolean; up: boolean }> {
  const MARK = 11        // half the flag mark's box
  const LAB_H = 12
  const LAB_DY = 16      // label centre, relative to the dot centre
  const halfWidth = (name: string) => (name.length * 5.1 + 8) / 2

  const marks: Box[] = items.map((i) => ({ l: i.x - MARK, r: i.x + MARK, t: i.y - MARK, b: i.y + MARK }))
  // The no-data gutter is furniture, not a dot, so nothing may be written under it.
  const taken: Box[] = [...reserved]
  const out = new Map<string, { show: boolean; up: boolean }>()

  const order = items
    .map((item, index) => ({ item, index }))
    .sort((a, b) =>
      a.item.anchor === b.item.anchor ? a.item.x - b.item.x : a.item.anchor ? -1 : 1,
    )

  const free = (box: Box, self: number) =>
    !taken.some((t) => overlaps(t, box)) &&
    !marks.some((m, j) => j !== self && overlaps(box, m))

  for (const { item, index } of order) {
    const w = halfWidth(item.name)
    const below: Box = { l: item.x - w, r: item.x + w, t: item.y + LAB_DY - LAB_H / 2, b: item.y + LAB_DY + LAB_H / 2 }
    const above: Box = { l: item.x - w, r: item.x + w, t: item.y - LAB_DY - LAB_H / 2, b: item.y - LAB_DY + LAB_H / 2 }

    if (free(below, index)) {
      taken.push(below)
      out.set(item.id, { show: true, up: false })
    } else if (free(above, index)) {
      taken.push(above)
      out.set(item.id, { show: true, up: true })
    } else if (item.anchor) {
      // Anchors are never hidden; they take the box that collides least badly.
      taken.push(below)
      out.set(item.id, { show: true, up: false })
    } else {
      out.set(item.id, { show: false, up: false })
    }
  }
  return out
}

export function SwarmField({
  cities, countryOf, question, secondAxis, selected, onToggle, intro,
}: Props) {
  const fieldRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(1000)

  useLayoutEffect(() => {
    const el = fieldRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth || 1000))
    ro.observe(el)
    setWidth(el.clientWidth || 1000)
    return () => ro.disconnect()
  }, [])

  // Stable pseudo-random intro offsets — regenerating them each render would
  // make the flags twitch instead of settle.
  const introPos = useMemo(
    () =>
      cities.map((_c, i) => {
        const seed = (i * 2654435761) % 4294967296
        return { left: 8 + ((seed >>> 8) % 84), top: 10 + ((seed >>> 16) % 72), rot: ((seed >>> 4) % 17) - 8 }
      }),
    [cities],
  )

  const scatter = secondAxis != null && question.kind !== 'country'

  const { placed, missing, gutter } = useMemo(() => {
    const rows = cities.map((city) => {
      const country = countryOf(city)
      return {
        city,
        value: question.value(city, country),
        y: secondAxis ? secondAxis.value(city, country) : null,
      }
    })

    // In scatter a city needs BOTH values. Half a coordinate is not a position,
    // it is a guess, so it goes to the gutter with everything else we don't know.
    const has = (r: { value: number | null; y: number | null }) =>
      r.value != null && (!secondAxis || r.y != null)

    const missing = rows.filter((r) => !has(r)).map((r) => r.city)
    const present = rows.filter(has) as { city: City; value: number; y: number | null }[]
    const gutter = missing.length > 0

    present.sort((a, b) => a.value - b.value)

    // When the gutter is showing it occupies the right edge, so the swarm's
    // usable width shrinks to match. Without this the cities at the top of the
    // scale (Las Vegas on sunshine, Milan pinned at "never") sit underneath it.
    const squeeze = gutter ? GUTTER_X : 100

    const taken: { x: number; lane: number }[] = []
    const placed: Placed[] = present.map(({ city, value, y }) => {
      const capped = question.cap != null && value >= question.cap
      const shown = capped ? question.cap! : value
      const x = question.scale(shown)
      const xpx = (x / 100) * (squeeze / 100) * width

      if (scatter) {
        // No lanes in a scatter: height is the second value, and nothing else.
        return { city, value, y, x, lane: 0, crowded: false, labUp: false, capped }
      }

      let lane = 0
      for (const cand of LANE_ORDER) {
        if (!taken.some((t) => t.lane === cand && Math.abs(t.x - xpx) < MIN_GAP)) {
          lane = cand
          break
        }
      }
      const crowded = taken.some(
        (t) => Math.abs(t.x - xpx) < CROWD_GAP && Math.abs(t.lane - lane) <= 1,
      )
      taken.push({ x: xpx, lane })

      return {
        city, value, y, x, lane,
        crowded: crowded && !ANCHORS.has(city.id),
        labUp: lane < 0,
        capped,
      }
    })

    return { placed, missing, gutter }
  }, [cities, countryOf, question, secondAxis, scatter, width])

  /* Plot geometry, in pixels.
   *
   * The swarm is unchanged: it spends a percentage of the field and gives the
   * last 13% back to the gutter, which is fine because it only ever ran at
   * comfortable widths. The scatter reserves the gutter in PIXELS instead —
   * 13% of a 250px phone field is 32px, narrower than the 70px gutter, so a
   * percentage would post dots underneath it. It also gives up a left column
   * to the y tick values and a strip at the top to the y-axis title. */
  const squeeze = gutter ? GUTTER_X : 100
  const yAxisW = scatter ? (width < NARROW ? Y_AXIS_W_NARROW : Y_AXIS_W) : 0
  const plotTop = scatter ? PLOT_TOP : 0
  const plotBottom = FIELD_H - (scatter ? PLOT_BOTTOM : 0)
  const plotRight = scatter
    ? width - (gutter ? GUTTER_RESERVE : 0)
    : (squeeze / 100) * width
  /** A 0-100 position on the question's own scale -> a pixel across the plot.
   *  In swarm yAxisW is 0 and plotRight is the squeezed width, so this reduces
   *  to exactly the percentage the swarm has always used. */
  const toX = (pct: number) => yAxisW + (pct / 100) * (plotRight - yAxisW)
  const toY = (pct: number) => plotBottom - (pct / 100) * (plotBottom - plotTop)

  /* Scatter labels re-collide in 2D, against the positions actually rendered. */
  const labels = useMemo(() => {
    if (!scatter || !secondAxis) return null
    return collide2D(
      placed.map((p) => ({
        id: p.city.id,
        name: p.city.name,
        x: toX(p.x),
        y: p.y == null ? plotBottom : toY(secondAxis.scale(p.y)),
        anchor: ANCHORS.has(p.city.id),
      })),
      gutter ? [{ l: width - 70, r: width - 6, t: 6, b: FIELD_H - 22 }] : [],
    )
    // toX/toY are closures rebuilt every render, but they are pure functions of
    // the geometry listed here, so this is the complete dependency set.
  }, [scatter, secondAxis, placed, gutter, yAxisW, width, plotTop, plotBottom])

  const selIndex = (id: string) => selected.indexOf(id)

  if (question.kind === 'country') {
    return <CountryBars cities={cities} countryOf={countryOf} selected={selected} onToggle={onToggle} />
  }

  return (
    <>
      <div
        ref={fieldRef}
        style={{
          position: 'relative',
          height: FIELD_H,
          transition: 'height var(--dur-slow) var(--ease-out)',
        }}
      >
        {/* Swarm-only furniture: the centreline is the lane grid's spine, and a
            scatter has no lanes for it to describe. */}
        {!scatter && (
          <div style={{ position: 'absolute', inset: '50% 0 auto 0', height: 1, background: 'var(--grid)' }} />
        )}

        {/* x ticks — vertical rules with their value underneath */}
        {question.ticks.map(([v, label]) => (
          <div key={label} aria-hidden="true"
            style={{
              position: 'absolute', top: plotTop, bottom: FIELD_H - plotBottom + (scatter ? 0 : SWARM_TICK_BOTTOM),
              width: 1, left: toX(question.scale(v)), background: 'var(--grid)',
            }}>
            <b style={{
              position: 'absolute', bottom: -16, left: -20, width: 40, textAlign: 'center',
              fontWeight: 400, fontSize: 10, color: 'var(--ink-3)',
            }}>{label}</b>
          </div>
        ))}

        {/* y axis — the same rules and the same 10px values as the x ticks, laid
            the other way, plus a title that says which direction is which. */}
        {scatter && secondAxis && (
          <>
            {secondAxis.ticks.map(([v, label]) => (
              <div key={label} aria-hidden="true"
                style={{
                  position: 'absolute', left: yAxisW, top: toY(secondAxis.scale(v)),
                  width: Math.max(0, plotRight - yAxisW), height: 1, background: 'var(--grid)',
                }}>
                <b style={{
                  position: 'absolute', right: '100%', top: -7, marginRight: 6,
                  fontWeight: 400, fontSize: 10, color: 'var(--ink-3)', whiteSpace: 'nowrap',
                }}>{label}</b>
              </div>
            ))}
            <div
              data-y-axis-label=""
              style={{
                position: 'absolute', left: 0, top: 0, fontSize: 11,
                color: 'var(--ink-2)', whiteSpace: 'nowrap',
              }}
            >
              ↑ {secondAxis.axisLabel}
            </div>
          </>
        )}

        {/* dots */}
        {placed.map((p) => {
          const i = cities.indexOf(p.city)
          const si = selIndex(p.city.id)
          const isSel = si >= 0
          const introStyle = introPos[i] ?? { left: 50, top: 50, rot: 0 }
          const lab = labels?.get(p.city.id)

          const px = intro ? (introStyle.left / 100) * width : toX(p.x)
          const py = intro
            ? (introStyle.top / 100) * FIELD_H
            : scatter && secondAxis && p.y != null
              ? toY(secondAxis.scale(p.y))
              : FIELD_H / 2 + p.lane * LANE_H

          const xText = question.fmt(p.capped ? question.cap! : p.value)
          const yText = scatter && secondAxis ? secondAxis.fmt(p.y) : null
          const reading = yText ? `${xText} · ${yText}` : xText

          const crowded = scatter ? lab?.show === false : p.crowded
          const labUp = scatter ? lab?.up === true : p.labUp

          return (
            <button
              key={p.city.id}
              onClick={() => onToggle(p.city.id)}
              aria-pressed={isSel}
              aria-label={`${p.city.name} — ${reading}${isSel ? ', selected' : ''}`}
              title={`${p.city.name} · ${reading}`}
              className="swarm-dot"
              data-city={p.city.id}
              data-sel={isSel || undefined}
              data-crowd={crowded && !isSel ? '' : undefined}
              data-labup={labUp ? '' : undefined}
              style={{
                transform: `translate(${px}px, ${py}px) translate(-50%, -50%)`,
                ['--sc' as string]: isSel ? pickColor(si) : undefined,
                zIndex: isSel ? 7 : undefined,
              }}
            >
              <span className="swarm-mark" style={{ transform: intro ? `rotate(${introStyle.rot}deg)` : undefined }}>
                <Flag cc={p.city.country} size={intro ? 15 : 17} />
              </span>
              <small>{p.city.name}</small>
            </button>
          )
        })}

        {/* the "no data" gutter — cities are parked here, never dropped */}
        {missing.length > 0 && (
          <div
            style={{
              position: 'absolute', right: 6, top: 6, bottom: 22, width: 64,
              borderLeft: '1px dashed var(--line)', color: 'var(--ink-3)',
              fontSize: 10, textAlign: 'center', paddingTop: 2,
              transition: 'opacity var(--dur-base)',
            }}
          >
            no<br />data
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'center', marginTop: 8 }}>
              {missing.map((c) => {
                const si = selIndex(c.id)
                const why = scatter ? 'no data for one of these two axes' : 'no data for this question'
                return (
                  <button
                    key={c.id}
                    onClick={() => onToggle(c.id)}
                    aria-pressed={si >= 0}
                    aria-label={`${c.name} — ${why}${si >= 0 ? ', selected' : ''}`}
                    title={`${c.name} — ${why}`}
                    className="swarm-dot swarm-null"
                    data-city={c.id}
                    data-sel={si >= 0 || undefined}
                    style={{ position: 'static', ['--sc' as string]: si >= 0 ? pickColor(si) : undefined }}
                  >
                    <span className="swarm-mark"><Flag cc={c.country} size={13} /></span>
                    <small>{c.name}</small>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </>
  )
}

/* ------------------------------------------------------------------ */
/* PR / citizenship — two-stage country bars                           */
/* ------------------------------------------------------------------ */

function CountryBars({
  cities, countryOf, selected, onToggle,
}: {
  cities: City[]
  countryOf: (c: City) => Country | undefined
  selected: string[]
  onToggle: (id: string) => void
}) {
  // One row per country, ordered by how quickly you can stop depending on an
  // employer. Countries with no path sit at the end with a dashed stub.
  const rows = useMemo(() => {
    const seen = new Map<string, Country>()
    for (const c of cities) {
      const k = countryOf(c)
      if (k && !seen.has(k.id)) seen.set(k.id, k)
    }
    return [...seen.values()].sort((a, b) => {
      const ap = a.pr_years_typical, bp = b.pr_years_typical
      if (ap == null && bp == null) return a.name.localeCompare(b.name)
      if (ap == null) return 1
      if (bp == null) return -1
      return ap - bp
    })
  }, [cities, countryOf])

  const scale = 29

  return (
    <div style={{ position: 'relative', height: rows.length * BAR_ROW_H + 26, paddingTop: 8 }}>
      {rows.map((k, i) => {
        const pr = k.pr_years_typical
        const cit = k.citizenship_years_typical
        const citiesHere = cities.filter((c) => c.country === k.id)
        const anySelected = citiesHere.some((c) => selected.includes(c.id))
        const note =
          k.id === 'US' ? ' · ⚑ lottery + Iran ban'
            : k.id === 'QA' ? ' · no citizenship'
              : k.id === 'AE' ? 'golden visa only — no citizenship path'
                : ''

        return (
          <div key={k.id}
            style={{
              position: 'absolute', left: 6, right: 6, top: 14 + i * BAR_ROW_H,
              display: 'flex', alignItems: 'center', gap: 9, fontSize: 11.5,
              transition: 'top var(--dur-slow) var(--ease-out)',
            }}>
            <button
              onClick={() => { const first = citiesHere[0]; if (first) onToggle(first.id) }}
              aria-pressed={anySelected}
              style={{
                width: 104, textAlign: 'right', color: anySelected ? 'var(--ink-1)' : 'var(--ink-2)',
                fontWeight: anySelected ? 600 : 400, flex: 'none', fontSize: 11.5,
              }}
              title={`${k.name} — ${pr == null ? 'no permanent path' : `~${pr} yrs to residency`}`}
            >
              {k.name}
            </button>

            {pr == null ? (
              <span aria-hidden="true" style={{
                width: 16, height: 10, border: '1.5px dashed var(--ink-3)', borderRadius: 4, flex: 'none',
              }} />
            ) : (
              <>
                <FlagRibbon cc={k.id} width={Math.max(10, pr * scale)} height={13} />
                {cit != null && cit > pr && (
                  <span aria-hidden="true" style={{
                    width: (cit - pr) * scale, height: 5, borderRadius: 3, opacity: 0.45, flex: 'none',
                    background: 'repeating-linear-gradient(90deg, var(--ink-2) 0 4px, transparent 4px 8px)',
                  }} />
                )}
              </>
            )}

            <b style={{ fontWeight: 500, color: 'var(--ink-2)', whiteSpace: 'nowrap' }}>
              {pr == null
                ? <em style={{ fontStyle: 'normal', color: 'var(--warn)' }}>{note}</em>
                : <>~{pr}{cit != null ? ` → ~${cit}` : ''} yrs
                  {note && <em style={{ fontStyle: 'normal', color: 'var(--warn)' }}>{note}</em>}</>}
            </b>
          </div>
        )
      })}
    </div>
  )
}
