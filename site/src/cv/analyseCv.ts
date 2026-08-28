/* Package 22, Tier 3 — the one fetch call this whole feature makes, to
 * the Worker's /analyse endpoint, carrying the ALREADY-STRIPPED text
 * (extractText.ts + stripPii.ts have both already run by the time this is
 * called) and a Turnstile token. Every failure the Worker can return maps
 * to its own honest UI state — the work order's own explicit list: rate-
 * limited, over cap, upstream failure, malformed input, model unavailable.
 */

// import.meta.env.VITE_CV_WORKER_URL — set at build time, never a secret
// (it is just the Worker's own public URL, the one place this app makes a
// cross-origin call, already named in index.html's own CSP connect-src).
const WORKER_URL = import.meta.env.VITE_CV_WORKER_URL as string | undefined

export interface CvProfile {
  status: 'ok' | 'incomplete'
  occupation: { isco08: string; confidence: 'high' | 'moderate' | 'low'; evidence: string }
  years_professional: number
  skills: string[]
  education_level: string
  languages: string[]
}

export type AnalyseOutcome =
  | { ok: true; profile: CvProfile; modelUsed: string }
  | { ok: false; code: string; message: string }

export async function analyseCv(cvText: string, turnstileToken: string): Promise<AnalyseOutcome> {
  if (!WORKER_URL) {
    return { ok: false, code: 'worker_not_configured', message: 'The CV reader is not configured on this deployment.' }
  }
  let res: Response
  try {
    res = await fetch(`${WORKER_URL}/analyse`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ cvText, turnstileToken }),
      signal: AbortSignal.timeout(45_000),
    })
  } catch {
    return { ok: false, code: 'network_error', message: 'Could not reach the CV reader — check your connection and try again.' }
  }

  let body: unknown
  try {
    body = await res.json()
  } catch {
    return { ok: false, code: 'network_error', message: 'The CV reader returned an unreadable response.' }
  }

  const b = body as Record<string, unknown>
  if (res.ok && b.ok === true) {
    return { ok: true, profile: b.profile as CvProfile, modelUsed: String(b.modelUsed) }
  }
  return {
    ok: false,
    code: typeof b.code === 'string' ? b.code : 'unknown_error',
    message: typeof b.message === 'string' ? b.message : `Request failed (${res.status})`,
  }
}
