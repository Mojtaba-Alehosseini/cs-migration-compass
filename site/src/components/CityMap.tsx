/* Where the 73 cities are.
 *
 * A real Mercator projection, cropped to the box the cities actually occupy
 * (lon -128..157, lat -45..62), so there is no empty Pacific and no Antarctica.
 * Land is Natural Earth 110m in the quiet paper tone; the flag-dots are the only
 * colour on it, exactly as on the Home field.
 *
 * The map is an enhancement and never the only path: the country list below it
 * is the canonical, geography-free browser, it holds the same 73 cities, and
 * under 560px the map yields to it rather than shrinking into an untappable
 * thumbnail. Dots are real buttons — reachable and activatable from the
 * keyboard, each labelled with its city and country.
 *
 * Cities closer together than a tappable dot are relaxed apart. That is a lie
 * about geography, so the line under the map says so out loud.
 */

import { useMemo } from 'react'
import { Flag } from './Flag'
import { LAND_PATH, LAND_VIEWBOX } from '../data/land'
import type { City } from '../data/types'

/** The crop. Chosen so the westernmost city (SF) and easternmost (Sydney) both
 *  sit inside it with a margin, and nothing empty is drawn. */
const MAP = { LON0: -128, LON1: 157, LAT0: -45, LAT1: 62, W: LAND_VIEWBOX.w, H: LAND_VIEWBOX.h }

/** Mercator's y, in radians of the inverse Gudermannian. */
const mer = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))

export function project(lat: number, lon: number): { x: number; y: number } {
  const y0 = mer(MAP.LAT1)
  const y1 = mer(MAP.LAT0)
  return {
    x: ((lon - MAP.LON0) / (MAP.LON1 - MAP.LON0)) * MAP.W,
    y: ((mer(lat) - y0) / (y1 - y0)) * MAP.H,
  }
}

interface Pt { id: string; x: number; y: number }

/** Push overlapping dots apart until each is tappable, clamping inside the loop
 *  so relaxation works against the borders instead of being undone by them —
 *  Tampere sits right on the top edge. */
export function relax(pts: Pt[], minD: number): Pt[] {
  for (let it = 0; it < 90; it++) {
    let moved = false
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const a = pts[i]!
        const b = pts[j]!
        let dx = b.x - a.x
        let dy = b.y - a.y
        let d = Math.hypot(dx, dy)
        if (d >= minD) continue
        moved = true
        if (d < 0.01) { dx = 1; dy = 0; d = 1 }
        const push = (minD - d) / 2 / d
        b.x += dx * push
        b.y += dy * push
        a.x -= dx * push
        a.y -= dy * push
      }
    }
    for (const p of pts) {
      p.x = Math.max(9, Math.min(MAP.W - 9, p.x))
      p.y = Math.max(9, Math.min(MAP.H - 9, p.y))
    }
    if (!moved) break
  }
  return pts
}

interface Props {
  cities: City[]
  countryName: (cc: string) => string
  isSelected: (id: string) => boolean
  onToggle: (id: string) => void
  /** Non-matching dots dim while the search above is filtering. */
  query: string
  matches: (city: City) => boolean
}

export function CityMap({ cities, countryName, isSelected, onToggle, query, matches }: Props) {
  const placed = useMemo(() => {
    const pts: Pt[] = []
    const byId = new Map<string, City>()
    for (const c of cities) {
      if (c.lat == null || c.lon == null) continue
      const { x, y } = project(c.lat, c.lon)
      pts.push({ id: c.id, x, y })
      byId.set(c.id, c)
    }
    relax(pts, 13)
    return pts.map((p) => ({ ...p, city: byId.get(p.id)! }))
  }, [cities])

  const filtering = query.trim().length >= 2

  return (
    <div className="mappanel">
      <svg viewBox={`0 0 ${MAP.W} ${MAP.H}`} aria-hidden="true">
        <path className="land" d={LAND_PATH} />
      </svg>
      <div className="mapdots">
        {placed.map(({ id, x, y, city }) => {
          const on = isSelected(id)
          return (
            <button
              key={id}
              type="button"
              className={`mdot${filtering && !matches(city) && !on ? ' dim' : ''}`}
              aria-pressed={on}
              aria-label={`${city.name}, ${countryName(city.country)}`}
              data-city={id}
              onClick={() => onToggle(id)}
              style={{ left: `${((x / MAP.W) * 100).toFixed(2)}%`, top: `${((y / MAP.H) * 100).toFixed(2)}%` }}
            >
              <Flag cc={city.country} size={12} className="mdot-mark" />
              <small aria-hidden="true">{city.name}</small>
            </button>
          )
        })}
      </div>
    </div>
  )
}
