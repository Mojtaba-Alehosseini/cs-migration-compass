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
 * Cities with no value are never dropped. They park in a "no data" gutter at
 * the edge, which is the whole point of the Oslo sunshine case.
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

export interface Placed {
  city: City
  value: number | null
  x: number          // 0-100
  lane: number
  crowded: boolean
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

  const { placed, missing, gutter } = useMemo(() => {
    const withValues = cities.map((city) => ({
      city,
      value: question.value(city, countryOf(city)),
    }))

    const missing = withValues.filter((p) => p.value == null).map((p) => p.city)
    const present = withValues.filter((p) => p.value != null) as { city: City; value: number }[]
    const gutter = missing.length > 0

    present.sort((a, b) => a.value - b.value)

    // When the gutter is showing it occupies the right edge, so the swarm's
    // usable width shrinks to match. Without this the cities at the top of the
    // scale (Las Vegas on sunshine, Milan pinned at "never") sit underneath it.
    const squeeze = gutter ? GUTTER_X : 100

    const taken: { x: number; lane: number }[] = []
    const placed: Placed[] = present.map(({ city, value }) => {
      const capped = question.cap != null && value >= question.cap
      const shown = capped ? question.cap! : value
      const x = (question.scale(shown) / 100) * squeeze
      const xpx = (x / 100) * width

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

      return { city, value, x, lane, crowded: crowded && !ANCHORS.has(city.id), capped }
    })

    return { placed, missing, gutter }
  }, [cities, countryOf, question, width])

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
        {/* centre line + tick grid */}
        <div style={{ position: 'absolute', inset: '50% 0 auto 0', height: 1, background: 'var(--grid)' }} />
        {question.ticks.map(([v, label]) => (
          <div key={label} aria-hidden="true"
            style={{
              position: 'absolute', top: 0, bottom: 18, width: 1,
              left: `${(question.scale(v) / 100) * (gutter ? GUTTER_X : 100)}%`, background: 'var(--grid)',
            }}>
            <b style={{
              position: 'absolute', bottom: -16, left: -20, width: 40, textAlign: 'center',
              fontWeight: 400, fontSize: 10, color: 'var(--ink-3)',
            }}>{label}</b>
          </div>
        ))}

        {/* dots */}
        {placed.map((p) => {
          const i = cities.indexOf(p.city)
          const si = selIndex(p.city.id)
          const isSel = si >= 0
          const introStyle = introPos[i] ?? { left: 50, top: 50, rot: 0 }
          const y = secondAxis
            ? secondAxis.value(p.city, countryOf(p.city))
            : null
          const yPos = secondAxis && y != null ? 100 - secondAxis.scale(y) : null

          return (
            <button
              key={p.city.id}
              onClick={() => onToggle(p.city.id)}
              aria-pressed={isSel}
              aria-label={`${p.city.name} — ${question.fmt(p.capped ? question.cap! : p.value)}${isSel ? ', selected' : ''}`}
              title={`${p.city.name} · ${question.fmt(p.capped ? question.cap! : p.value)}`}
              className="swarm-dot"
              data-sel={isSel || undefined}
              data-crowd={p.crowded && !isSel ? '' : undefined}
              data-labup={p.lane < 0 ? '' : undefined}
              style={{
                position: 'absolute',
                left: intro ? `${introStyle.left}%` : `${p.x}%`,
                top: intro
                  ? `${introStyle.top}%`
                  : secondAxis && yPos != null
                    ? `${yPos}%`
                    : `calc(50% + ${p.lane * LANE_H}px)`,
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
                return (
                  <button
                    key={c.id}
                    onClick={() => onToggle(c.id)}
                    aria-pressed={si >= 0}
                    aria-label={`${c.name} — no data for this question${si >= 0 ? ', selected' : ''}`}
                    title={`${c.name} — no data`}
                    className="swarm-dot swarm-null"
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

      {secondAxis && (
        <div style={{
          display: 'flex', justifyContent: 'space-between', fontSize: 11,
          color: 'var(--ink-3)', paddingTop: 4,
        }}>
          <span>{secondAxis.axisL} (bottom)</span>
          <span style={{ color: 'var(--ink-2)' }}>up ↑ {secondAxis.label}</span>
          <span>{secondAxis.axisR} (top)</span>
        </div>
      )}
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
