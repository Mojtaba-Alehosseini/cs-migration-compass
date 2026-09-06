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
import { useSearchParams } from 'react-router-dom'

/** Write `patch` into the query string; a null value removes its key. */
export function useUrlPatch() {
  const [, setParams] = useSearchParams()
  return useCallback((patch: Record<string, string | null>) => {
    setParams((cur) => {
      const next = new URLSearchParams(cur)
      for (const [k, v] of Object.entries(patch)) {
        if (v == null || v === '') next.delete(k)
        else next.set(k, v)
      }
      return next
    }, { replace: true })
  }, [setParams])
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
   * failed at every call site, which is what the type checker said. */
  const set = useCallback((v: string[] | ((cur: string[]) => string[])) => {
    const next = typeof v === 'function' ? v(value) : v
    const same = next.length === fallback.length && next.every((x, i) => x === fallback[i])
    patch({ [key]: same ? null : next.join(',') })
  }, [patch, key, fallback, value])
  return [value, set]
}

/** A whole number, clamped. A stale `?rows=99999999` becomes the maximum
 *  rather than an attempt to render ninety-nine million rows. */
export function useUrlNumber(
  key: string, fallback: number, { min, max }: { min: number; max: number },
): [number, (v: number) => void] {
  const [params] = useSearchParams()
  const patch = useUrlPatch()
  const raw = params.get(key)
  const parsed = raw == null ? NaN : Number(raw)
  const value = Number.isFinite(parsed) ? Math.min(max, Math.max(min, Math.trunc(parsed))) : fallback
  const set = useCallback((v: number) => patch({ [key]: v === fallback ? null : String(v) }),
    [patch, key, fallback])
  return [value, set]
}
