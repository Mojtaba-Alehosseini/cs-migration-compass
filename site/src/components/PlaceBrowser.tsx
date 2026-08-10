/* The browser: every city we hold, arranged so a visitor can learn what the
 * site contains.
 *
 * Compare with no `?places` opens this, because an empty comparison is not a
 * state to escape — it is the moment the 73 cities are worth showing. The same
 * component opens as a sheet from "+ add a city", so there is one browser with
 * two presentations rather than two implementations that drift.
 *
 * The country list is canonical: alphabetical countries, alphabetical cities,
 * each card carrying the two numbers the Home field leads with. The map above
 * it is an enhancement. Nothing here is ranked, and a city missing a figure says
 * which figure is missing rather than showing a dash.
 */

import { useMemo, useState } from 'react'
import { Flag } from './Flag'
import { CityMap } from './CityMap'
import { useData } from '../data/store'
import { useSelection, MAX_PLACES } from '../data/selection'
import { useToast } from './Toast'
import { isNeverAffordable, missingInputs, yearsToHome } from '../data/compute'
import { moneyShort, years } from '../data/format'
import type { City, Country } from '../data/types'

/** Examples, not recommendations — four pairings that show what a comparison is. */
const POPULAR_PAIRS: [string, string][] = [
  ['berlin', 'toronto'],
  ['austin', 'dubai'],
  ['london', 'amsterdam'],
  ['helsinki', 'sydney'],
]

/** The country's own line in its group header. */
function stayLine(k: Country): string {
  const pr = k.pr_years_typical
  const cit = k.citizenship_years_typical
  if (pr == null) return k.id === 'AE' ? 'golden visa only — no citizenship path' : 'no permanent path'
  return cit == null ? `~${pr} yrs to PR` : `~${pr} yrs to PR · passport ~${cit}`
}

interface Props {
  variant: 'page' | 'sheet'
  /** Sheet only: closes it. */
  onClose?: () => void
  /** Page only: a popular pair jumps straight to the comparison. */
  onPair?: (ids: string[]) => void
}

