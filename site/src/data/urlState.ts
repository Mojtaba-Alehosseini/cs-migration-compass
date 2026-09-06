/* Material state in the address — NEEDS-DECISION #9.
 *
 * Package 33 exercised every control on every route and found all of them
 * material: each changes something a reader sees. A visitor could not send
 * anyone a link to a filtered openings list, a currency-converted view, or a
 * city page on the senior band — the page they were looking at had no address.
 *
 * This is the pattern `/work` already uses (useSearchParams, an update that
 * DELETES a key rather than writing an empty one, `{ replace: true }` so the
 * back button still means "the previous page" and not "the previous
 * keystroke"), extracted so twenty-eight controls do not each reimplement it
 * and drift. #9's own note is the behaviour to preserve: state stays out of the
 * address until it is touched.
 *
 * Two properties this file exists to guarantee:
 *
 *   A default writes NOTHING. A page nobody has touched carries no query
 *   string, so the canonical URL of every route stays what it was and every
 *   link shared before this existed still means the same thing.
 *
 *   An unreadable value falls back rather than breaking. A shared link can
 *   outlive the thing it names — a country drops out of the harvest, a
 *   currency is retired, a city turns out not to have the band the link asks
 *   for. `?country=ZZ` is not an error page; it is the default view, because
 *   the alternative is a link that used to work rendering a crash.
 */
import { useCallback, useMemo } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import type { Budget } from './compute'

/**
 * Write into the query string; a null value removes its key. Pass an object,
 * or a function of the current params when the new value depends on the old
 * one (a base year stepped by an arrow key, a list toggled).
 *
 * Two calls in one tick have to COMPOSE, and this is the reason the function
 * is not a one-liner. Home's question pill changes three things at once —
 * "this question, and drop the second axis that belonged to the last one" —
 * and react-router's own updater hands each call the last COMMITTED params,
 * not the ones the previous call in the same tick queued. Written the obvious
 * way, the last write silently wins and the question never reaches the
 * address at all: the check caught exactly that, `?ask=` missing from a URL
 * whose pill was visibly pressed.
 *
 * `pending` lives at module scope, not in a ref, because the calls that have
 * to compose come from DIFFERENT hooks — `setQi` is a useUrlState, the two it
 * clears are a useUrlFlag and another useUrlState, and each of those calls
 * useUrlPatch itself. A per-hook ref composes a hook with itself and nothing
 * else, which is why the first fix left `?ask=` missing exactly as before.
 *
 * It composes patch with patch, and only that. `/compare`, `/work` and
 * `/position` each also own a direct `setParams` writer that neither reads nor
 * sets `pending`, so a future handler touching both in one tick would lose one
 * write — the very bug this exists to prevent. No handler does today; the
 * limit is recorded here rather than left to be rediscovered.
 *
 * It is keyed on the route and query the write was derived FROM — as a string,
 * not as an object. `useSearchParams` builds a fresh URLSearchParams for every
 * hook instance, so two components looking at one identical location hold two
 * unequal objects; an identity check between them is always false and the
 * composition silently does nothing. That is not a deduction, it is what the
 * probe printed: click one picker and the address said `?hp=CA,DE,GB,AU`,
 * click the second in the same tick and it said `?tp=...` alone.
 *
 * And it is DROPPED on the next microtask, which is the part the key alone got
 * wrong. Keyed only on route-plus-query, a pending `?base=2000` written on one
 * visit to /explore/housing matched the next clean visit to the same route and
 * was replayed onto it — the probe caught a base year the reader never chose
 * riding along in the address. A microtask runs after the synchronous batch
 * that a single click produces and before anything a person can do next, which
 * is exactly the window this is meant to cover.
 */
type Patch = Record<string, string | null>

let pending: { from: string; next: URLSearchParams } | null = null

export function useUrlPatch() {
  const [params, setParams] = useSearchParams()
  const { pathname } = useLocation()

  return useCallback((patch: Patch | ((cur: URLSearchParams) => Patch)) => {
    const from = pathname + '?' + params.toString()
    const base = pending?.from === from ? pending.next : params
    const next = new URLSearchParams(base)
    for (const [k, v] of Object.entries(typeof patch === 'function' ? patch(base) : patch)) {
      if (v == null || v === '') next.delete(k)
      else next.set(k, v)
    }
    pending = { from, next }
    queueMicrotask(() => { pending = null })
    setParams(next, { replace: true })
  }, [params, setParams, pathname])
}

