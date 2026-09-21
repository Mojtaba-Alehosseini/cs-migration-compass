/* NEEDS-DECISION #56 — the parts of the vault that decide what is allowed
 * in, kept in their own module with no `cloudflare:workers` import so they
 * can be tested by plain `node --test`, the way gemini.ts already is.
 *
 * Everything here is a gate. The Durable Object trusts what reaches it, so
 * whatever is wrong has to be wrong before this file returns.
 */

/** Mirrors RETENTION_DAYS in site/src/cv/vault.ts, which is the number the
 *  reader is shown at the consent point. If these two ever disagree, the
 *  site is making a promise the Worker does not keep — test/vault.test.ts
 *  asserts they match. */
export const RETENTION_DAYS = 30

/** The capability token travels here and nowhere else. Never a query
 *  string: a URL reaches browser history, Referer headers, every access log
 *  on the path, and whatever a reader pastes to someone else. */
export const VAULT_KEY_HEADER = 'x-compass-vault-key'

/** 43 base64url characters is exactly 32 unpadded bytes — what
 *  site/src/cv/vault.ts mints from crypto.getRandomValues. Anything else is
 *  refused before it is hashed, which bounds the header and denies a client
 *  the chance to invent a short, guessable "token" of its own. */
export const VAULT_KEY_RE = /^[A-Za-z0-9_-]{43}$/

/** The storage name is the SHA-256 of the token, so the token is never
 *  written down on the server side — not as a Durable Object name, not in
 *  metrics, nowhere a dump would reach. Same reasoning as a password
 *  digest: holding the verifier must not amount to holding the key. */
export async function vaultName(token: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token))
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

export interface StoredProfile {
  occupation: string | null
  yearsProfessional: number
}

/** A CLOSED shape, checked field by field, returning only the two fields it
 *  recognises. The minimum payload is only a minimum if a caller cannot
 *  widen it by sending more — so extra keys are dropped here rather than
 *  reaching storage, and a body that is wrong in any way is refused rather
 *  than coerced. */
export function parseStoredProfile(body: unknown): { ok: true; value: StoredProfile } | { ok: false; message: string } {
  if (typeof body !== 'object' || body === null) return { ok: false, message: 'request body must be a JSON object' }
  const { occupation, yearsProfessional } = body as Record<string, unknown>
  if (occupation != null && (typeof occupation !== 'string' || occupation.length > 64)) {
    return { ok: false, message: 'occupation must be a short string or null' }
  }
  if (typeof yearsProfessional !== 'number' || !Number.isFinite(yearsProfessional)
      || yearsProfessional < 0 || yearsProfessional > 80) {
    return { ok: false, message: 'yearsProfessional must be a number between 0 and 80' }
  }
  return { ok: true, value: { occupation: occupation ?? null, yearsProfessional } }
}
