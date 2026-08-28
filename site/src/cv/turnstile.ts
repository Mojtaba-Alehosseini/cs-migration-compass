/* Package 22, Tier 3 — loads the Turnstile script and renders one widget,
 * dynamically, behind the same upload flow pdf.js sits behind: a visitor
 * who never opens the CV panel never fetches Cloudflare's script either.
 * The widget itself is what protects the Worker endpoint; this module
 * only manages ITS lifecycle (render, read the token, reset after use —
 * tokens are single-use, and a page that stays open for a retry needs a
 * fresh one, not the same token replayed).
 */

const SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js'
const ACTION = 'cv-analyse' // must match worker/wrangler.jsonc's own TURNSTILE_EXPECTED_ACTION

type TurnstileGlobal = {
  render: (container: HTMLElement, opts: {
    sitekey: string
    action: string
    callback: (token: string) => void
    'error-callback'?: () => void
    'expired-callback'?: () => void
  }) => string
  reset: (widgetId: string) => void
  remove: (widgetId: string) => void
}

declare global {
  interface Window { turnstile?: TurnstileGlobal }
}

let scriptLoadPromise: Promise<TurnstileGlobal> | null = null

function loadTurnstileScript(): Promise<TurnstileGlobal> {
  if (window.turnstile) return Promise.resolve(window.turnstile)
  if (scriptLoadPromise) return scriptLoadPromise
  scriptLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SCRIPT_URL
    script.async = true
    script.defer = true
    script.onload = () => {
      if (window.turnstile) resolve(window.turnstile)
      else reject(new Error('Turnstile script loaded but window.turnstile is not present'))
    }
    script.onerror = () => reject(new Error('Turnstile script failed to load'))
    document.head.appendChild(script)
  })
  return scriptLoadPromise
}

export interface TurnstileHandle {
  /** Resolves with a fresh token each time the widget solves — a
   *  React effect subscribes once and gets called again on every solve,
   *  including after reset(). */
  onToken: (cb: (token: string) => void) => void
  onError: (cb: () => void) => void
  reset: () => void
  remove: () => void
}

/** Renders the widget into `container` and returns a handle. `sitekey` is
 *  the PUBLIC key — safe to pass in from a Vite env var baked into the
 *  bundle, unlike the secret key the Worker alone holds. */
export async function renderTurnstile(container: HTMLElement, sitekey: string): Promise<TurnstileHandle> {
  const turnstile = await loadTurnstileScript()
  let tokenCb: ((token: string) => void) | null = null
  let errorCb: (() => void) | null = null
  const widgetId = turnstile.render(container, {
    sitekey,
    action: ACTION,
    callback: (token) => tokenCb?.(token),
    'error-callback': () => errorCb?.(),
    'expired-callback': () => errorCb?.(),
  })
  return {
    onToken: (cb) => { tokenCb = cb },
    onError: (cb) => { errorCb = cb },
    reset: () => turnstile.reset(widgetId),
    remove: () => turnstile.remove(widgetId),
  }
}