/**
 * One piece of material state, addressable.
 *
 * `valid` is what makes a stale link degrade instead of breaking: a value the
 * page cannot honour is treated as absent. Pass a list where the values are
 * known (a currency, a lens, a band), or a predicate where they are open-ended
 * (a country code that has to exist in this build's data).
 */
export function useUrlState<T extends string>(
  key: string,
  fallback: T,
  valid?: readonly T[] | ((v: string) => boolean),
): [T, (v: T) => void] {
  const [params] = useSearchParams()
  const patch = useUrlPatch()
  const raw = params.get(key)

  const value = useMemo(() => {
    if (raw == null) return fallback
    const ok = typeof valid === 'function' ? valid(raw)
      : valid ? (valid as readonly string[]).includes(raw)
        : true
    return ok ? (raw as T) : fallback
  }, [raw, fallback, valid])

  const set = useCallback((v: T) => patch({ [key]: v === fallback ? null : v }), [patch, key, fallback])
  return [value, set]
}

/** A boolean flag. Present-and-"1" is true; anything else, including a stale
 *  `?remote=yes`, reads as false rather than as an error. */
export function useUrlFlag(key: string, fallback = false): [boolean, (v: boolean) => void] {
  const [params] = useSearchParams()
  const patch = useUrlPatch()
  const raw = params.get(key)
  const value = raw == null ? fallback : raw === '1'
  const set = useCallback((v: boolean) => patch({ [key]: v === fallback ? null : (v ? '1' : '0') }),
    [patch, key, fallback])
  return [value, set]
}

/**
 * A list of short codes, comma-separated — the country and city selections the
 * Explore charts are built from.
 *
 * Unknown members are dropped rather than rejecting the whole list: a link to
 * four countries, one of which has since left the dataset, is still a link to
 * three countries and is more useful than the default. If nothing survives, the
 * default does — an empty chart is not what the sender meant.
 */
export function useUrlList(
  key: string, fallback: readonly string[], valid?: (v: string) => boolean,
): [string[], (v: string[] | ((cur: string[]) => string[])) => void] {
  const [params] = useSearchParams()
  const patch = useUrlPatch()
  const raw = params.get(key)

  const value = useMemo(() => {
    if (raw == null) return [...fallback]
    const kept = raw.split(',').map((s) => s.trim()).filter((s) => s && (!valid || valid(s)))
    return kept.length ? kept : [...fallback]
  }, [raw, fallback, valid])

  /* Accepts an updater as well as a value, because Picker — the site's own
   * multi-select — calls onChange with `(cur) => next`, the way setState does.
   * A setter that only took a value would have compiled at the definition and
   * failed at every call site, which is what the type checker said.
   *
   * The updater is resolved against the ADDRESS, not against this render's
   * `value`. Two picks in quick succession would otherwise both compute from
   * the same stale list and the first would be lost. */
  const set = useCallback((v: string[] | ((cur: string[]) => string[])) => patch((cur) => {
    const next = typeof v === 'function' ? v(readList(cur.get(key), fallback, valid)) : v
    const same = next.length === fallback.length && next.every((x, i) => x === fallback[i])
    return { [key]: same ? null : next.join(',') }
  }), [patch, key, fallback, valid])
  return [value, set]
}

function readList(
  raw: string | null, fallback: readonly string[], valid?: (v: string) => boolean,
): string[] {
  if (raw == null) return [...fallback]
  const kept = raw.split(',').map((s) => s.trim()).filter((s) => s && (!valid || valid(s)))
  return kept.length ? kept : [...fallback]
}

/** A whole number, clamped. A stale `?rows=99999999` becomes the maximum
 *  rather than an attempt to render ninety-nine million rows, and a stale
 *  `?base=1776` becomes the earliest year the data actually covers — the same
 *  view a reader reaches by dragging the handle as far left as it goes. */
