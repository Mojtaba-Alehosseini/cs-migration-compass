/** Every failure this Worker can produce, named once. The UI renders each
 *  `code` as its own honest state (Tier 3's own requirement) -- a generic
 *  "something went wrong" collapses "you're over today's cap, try tomorrow"
 *  and "the model is down, try again" into copy that tells the reader
 *  nothing useful for either. */
export type ErrorCode =
  | 'origin_forbidden'
  | 'turnstile_missing'
  | 'turnstile_failed'
  | 'rate_limited'
  | 'daily_cap_exceeded'
  | 'malformed_input'
  | 'upstream_failure'
  | 'model_unavailable'

const STATUS: Record<ErrorCode, number> = {
  origin_forbidden: 403,
  turnstile_missing: 403,
  turnstile_failed: 403,
  rate_limited: 429,
  daily_cap_exceeded: 429,
  malformed_input: 400,
  upstream_failure: 502,
  model_unavailable: 503,
}

export interface AnalyseErrorBody {
  ok: false
  code: ErrorCode
  message: string
}

/** A JSON error response with the right status for `code` and a CORS header
 *  scoped to the ONE origin that made this request -- never a wildcard,
 *  and never echoing back an origin that failed validation. */
export function errorResponse(code: ErrorCode, message: string, allowOrigin?: string): Response {
  const body: AnalyseErrorBody = { ok: false, code, message }
  const headers: Record<string, string> = { 'content-type': 'application/json' }
  if (allowOrigin) headers['access-control-allow-origin'] = allowOrigin
  return new Response(JSON.stringify(body), { status: STATUS[code], headers })
}
