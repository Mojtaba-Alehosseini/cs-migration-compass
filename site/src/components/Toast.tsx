/* The one-line confirmation the mockup raises for anything that happens off
 * screen: an export that lands in the downloads folder, a link on the
 * clipboard, a seventh city the cap turned away, a comparison cleared.
 *
 * It is a live region rather than an alert, because none of these interrupt —
 * they confirm. It never carries an action, so nothing is lost when it fades. */

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

const ToastContext = createContext<((msg: string) => void) | null>(null)

/** Say one short sentence. Calling again replaces the current message. */
export function useToast() {
  const t = useContext(ToastContext)
  if (!t) throw new Error('useToast must be used inside <ToastHost>')
  return t
}

export function ToastHost({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null)
  const timer = useRef<number>(0)

  const show = useCallback((next: string) => {
    setMsg(next)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setMsg(null), 2600)
  }, [])

  useEffect(() => () => window.clearTimeout(timer.current), [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div aria-live="polite" className="toast-host">
        {msg && <div className="toast" data-testid="toast">{msg}</div>}
      </div>
    </ToastContext.Provider>
  )
}
