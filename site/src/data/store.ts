/* Data loading.
 *
 * core.json is the only blocking fetch — countries, cities, metrics and the
 * precomputed defaults, ~330 KB. Everything historical is lazy and per-source,
 * so a visitor who never opens Explore never downloads BIS or Eurostat.
 */

import { createContext, useContext } from 'react'
import type { Core, HistoryManifestEntry, Provenance } from './types'

const BASE = import.meta.env.BASE_URL

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}data/${path}`)
  if (!res.ok) throw new Error(`Could not load ${path} (HTTP ${res.status})`)
  return (await res.json()) as T
}

export const loadCore = () => getJson<Core>('core.json')
export const loadProvenance = () => getJson<Provenance>('provenance.json')
export const loadManifest = () => getJson<Record<string, HistoryManifestEntry>>('history-manifest.json')

let payCompositionCache: Promise<PayComposition> | null = null

/** data/pay_composition.json, copied verbatim (not through the per-theme
 *  history mechanism — it isn't a time series, it's the <Derived> method
 *  card's own concept-name/includes-excludes/pay-cycle-context source).
 *  Memoised the same way loadHistory() is, since every open method card
 *  fetches it. */
export function loadPayComposition(): Promise<PayComposition> {
  if (!payCompositionCache) payCompositionCache = getJson<PayComposition>('pay_composition.json')
  return payCompositionCache
}

export interface PayComposition {
  sources: {
    source_id: string
    office: string
    concept_name: string
    irregular_bonus: boolean | string
    overtime: boolean | string
    employer_social_contributions: boolean | string
    gross_or_net: string
    separately_published_components: string[]
    note: string
    citation_url: string
    verified_live_this_session: boolean
  }[]
  /** Country/region code -> sourced background prose, e.g. NL/ES/DK/SE/NO/FI/
   *  DE/AU/IT/AE_QA (the two Gulf countries share one entry). '_note' is the
   *  file's own preamble, not a country — skip it when iterating keys. */
  pay_cycle_context: Record<string, string>
}

const historyCache = new Map<string, Promise<unknown>>()

/** Lazily fetch one processed dataset, memoised for the session. */
export function loadHistory<T = unknown>(sourceId: string): Promise<{ data: T; meta: Record<string, unknown> }> {
  const cached = historyCache.get(sourceId)
  if (cached) return cached as Promise<{ data: T; meta: Record<string, unknown> }>
  const p = getJson<{ data: T; meta: Record<string, unknown> }>(`history/${sourceId}.json`)
  historyCache.set(sourceId, p)
  return p
}

export interface Dataset extends Core {
  countryById: Map<string, Core['countries'][number]>
  cityById: Map<string, Core['cities'][number]>
  citiesByCountry: Map<string, Core['cities']>
}

export function indexCore(core: Core): Dataset {
  const countryById = new Map(core.countries.map((c) => [c.id, c]))
  const cityById = new Map(core.cities.map((c) => [c.id, c]))
  const citiesByCountry = new Map<string, Core['cities']>()
  for (const city of core.cities) {
    const list = citiesByCountry.get(city.country) ?? []
    list.push(city)
    citiesByCountry.set(city.country, list)
  }
  // Alphabetical everywhere by default. Any other order is something the user
  // asked for, never something we decided for them.
  for (const list of citiesByCountry.values()) list.sort((a, b) => a.name.localeCompare(b.name))
  return { ...core, countryById, cityById, citiesByCountry }
}

export const DataContext = createContext<Dataset | null>(null)

export function useData(): Dataset {
  const d = useContext(DataContext)
  if (!d) throw new Error('useData must be used inside <DataProvider>')
  return d
}
