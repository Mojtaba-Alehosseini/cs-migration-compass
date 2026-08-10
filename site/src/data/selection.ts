/* One selection, shared by the whole session.
 *
 * Dots tapped on the Home field and cards ticked in the Compare browser are the
 * same list. Before this existed each surface kept its own, so a visitor who
 * picked three cities on the field arrived at Compare and found a default pair
 * they had never chosen.
 *
 * The list is ordered (columns keep the order you added them), deduplicated and
 * capped at six. On Compare the URL is the source of truth — a `?places` deep
 * link wins on mount and the store follows it from then on. Everywhere else the
 * store is simply the session's memory of what you picked.
 *
 * Nothing here sorts, ranks or reorders. `add` appends; that is the whole rule.
 */

import { createContext, useCallback, useContext, useMemo, useState } from 'react'

export const MAX_PLACES = 6

export interface Selection {
  ids: string[]
  /** true once six places are held — the browser dims further cards rather than hiding them. */
  atCap: boolean
  has: (id: string) => boolean
  /** Appends. Returns false when the cap turned it away, so the caller can say why. */
  add: (id: string) => boolean
  remove: (id: string) => void
  /** Adds when absent, removes when present. Returns false only when the cap refused an add. */
  toggle: (id: string) => boolean
  /** Replace the whole list — used by pair buttons and by a `?places` deep link. */
  replace: (ids: string[]) => void
  clear: () => void
}

export const SelectionContext = createContext<Selection | null>(null)

/** Ordered, deduplicated, capped. The one place those three rules live. */
export function normalise(ids: string[]): string[] {
  const out: string[] = []
  for (const id of ids) {
    if (!id || out.includes(id)) continue
    out.push(id)
    if (out.length >= MAX_PLACES) break
  }
  return out
}

export function useSelectionState(): Selection {
  const [ids, setIds] = useState<string[]>([])

  const has = useCallback((id: string) => ids.includes(id), [ids])

  // The cap is read from the render this handler was created in, which is the
  // list the user is looking at — so a refusal and its toast always agree with
  // what is on screen.
  const add = useCallback((id: string) => {
    if (ids.includes(id)) return true
    if (ids.length >= MAX_PLACES) return false
    setIds((cur) => (cur.includes(id) || cur.length >= MAX_PLACES ? cur : [...cur, id]))
    return true
  }, [ids])

  const remove = useCallback((id: string) => {
    setIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur))
  }, [])

  const toggle = useCallback((id: string) => {
    if (ids.includes(id)) { remove(id); return true }
    return add(id)
  }, [ids, add, remove])

  const replace = useCallback((next: string[]) => {
    setIds((cur) => {
      const clean = normalise(next)
      // Same list, same array — so effects that sync the URL do not loop.
      return clean.length === cur.length && clean.every((v, i) => v === cur[i]) ? cur : clean
    })
  }, [])

  const clear = useCallback(() => setIds((cur) => (cur.length ? [] : cur)), [])

  return useMemo(
    () => ({ ids, atCap: ids.length >= MAX_PLACES, has, add, remove, toggle, replace, clear }),
    [ids, has, add, remove, toggle, replace, clear],
  )
}

export function useSelection(): Selection {
  const s = useContext(SelectionContext)
  if (!s) throw new Error('useSelection must be used inside <SelectionProvider>')
  return s
}
