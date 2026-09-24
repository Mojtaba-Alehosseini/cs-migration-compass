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

import { useEffect, useMemo, useRef } from 'react'
import { useMeasuredWidth } from './chart/useMeasuredWidth'
import { Flag, FlagRibbon } from './Flag'
import type { City, Country } from '../data/types'
import type { Question, SecondAxis } from '../data/questions'
import type { Budget } from '../data/compute'
import { ANCHORS, pickColor } from '../data/questions'

const LANE_ORDER = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7]
/* Package 47, NEEDS-DECISION #87 — ruled: a taller field on phones, sized to
 * what each question needs; desktop unchanged.
 *
 * The field above packs every city into ±7 lanes of a 440px field. On a phone
 * that is not enough room: when all fifteen lanes are taken near an x the
 * packer gave up and drew the city on top of whoever held the middle lane (28
 * pairs on years-to-a-home at 390), lanes ±6 and ±7 sit on or past the tick
 * labels (lane 7's centre is 444px, below the field's own edge), and the
 * gutter, given 13% of the width, is 42px of an 82px box at 390, so four cities
 * WITH a value were drawn inside "no data".
 *
 * So the field lays out the classic way first, and only where that fails — a
 * city with no free lane, a lane the 440px field cannot hold with its label
 * clear of the ticks, or a valued city reaching into the gutter — it lays out
 * again FITTED: the gutter reserved in pixels as the scatter already does, as
 * many lanes as the question needs, and the field as tall as those lanes. The
 * switch is where the classic layout stops working for that question at that
 * width, not a width chosen in advance; at desktop widths the classic layout
 * never fails, so desktop is untouched by construction. Flag size, lane pitch
 * and labels are the same in both. */
const FIT_LANES = [0, ...Array.from({ length: 40 }, (_, i) => [i + 1, -(i + 1)]).flat()]
/* The most lanes each side a 440px field holds with the bottom lane's label
 * clear of the tick labels: 220 + 32L + 22 <= 440 - 18. */
const CLASSIC_MAX_LANE = 5
/* Top and bottom room around the lanes in a fitted field — the lane's label
 * above or below its flag, and the tick labels' strip. (2L + 1) lanes of 32px
 * plus this is 531px for ±7, 659 for ±9, 915 for ±13 — package 46's figures. */
const FIT_PAD = 51
const LANE_H = 32
const MIN_GAP = 19       // px between dots in the same lane
const CROWD_GAP = 34     // px within which a label is hidden
const FIELD_H = 440
const BAR_ROW_H = 29
/* The box width the one-row country bars need at 29px a year: 834px in the
   Compass, Editorial and Terminal themes and 830px in Warm, measured in
   package 46 — plus 26px for a platform whose interface font sets wider. */
const WIDE_BARS = 860
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
/* The gutter box is 76px wide with a 6px margin; a dot is 25px wide, so the
   plot has to stop 96px short of the edge for the rightmost mark to clear it.
   76, not 64: package 44 raised the parked cities' labels to the 12px floor
   (#79) and the widest of them — "Gold Coast", measured across every question
   this field asks — is 64.3px, so a 63px content box overflowed its own gutter
   by 5px. Adversarial review finding 7. */
