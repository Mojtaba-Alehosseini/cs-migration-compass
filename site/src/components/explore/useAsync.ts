import { useEffect, useState } from 'react'

/** Load once, keep the result, and say so honestly when it fails. A theme that
 *  cannot load its data says which dataset — silence would read as "empty". */
export function useAsync<T>(load: () => Promise<T>, key: string) {
  const [state, setState] = useState<{ data: T | null; error: string | null }>({ data: null, error: null })
  useEffect(() => {
    let alive = true
    setState({ data: null, error: null })
    load()
      .then((data) => { if (alive) setState({ data, error: null }) })
      .catch((e: unknown) => {
        if (alive) setState({ data: null, error: e instanceof Error ? e.message : String(e) })
      })
    return () => { alive = false }
    // `key` identifies the dataset set; `load` is recreated every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return state
}