export function PlaceBrowser({ variant, onClose, onPair }: Props) {
  const data = useData()
  const sel = useSelection()
  const toast = useToast()
  const [q, setQ] = useState('')
  const [mapOpen, setMapOpen] = useState(true)

  const query = q.trim().toLowerCase()
  const filtering = query.length >= 2

  const countryName = (cc: string) => data.countryById.get(cc)?.name ?? cc

  // City name OR its country's name — typing "germany" leaves the five German
  // cities, typing "syd" leaves Sydney.
  const matches = useMemo(() => (city: City) => {
    if (!filtering) return true
    if (city.name.toLowerCase().includes(query)) return true
    return countryName(city.country).toLowerCase().includes(query)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, filtering, data])

  const groups = useMemo(() => {
    const countries = [...data.countries].sort((a, b) => a.name.localeCompare(b.name))
    return countries
      .map((k) => ({ country: k, cities: (data.citiesByCountry.get(k.id) ?? []).filter(matches) }))
      .filter((g) => g.cities.length > 0)
  }, [data, matches])

  const shown = groups.reduce((n, g) => n + g.cities.length, 0)

  const toggle = (id: string) => {
    if (!sel.toggle(id)) toast(`${MAX_PLACES} places is the limit — remove one first`)
  }

  const search = (
    <input
      className="bigsearch"
      type="search"
      value={q}
      onChange={(e) => setQ(e.target.value)}
      placeholder={variant === 'sheet' ? 'Find a city or country…' : 'Find a city or country — try “berlin”, or “canada”…'}
      aria-label="Find a city or country"
    />
  )

  const list = (
    <div className="groups">
      {groups.length === 0 ? (
        <p className="quiet" style={{ padding: '22px 0' }}>
          Nothing matches “{q.trim()}” — try a city or a country name.
        </p>
      ) : (
        groups.map(({ country, cities }) => (
          <div className="cg" key={country.id}>
            <div className="cgh">
              <Flag cc={country.id} size={16} />
              <b>{country.name}</b>
              <span className="n">{cities.length} {cities.length === 1 ? 'city' : 'cities'}</span>
              <span className="stay">{stayLine(country)}</span>
            </div>
            <div className="cards">
              {cities.map((c) => <CityCard key={c.id} city={c} on={sel.has(c.id)}
                dim={!sel.has(c.id) && sel.atCap} onToggle={() => toggle(c.id)} />)}
            </div>
          </div>
        ))
      )}
    </div>
  )

  if (variant === 'sheet') {
    return (
      <>
        <div className="shead">
          <h2>Add a city</h2>
          <span>{sel.ids.length} of {MAX_PLACES} chosen · tap to add or remove</span>
          <button className="sheet-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {search}
        {list}
      </>
    )
  }

  return (
    <>
      <div className="searchrow">
        {search}
        <span className="hint">
          {filtering
            ? `${shown} of ${data.cities.length} cities match`
            : `${data.cities.length} cities · ${data.countries.length} countries`}
        </span>
      </div>

      <div className="pairs">
        <span className="lbl">Popular pairs —</span>
        {POPULAR_PAIRS.filter(([a, b]) => data.cityById.has(a) && data.cityById.has(b)).map(([a, b]) => {
          const ca = data.cityById.get(a)!
          const cb = data.cityById.get(b)!
          return (
            <button className="pairbtn" key={`${a}-${b}`} onClick={() => onPair?.([a, b])}>
              <Flag cc={ca.country} size={13} />{ca.name}
              <span className="vs">vs</span>
              <Flag cc={cb.country} size={13} />{cb.name}
            </button>
          )
        })}
      </div>

      <div className="mapline">
        <span className="sub">
          <b>Where they are.</b> Tap a dot to add it — position is geography, nothing more.
        </span>
        <button className="maptoggle" aria-expanded={mapOpen} onClick={() => setMapOpen((v) => !v)}>
          {mapOpen ? 'hide map' : 'show map'}
        </button>
      </div>
      {mapOpen && (
        <>
          <CityMap
            cities={data.cities}
            countryName={countryName}
            isSelected={sel.has}
            onToggle={toggle}
            query={q}
            matches={matches}
          />
          <p className="mapfoot">
            All {data.cities.length} cities. Dots this close together are nudged apart just enough to
            stay tappable — the list below is the exact geography-free version. Land: Natural Earth.
          </p>
        </>
      )}

      {list}

      <p className="quiet">
        <b>Or start from the field:</b> tap dots on the home page — the cities you pick there are
        already waiting here when you arrive.
      </p>
    </>
  )
}

/** One city, with the two numbers the field leads with: gross mid salary, and
 *  years to a home at mid. A missing figure is named, never dashed. */
function CityCard({ city, on, dim, onToggle }:
  { city: City; on: boolean; dim: boolean; onToggle: () => void }) {
  const y = yearsToHome(city, 'mid')
  const never = isNeverAffordable(city, 'mid')
  const missing = missingInputs(city, 'mid')

  return (
    <button className={`ccard${dim ? ' dim' : ''}`} aria-pressed={on} onClick={onToggle} data-city={city.id}>
      <span className="nm">
        <Flag cc={city.country} size={13} />
        {city.name}
        <i className="ck" aria-hidden="true">✓ added</i>
      </span>
      <span className="nums">
        <span><b>{moneyShort(city.salary_usd_year.mid)}</b><small>mid salary</small></span>
        {never ? (
          <span><b className="nvr-inline">never</b><small>on this salary</small></span>
        ) : y == null ? (
          <span className="nd">no {missing[0] ?? 'purchase-price'} data</span>
        ) : (
          <span><b>{years(y)}</b><small>to a home</small></span>
        )}
      </span>
    </button>
  )
}