const GUTTER_RESERVE = 96

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
  /** The reader's own rent/living assumptions. The field is where they have
   *  to show up: `home` and `left` are computed FROM them, and the home
   *  question's own sub-line promises they are editable. */
  budget: Budget
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
  cities, countryOf, question, secondAxis, budget, selected, onToggle, intro,
}: Props) {
  /* Package 46: the fallback is 0, and the dots wait for a real width.
   * It was 1000 — a desktop field's width — so the first render laid every
   * dot out at that scale. The measurement corrected it before paint, but by
   * then reading the width had fixed those positions as where each dot's
   * 750ms transition STARTS: on a phone the flags drifted in from as far as
   * 827px, off the right edge, and the page was that wide until they landed
   * (at 390 the browser's layout viewport grew to 827px). A dot that is not
   * drawn until the field is measured starts where it belongs. */
  const [fieldRef, width] = useMeasuredWidth<HTMLDivElement>(0)

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

  const { placed, missing, gutter, fit, maxLane } = useMemo(() => {
    const rows = cities.map((city) => {
      const country = countryOf(city)
      return {
        city,
        value: question.value(city, country, budget),
        y: secondAxis ? secondAxis.value(city, country, budget) : null,
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

    /* The lanes, and so the field's height, belong to the QUESTION: packed
     * from the cities with a value for it, with its own gutter — the same set
     * whether or not a second axis is on (a scatter sends cities missing the
     * SECOND value to the gutter too, which would change the packing, the
     * height, and move "+ second axis" when it is tapped). With no second
     * axis these are exactly `present` and `gutter`. */
    const swarmPresent = rows.filter((r) => r.value != null) as { city: City; value: number; y: number | null }[]
    swarmPresent.sort((a, b) => a.value - b.value)
    const swarmGutter = swarmPresent.length < rows.length

    // When the gutter is showing it occupies the right edge, so the swarm's
    // usable width shrinks to match. Without this the cities at the top of the
    // scale (Las Vegas on sunshine, Milan pinned at "never") sit underneath it.
    const squeeze = swarmGutter ? GUTTER_X : 100

    /* One packing pass over `usable` pixels with the given lane order.
     * `fellBack` counts cities that found no free lane and were put in the
     * middle one anyway — on top of whoever is there. */
    const pack = (usable: number, order: number[]) => {
      const taken: { x: number; lane: number }[] = []
      let fellBack = 0
      const placed: Placed[] = swarmPresent.map(({ city, value, y }) => {
        const capped = question.cap != null && value >= question.cap
        const shown = capped ? question.cap! : value
        const x = question.scale(shown)
        const xpx = (x / 100) * usable

        let lane: number | null = null
        for (const cand of order) {
          if (!taken.some((t) => t.lane === cand && Math.abs(t.x - xpx) < MIN_GAP)) {
            lane = cand
            break
          }
        }
        if (lane == null) { lane = 0; fellBack++ }
        const crowded = taken.some(
          (t) => Math.abs(t.x - xpx) < CROWD_GAP && Math.abs(t.lane - lane!) <= 1,
        )
        taken.push({ x: xpx, lane })

        return {
          city, value, y, x, lane,
          crowded: crowded && !ANCHORS.has(city.id),
          labUp: lane < 0,
          capped,
        }
      })
      const maxLane = placed.reduce((m, p) => Math.max(m, Math.abs(p.lane)), 0)
      return { placed, fellBack, maxLane }
    }

    const classic = pack((squeeze / 100) * width, LANE_ORDER)
    /* Does the classic layout hold at this width? A city with no lane, a lane
     * the 440px field cannot hold, or a valued flag reaching the gutter's box
     * (its left edge is 82px from the field's right: 76 wide, 6 in). */
    const gutterLeft = width - 82
    const reachesGutter = swarmGutter && classic.placed.some((p) => (p.x / 100) * (squeeze / 100) * width + 12.5 > gutterLeft)
    const fit = width > 0 && (classic.fellBack > 0 || classic.maxLane > CLASSIC_MAX_LANE || reachesGutter)
    const lanes = fit ? pack(width - (swarmGutter ? GUTTER_RESERVE : 0), FIT_LANES) : classic
    /* The height is the QUESTION's, decided by its swarm even while a second
     * axis is on: a scatter scales to any height, and keeping the swarm's means
     * "+ second axis", under the field, stays under the finger that tapped it
     * instead of jumping up by the difference (475px on years-to-a-home at 390).
     * At desktop widths the swarm is classic, so the scatter is 440px as before. */
    const placed = scatter
      ? present.map(({ city, value, y }): Placed => {
        const capped = question.cap != null && value >= question.cap
        // No lanes in a scatter: height is the second value, and nothing else.
        return { city, value, y, x: question.scale(capped ? question.cap! : value), lane: 0, crowded: false, labUp: false, capped }
      })
      : lanes.placed
    return { placed, missing, gutter, fit, maxLane: lanes.maxLane }
  // `budget` belongs here because the placement above READS it. Leaving it out
  // made the field ignore a live budget edit entirely: every other dependency
  // is stable across one, so the memo never re-ran and the dots kept the
  // positions they had before the slider moved.
  }, [cities, countryOf, question, secondAxis, scatter, width, budget])

  /* Plot geometry, in pixels.
   *
   * The swarm is unchanged: it spends a percentage of the field and gives the
   * last 13% back to the gutter, which is fine because it only ever ran at
   * comfortable widths. The scatter reserves the gutter in PIXELS instead —
   * 13% of a 250px phone field is 32px, narrower than the 70px gutter, so a
   * percentage would post dots underneath it. It also gives up a left column
   * to the y tick values and a strip at the top to the y-axis title.
   *
   * Package 46 measured the swarm's half of that sentence and it does not
   * hold: Home is the page a phone lands on, and at 390 the percentage leaves
   * 42px for an 82px gutter, so the top of three scales is drawn inside "no
   * data". Reserving the gutter in pixels here, alone, doubles the dots drawn
   * on top of each other (28 -> 57 pairs on years-to-a-home), because the
   * phone field is already short of lanes. Both are one capacity problem, and
   * NEEDS-DECISION #87 has the numbers and the options — ruled in package 47:
   * where the classic layout fails, the FITTED one reserves the gutter in
   * pixels too and makes the field as tall as its lanes (see FIT_LANES). */
  const squeeze = gutter ? GUTTER_X : 100
  const fieldH = fit ? Math.max(FIELD_H, (2 * maxLane + 1) * LANE_H + FIT_PAD) : FIELD_H
  const yAxisW = scatter ? (width < NARROW ? Y_AXIS_W_NARROW : Y_AXIS_W) : 0
  const plotTop = scatter ? PLOT_TOP : 0
  const plotBottom = fieldH - (scatter ? PLOT_BOTTOM : 0)
  const plotRight = scatter || fit
    ? width - (gutter ? GUTTER_RESERVE : 0)
    : (squeeze / 100) * width

  /* A change of WIDTH alone — a phone turned on its side, a window resized —
   * moves every dot to where it belongs at the new width, and must not animate
   * there: a dot sliding from its old x runs past the new edge, and package 46
   * measured a rotated phone's page at 744-837px wide for seconds while the
   * flags slid. A new question, axis, budget or data still animates as before.
   * The first measurement is a width change too (0 -> the field), so the first
   * painted frame is already at the fitted height instead of growing to it. */
  const layoutKey = `${question.id}|${secondAxis?.id ?? ''}|${JSON.stringify(budget)}|${cities.length}`
  const prevLayout = useRef({ width, layoutKey })
  const snap = prevLayout.current.width !== width && prevLayout.current.layoutKey === layoutKey
  useEffect(() => { prevLayout.current = { width, layoutKey } })
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
      gutter ? [{ l: width - 70, r: width - 6, t: 6, b: fieldH - 22 }] : [],
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
          height: fieldH,
          // A new question grows or shrinks the field on the site's own motion
          // tokens (zeroed under reduced motion); a width-only change snaps.
          transition: snap ? 'none' : 'height var(--dur-slow) var(--ease-out)',
        }}
      >
        {/* Swarm-only furniture: the centreline is the lane grid's spine, and a
            scatter has no lanes for it to describe. */}
        {!scatter && (
          <div style={{ position: 'absolute', inset: '50% 0 auto 0', height: 1, background: 'var(--grid)' }} />
        )}

        {/* x ticks — vertical rules with their value underneath. A label
            centred on its rule would reach 20px right of it, and the last one
            ("≈never", "3,600", "$125k" on a phone) then printed inside the "no
            data" gutter's column — the pin's own label where "no data" is
            (package 46's review, #87). Such a label ends at its rule instead. */}
        {question.ticks.map(([v, label]) => {
          const tx = toX(question.scale(v))
          const endAtRule = gutter && tx + 20 > width - 84
          return (
            <div key={label} aria-hidden="true"
              style={{
                position: 'absolute', top: plotTop, bottom: fieldH - plotBottom + (scatter ? 0 : SWARM_TICK_BOTTOM),
                width: 1, left: tx, background: 'var(--grid)',
              }}>
              <b style={{
                position: 'absolute', bottom: -16, left: endAtRule ? -40 : -20, width: 40,
                textAlign: endAtRule ? 'right' : 'center',
                fontWeight: 400, fontSize: 10, color: 'var(--ink-2)',
              }}>{label}</b>
            </div>
          )
        })}

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
                  fontWeight: 400, fontSize: 10, color: 'var(--ink-2)', whiteSpace: 'nowrap',
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

        {/* dots — not before the field has a measured width (see above) */}
        {width > 0 && placed.map((p) => {
          const i = cities.indexOf(p.city)
          const si = selIndex(p.city.id)
          const isSel = si >= 0
          const introStyle = introPos[i] ?? { left: 50, top: 50, rot: 0 }
          const lab = labels?.get(p.city.id)

          const px = intro ? (introStyle.left / 100) * width : toX(p.x)
          const py = intro
            ? (introStyle.top / 100) * fieldH
            : scatter && secondAxis && p.y != null
              ? toY(secondAxis.scale(p.y))
              : fieldH / 2 + p.lane * LANE_H

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
                transition: snap ? 'none' : undefined,
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
            /* Addressable, so a check can find the mark rather than matching
               its text — which is "no<br>data", so a search for "no data"
               finds nothing and reports a mark that IS drawn as unreachable. */
            className="swarm-gutter"
            style={{
              position: 'absolute', right: 6, top: 6, bottom: 22, width: 76,
              borderLeft: '1px dashed var(--line)', color: 'var(--ink-3)',
              /* Package 44, #79. The ruling raises the marks that say the chart
                 cannot show you something, and this heading is the one that
                 says it for every city below it — the same argument as
                 `.swarm-null small`, which the item names. 10px was the
                 smallest text on Home and it was the refusal. */
              fontSize: 'var(--text-2xs)', textAlign: 'center', paddingTop: 2,
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

  /* Package 46. The one-row layout draws 29px a year, and its longest row —
   * Qatar's 20-year bar and "~20 yrs · no citizenship" — needs 830–834px of
   * this box in every theme (measured). A phone's box is 290–320px, so at 390
   * the rows ran to 863px: the page was wider than the screen and every value
   * label from Norway down sat off it. Where the row does not fit, each
   * country takes two lines instead, name and value over its bar, and the
   * scale shrinks to fit the width — one scale for every row, as before, so
   * the bars still compare. Where it fits, nothing changes. */
  const [boxRef, boxW] = useMeasuredWidth<HTMLDivElement>(0)
  const wide = boxW >= WIDE_BARS
  const maxYears = Math.max(1, ...rows.map((k) => Math.max(k.pr_years_typical ?? 0, k.citizenship_years_typical ?? 0)))
  // Narrow: the row's 6px insets and the 9px gap between ribbon and dashes
  // come off first, so the longest path ends at the box's edge, not past it.
  const scale = wide ? 29 : Math.min(29, Math.max(0, boxW - 12 - 9) / maxYears)

  return (
    <div ref={boxRef} style={wide
      ? { position: 'relative', height: rows.length * BAR_ROW_H + 26, paddingTop: 8 }
      : { padding: '10px 0 6px' }}>
      {boxW > 0 && rows.map((k, i) => {
        const pr = k.pr_years_typical
        const cit = k.citizenship_years_typical
        const citiesHere = cities.filter((c) => c.country === k.id)
        const anySelected = citiesHere.some((c) => selected.includes(c.id))
        const note =
          k.id === 'US' ? ' · ⚑ lottery + Iran ban'
            : k.id === 'QA' ? ' · no citizenship'
              : k.id === 'AE' ? 'golden visa only — no citizenship path'
                : ''

        const name = (
          <button
            onClick={() => { const first = citiesHere[0]; if (first) onToggle(first.id) }}
            aria-pressed={anySelected}
            style={{
              width: wide ? 104 : undefined, textAlign: wide ? 'right' : 'left',
              color: anySelected ? 'var(--ink-1)' : 'var(--ink-2)',
              fontWeight: anySelected ? 600 : 400, flex: 'none', fontSize: 11.5,
            }}
            title={`${k.name} — ${pr == null ? 'no permanent path' : `~${pr} yrs to residency`}`}
          >
            {k.name}
          </button>
        )

        const bars = pr == null ? (
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
        )

        const value = (
          <b style={{ fontWeight: 500, color: 'var(--ink-2)', whiteSpace: wide ? 'nowrap' : undefined }}>
            {pr == null
              ? <em style={{ fontStyle: 'normal', color: 'var(--warn)' }}>{note}</em>
              : <>~{pr}{cit != null ? ` → ~${cit}` : ''} yrs
                {note && <em style={{ fontStyle: 'normal', color: 'var(--warn)' }}>{note}</em>}</>}
          </b>
        )

        return wide ? (
          <div key={k.id}
            style={{
              position: 'absolute', left: 6, right: 6, top: 14 + i * BAR_ROW_H,
              display: 'flex', alignItems: 'center', gap: 9, fontSize: 11.5,
              transition: 'top var(--dur-slow) var(--ease-out)',
            }}>
            {name}
            {bars}
            {value}
          </div>
        ) : (
          <div key={k.id} style={{ padding: '4px 6px 5px', fontSize: 11.5 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', columnGap: 9 }}>
              {name}
              {value}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginTop: 3, minHeight: 13 }}>
              {bars}
            </div>
          </div>
        )
      })}
    </div>
  )
}
