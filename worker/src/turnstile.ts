/** Server-side Turnstile verification — the half of Turnstile that actually
 *  protects the endpoint. A widget on the page with no siteverify call
 *  behind it stops nothing; the token is opaque to the client and only
 *  Cloudflare's own siteverify endpoint can say whether it is real.
 *
 *  Checking `success` alone is not enough: the public sitekey is, by
 *  design, visible to anyone who loads the page, so an attacker can run
 *  their OWN Turnstile widget against OUR sitekey on a page THEY control,
 *  solve it there, and replay the resulting (genuinely valid) token here.
 *  `hostname` and `action` are what a replayed token cannot forge — they
 *  are stamped by Cloudflare from where the widget actually ran and what
 *  the page told it it was for, not from anything the client sends. */

const SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

interface SiteverifyResult {
  success: boolean
  action?: string
  hostname?: string
  'error-codes'?: string[]
}

export type TurnstileVerdict =
  | { ok: true }
  | { ok: false; reason: string }

export async function verifyTurnstile(
  token: string,
  secret: string,
  remoteIp: string | null,
  expectedAction: string,
  expectedHostnames: Set<string>,
): Promise<TurnstileVerdict> {
  if (!token || token.length === 0 || token.length > 2048) {
    return { ok: false, reason: 'token missing or malformed' }
  }

  let result: SiteverifyResult
  try {
    const body = new URLSearchParams({ secret, response: token })
    if (remoteIp) body.set('remoteip', remoteIp)
    const r = await fetch(SITEVERIFY_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body,
      signal: AbortSignal.timeout(10_000),
    })
    if (!r.ok) return { ok: false, reason: `siteverify http ${r.status}` }
    result = await r.json()
  } catch {
    // A network failure talking to Cloudflare's own endpoint is not the
    // same claim as "this token is invalid" -- both fail closed (the
    // caller still gets refused) but the caller's own logs get an honest
    // reason, not a fabricated "bad token".
    return { ok: false, reason: 'siteverify unreachable' }
  }

  if (!result.success) {
    return { ok: false, reason: `siteverify rejected: ${(result['error-codes'] ?? []).join(', ') || 'unknown'}` }
  }
  if (result.action !== expectedAction) {
    return { ok: false, reason: `action mismatch (got ${result.action ?? 'none'}, want ${expectedAction})` }
  }
  if (!result.hostname || !expectedHostnames.has(result.hostname)) {
    return { ok: false, reason: `hostname mismatch (got ${result.hostname ?? 'none'})` }
  }
  return { ok: true }
}