export function useUrlNumber(
  key: string, fallback: number, { min, max }: { min: number; max: number },
): [number, (v: number | ((cur: number) => number)) => void] {
  const [params] = useSearchParams()
  const patch = useUrlPatch()
  const read = useCallback((raw: string | null) => {
    /* `Number('')` is 0, which is finite — so an empty `?base=` used to clamp
     * to the minimum and land on 1970 rather than falling back to the default,
     * which is the one behaviour this file's own header promises. Requiring
     * actual digits also refuses `0x7e4`, `1e3` and whitespace-padded values,
     * none of which a key documented as a whole number should quietly accept. */
    if (raw == null || !/^-?\d+$/.test(raw.trim())) return fallback
    return Math.min(max, Math.max(min, Math.trunc(Number(raw))))
  }, [fallback, min, max])
  const value = read(params.get(key))

  /* Held-down arrow keys are why this takes an updater. Ten keydowns arrive
   * before React re-renders once; a setter that computed from this render's
   * `value` moved the base year by one year in total, which is what the check
   * reported — `?base=1991` after ten presses that should have reached 2000. */
  const set = useCallback((v: number | ((cur: number) => number)) => patch((cur) => {
    const next = typeof v === 'function' ? v(read(cur.get(key))) : v
    const clamped = Math.min(max, Math.max(min, Math.trunc(next)))
    return { [key]: clamped === fallback ? null : String(clamped) }
  }), [patch, key, fallback, min, max, read])
  return [value, set]
}

/**
 * A budget — the reader's own rent, living cost, or salary in place of the
 * city's published figures.
 *
 * This is the one piece of state here that changes how numbers are COMPUTED
 * rather than which ones are shown, which is exactly why it belongs in the
 * address: "here is that city on my actual rent" is a thing worth sending,
 * and until now it could not be sent.
 *
 * Encoded compactly — `?b=r:1200,l:800,s:95000` — because the alternative is
 * five keys of boilerplate in a query string a human sometimes reads.
 *
 * Every field is validated on its own and a bad one is dropped rather than
 * failing the whole budget, so `?b=r:1200,l:banana` is a rent override, not a
 * blank page. A value that is not a finite positive number is not a budget
 * figure: zero rent and negative rent both mean the parser misread something,
 * and both would propagate into a division downstream.
 */
const BUDGET_CODEC: ReadonlyArray<readonly [string, keyof Budget]> = [
  ['r', 'rentUsd'], ['l', 'livingUsd'],
  ['rf', 'rentFactor'], ['lf', 'livingFactor'],
  ['s', 'salaryUsdYearOverride'],
]

export function parseBudget(raw: string | null): Budget {
  if (!raw) return {}
  const out: Budget = {}
  for (const part of raw.split(',')) {
    const at = part.indexOf(':')
    if (at < 0) continue
    const entry = BUDGET_CODEC.find(([code]) => code === part.slice(0, at).trim())
    if (!entry) continue
    const n = Number(part.slice(at + 1))
    if (!Number.isFinite(n) || n <= 0) continue
    out[entry[1]] = n
  }
  return out
}

/** A factor of 1 is not a budget — it is the city's own figure, written as a
 *  multiplication by one. The editor's sliders emit it whenever a reader drags
 *  one back to 100%, and writing it would leave `?b=rf:1` in the address of a
 *  page that is computing exactly what an untouched page computes. Absolute
 *  overrides have no such identity value and are always written. */
const IDENTITY: Partial<Record<keyof Budget, number>> = { rentFactor: 1, livingFactor: 1 }

export function formatBudget(b: Budget): string {
  return BUDGET_CODEC
    .map(([code, field]) => {
      const v = b[field]
      return v == null || v === IDENTITY[field] ? null : `${code}:${v}`
    })
    .filter((s): s is string => s != null)
    .join(',')
}

export function useUrlBudget(key = 'b'): [Budget, (b: Budget) => void] {
  const [params] = useSearchParams()
  const patch = useUrlPatch()
  const raw = params.get(key)
  const value = useMemo(() => parseBudget(raw), [raw])
  const set = useCallback((b: Budget) => patch({ [key]: formatBudget(b) || null }), [patch, key])
  return [value, set]
}
