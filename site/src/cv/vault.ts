/* NEEDS-DECISION #56, Tiers 2-4 — identity without accounts, and the three
 * calls that use it.
 *
 * THE TOKEN IS THE IDENTITY. 32 bytes from the platform CSPRNG, base64url,
 * held in this browser's localStorage and sent in a request header. There
 * is no login, no session cookie, no email, and nothing on the server that
 * could be matched back to a person — the Worker stores the profile under
 * the SHA-256 of the token and never sees the token written down.
 *
 * Three consequences, stated rather than discovered:
 *   · Whoever holds the token holds the record. It is a capability, not a
 *     claim about who you are, so it is never put in a URL: a query string
 *     goes into history, into Referer headers, into server logs, and into
 *     whatever a reader pastes to someone else. A header goes into none of
 *     those.
 *   · Lose the browser profile and the record is unreachable. Nobody can
 *     restore it, including the site's owner. It then expires unread.
 *   · It is minted at the MOMENT OF CONSENT and not before. Until the
 *     reader opts in, this browser has no identifier at all — which is the
 *     difference between "we do not track you" and "we track you but do not
 *     call it that".
 */

const KEY_STORAGE = 'compass:vault-key'
const WORKER_URL = import.meta.env.VITE_CV_WORKER_URL as string | undefined

/* PACKAGE 47 — the site never offers to keep what it cannot keep.
 *
 * Whether this build offers storage at all is decided when it is BUILT: the
 * Deploy workflow runs scripts/probe_vault.mjs, a GET /profile with no Origin
 * header, which the vault refuses before its rate limiter or storage is
 * touched and which a Worker without the vault answers with its 404. Nothing
 * is sent from a reader's browser to find out — package 22's second property,
 * that nothing is sent until the reader confirms, would not survive a probe
 * on page load.
 *
 * Only the exact string 'on' turns it on. Unset, empty, 'off', or a probe
 * that errored or timed out: off. Off means no consent line, no saved-profile
 * panel, and every call below refusing before it reaches the network; reading,
 * reviewing and applying a CV work exactly as they did before package 45.
 * Once the Worker is deployed, re-running the Deploy workflow turns it on with
 * no change here. */
export const VAULT_OFFERED = import.meta.env.VITE_CV_VAULT === 'on' && !!WORKER_URL

export interface StoredProfile {
  occupation: string | null
  yearsProfessional: number
}
export interface VaultRecord extends StoredProfile {
  savedAt: number
  expiresAt: number
}
export type VaultOutcome<T> = { ok: true; value: T } | { ok: false; code: string; message: string }

/** Whatever the reader is told at the consent point has to be the number
 *  the Worker actually enforces; this is exported so the copy can read it
 *  from here rather than restating it. It mirrors RETENTION_DAYS in
 *  worker/src/vaultKey.ts, and worker/test/vault.test.ts asserts the two
 *  agree. */
export const RETENTION_DAYS = 30

function b64url(bytes: Uint8Array): string {
  let s = ''
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** localStorage throws rather than returning null in a browser with site
 *  data blocked, and this feature must degrade to "not offered" there, not
 *  to a crash on a page that has nothing to do with CVs. */
function safeGet(): string | null {
  try {
    return localStorage.getItem(KEY_STORAGE)
  } catch {
    return null
  }
}

export function hasKey(): boolean {
  return safeGet() != null
}

/** Called only from the consent handler.
 *
 *  Reports whether it MINTED or found one already there, because the caller
 *  needs to know: a save that fails should drop a key it just created (an
 *  identifier with no purpose) but must not drop one that already existed —
 *  that key is the only route to a record already in the store, and
 *  forgetting it strands that record until its own expiry with nobody able
 *  to read or delete it. An adversarial review found exactly that path.
 *
 *  `fresh: false` with a null token means this browser will not keep one,
 *  so there is nothing to save to. */
export function mintKey(): { token: string | null; fresh: boolean } {
  const existing = safeGet()
  if (existing) return { token: existing, fresh: false }
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  const token = b64url(bytes)
  try {
    localStorage.setItem(KEY_STORAGE, token)
  } catch {
    return { token: null, fresh: false }
  }
  return { token, fresh: true }
}

/** Local only. The record on the server is deleted through `deleteProfile`;
 *  dropping the key without that would leave a record nobody can ever reach
 *  or remove, so the two are always called together — see CvUpload.tsx. */
export function forgetKey(): void {
  try {
    localStorage.removeItem(KEY_STORAGE)
  } catch {
    /* nothing to forget */
  }
}

async function call<T>(method: string, body?: unknown): Promise<VaultOutcome<T>> {
  /* Nothing renders a way here when it is off; this is the floor under that.
   * (VAULT_OFFERED already requires WORKER_URL, so it answers for both.) */
  if (!VAULT_OFFERED) return { ok: false, code: 'vault_not_offered', message: 'Keeping a profile is not offered on this deployment.' }
  const token = safeGet()
  if (!token) return { ok: false, code: 'no_key', message: 'Nothing is saved from this browser.' }
  let res: Response
  try {
    res = await fetch(`${WORKER_URL}/profile`, {
      method,
      headers: {
        'x-compass-vault-key': token,
        ...(body === undefined ? {} : { 'content-type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(15_000),
    })
  } catch {
    return { ok: false, code: 'network_error', message: 'Could not reach the store — check your connection and try again.' }
  }
  let parsed: unknown
  try {
    parsed = await res.json()
  } catch {
    return { ok: false, code: 'network_error', message: 'The store returned an unreadable response.' }
  }
  const b = parsed as Record<string, unknown>
  if (res.ok && b.ok === true) return { ok: true, value: b as T }
  return {
    ok: false,
    code: typeof b.code === 'string' ? b.code : 'unknown_error',
    message: typeof b.message === 'string' ? b.message : `Request failed (${res.status})`,
  }
}

export function saveProfile(p: StoredProfile) {
  return call<{ record: VaultRecord; retentionDays: number }>('POST', p)
}
export function loadProfile() {
  return call<{ record: VaultRecord | null }>('GET')
}
export function deleteProfile() {
  return call<{ had: boolean; gone: boolean }>('DELETE')
}
