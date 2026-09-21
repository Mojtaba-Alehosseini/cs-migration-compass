import { DailyCounter } from './dailyCounter'
import { verifyTurnstile } from './turnstile'
import { errorResponse } from './errors'
import { analyseWithFallback } from './gemini'
import { ProfileVault } from './profileVault'
import { RETENTION_DAYS, VAULT_KEY_HEADER, VAULT_KEY_RE, parseStoredProfile, vaultName } from './vaultKey'

export { DailyCounter, ProfileVault }

export interface Env {
  ALLOWED_ORIGINS: string
  TURNSTILE_EXPECTED_ACTION: string
  TURNSTILE_EXPECTED_HOSTNAMES: string
  DAILY_CV_LIMIT: string
  DAILY_VAULT_WRITE_LIMIT: string
  DAILY_VAULT_READ_LIMIT: string
  GEMINI_API_KEY: string
  TURNSTILE_SECRET_KEY: string
  DAILY_COUNTER: DurableObjectNamespace<DailyCounter>
  PROFILE_VAULT: DurableObjectNamespace<ProfileVault>
  BURST_LIMITER: { limit: (opts: { key: string }) => Promise<{ success: boolean }> }
}

const CORS_METHODS = 'GET, POST, DELETE, OPTIONS'
/* Naming the vault's header here is what makes the browser's preflight
 * allow it; vaultKey.ts says why the token travels in a header at all. */
const CORS_HEADERS = `content-type, ${VAULT_KEY_HEADER}`

/* Number(undefined) is NaN, and `current >= NaN` is false, so a missing or
 * malformed variable made a cap fail OPEN — it would have counted forever
 * and refused nothing. A cap that cannot be read is a cap at its default,
 * never no cap at all. Adversarial review, L4. */
function capOf(v: string | undefined, fallback: number): number {
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

function splitList(v: string): Set<string> {
  return new Set(v.split(',').map((s) => s.trim()).filter(Boolean))
}

/** CORS preflight — a browser sends OPTIONS before the real POST for any
 *  cross-origin request carrying a JSON content-type (not a "simple"
 *  request). Answered from the SAME allow-list `handleAnalyse` checks, so
 *  the two can never disagree about which origins are permitted. */
function handleOptions(request: Request, allowedOrigins: Set<string>): Response {
  const origin = request.headers.get('Origin')
  if (!origin || !allowedOrigins.has(origin)) return new Response(null, { status: 403 })
  return new Response(null, {
    status: 204,
    headers: {
      'access-control-allow-origin': origin,
      'access-control-allow-methods': CORS_METHODS,
      'access-control-allow-headers': CORS_HEADERS,
      'access-control-max-age': '86400',
    },
  })
}

/** POST /analyse. Cheapest and least revealing checks first — Origin, then
 *  input shape, then the local burst brake, THEN Turnstile's own outbound
 *  call, then the daily cap — and every rejection returns before the next
 *  check runs, so a probe against one gate cannot also learn something
 *  about the next one, and an obviously-abusive burst never costs a real
 *  siteverify call. */
async function handleAnalyse(request: Request, env: Env): Promise<Response> {
  const allowedOrigins = splitList(env.ALLOWED_ORIGINS)
  const origin = request.headers.get('Origin')

  // ---- Origin, checked server-side. CORS is a browser convention; curl
  // ignores it, so the enforcement has to happen here, not just in the
  // preflight response above. ----
  if (!origin || !allowedOrigins.has(origin)) {
    return errorResponse('origin_forbidden', 'this origin is not permitted to call this endpoint')
  }

  if (request.method !== 'POST') {
    return errorResponse('malformed_input', 'POST required', origin)
  }

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return errorResponse('malformed_input', 'request body must be JSON', origin)
  }
  if (typeof body !== 'object' || body === null) {
    return errorResponse('malformed_input', 'request body must be a JSON object', origin)
  }
  const { cvText, turnstileToken } = body as Record<string, unknown>
  if (typeof cvText !== 'string' || cvText.length === 0) {
    return errorResponse('malformed_input', 'cvText is required and must be non-empty', origin)
  }
  // Tier 1's own cap is 20,000 characters (see site/src/cv/extractText.ts);
  // this is a second, independent ceiling on the SERVER side — a client
  // that skips the browser step entirely (curl, a modified frontend) must
  // not be able to send more than the UI itself ever would.
  if (cvText.length > 20_000) {
    return errorResponse('malformed_input', 'cvText exceeds the maximum accepted length', origin)
  }
  if (typeof turnstileToken !== 'string' || turnstileToken.length === 0) {
    return errorResponse('turnstile_missing', 'a Turnstile token is required', origin)
  }

  // ---- burst brake, per IP, BEFORE Turnstile deliberately: a cheap local
  // check (no outbound call) that stops rapid repeated requests from each
  // spending a real siteverify call -- Cloudflare's own endpoint, not
  // infinite. Not the real cap -- see dailyCounter.ts for that. Ordering
  // this first also means it's testable on its own, without a genuine
  // Turnstile token, unlike everything below it. ----
  const remoteIp = request.headers.get('CF-Connecting-IP')
  const burstKey = remoteIp ?? 'unknown'
  const burst = await env.BURST_LIMITER.limit({ key: burstKey })
  if (!burst.success) {
    return errorResponse(
      'rate_limited',
      'too many requests from this address in a short window -- wait a minute and try again',
      origin,
    )
  }

  // ---- Turnstile, verified server-side against Cloudflare's own
  // siteverify endpoint -- checks hostname and action, not just success,
  // so a token solved against our public sitekey on an attacker's own page
  // cannot be replayed here (see turnstile.ts's own header). ----
  const verdict = await verifyTurnstile(
    turnstileToken,
    env.TURNSTILE_SECRET_KEY,
    remoteIp,
    env.TURNSTILE_EXPECTED_ACTION,
    splitList(env.TURNSTILE_EXPECTED_HOSTNAMES),
  )
  if (!verdict.ok) {
    return errorResponse('turnstile_failed', verdict.reason, origin)
  }

  // ---- the real spend cap, account-wide, not per IP. ----
  const limit = Number(env.DAILY_CV_LIMIT)
  const counterId = env.DAILY_COUNTER.idFromName('global')
  const consumed = await env.DAILY_COUNTER.get(counterId).tryConsume(limit)
  if (!consumed.allowed) {
    return errorResponse(
      'daily_cap_exceeded',
      `today's analysis budget (${consumed.limit}) is used up -- try again tomorrow`,
      origin,
    )
  }

  // ---- the model call, with its own fallback chain (gemini.ts). Every
  // gate above already passed, so this is the ONE place a real Gemini
  // request happens, spending exactly one real quota unit per genuine
  // analysis request -- not per HTTP request, since none of the checks
  // above reach this line on their own. ----
  const outcome = await analyseWithFallback(cvText, env.GEMINI_API_KEY)
  if (!outcome.ok) {
    const code = outcome.reason === 'all_models_exhausted' ? 'model_unavailable' : 'upstream_failure'
    return errorResponse(code, outcome.detail, origin)
  }

  // profile.status can be "incomplete" here — a genuine, successful model
  // response that says it could not confidently extract a profile, not a
  // Worker-level error. Relayed as-is; Tier 3's own UI is what decides
  // what "incomplete" means for the reader (the work order's own
  // instruction: check status == "incomplete" before parsing).
  return new Response(
    JSON.stringify({
      ok: true,
      profile: outcome.profile,
      // Named explicitly, not just logged server-side: Tier 4 gate 7
      // ("show it moving to the next model, not retrying the exhausted
      // one") needs this visible in the response itself, not inferred.
      modelUsed: outcome.modelUsed,
      dailyUsage: { count: consumed.count, limit: consumed.limit },
    }),
    { status: 200, headers: { 'content-type': 'application/json', 'access-control-allow-origin': origin } },
  )
}

/* ---------------------------------------------------------------- vault ---
 *
 * NEEDS-DECISION #56. Three endpoints over one Durable Object per token:
 * save what the reader confirmed, read it back, delete it. No login, no
 * session, no account — the token IS the identity, and it is minted in the
 * reader's browser at the moment they consent, not before (see
 * site/src/cv/vault.ts).
 *
 * What this side can see: that some holder of some token saved an
 * occupation key and a number. Not who, not from where beyond the IP any
 * HTTP request carries, and not the CV — the file, its extracted text and
 * its stripped text all stay in the browser exactly as package 22 left
 * them. What it cannot do is help a reader who has lost the token: there is
 * nothing to match them against, by design, so the data expires unread.
 */

async function handleVault(request: Request, env: Env): Promise<Response> {
  const allowedOrigins = splitList(env.ALLOWED_ORIGINS)
  const origin = request.headers.get('Origin')
  if (!origin || !allowedOrigins.has(origin)) {
    return errorResponse('origin_forbidden', 'this origin is not permitted to call this endpoint')
  }

  // Same brake as /analyse, on every method: a token is unguessable, but an
  // endpoint is still an endpoint.
  const remoteIp = request.headers.get('CF-Connecting-IP')
  const burst = await env.BURST_LIMITER.limit({ key: remoteIp ?? 'unknown' })
  if (!burst.success) {
    return errorResponse('rate_limited', 'too many requests from this address in a short window -- wait a minute and try again', origin)
  }

  const token = request.headers.get(VAULT_KEY_HEADER)
  if (!token || !VAULT_KEY_RE.test(token)) {
    return errorResponse('malformed_input', `a valid ${VAULT_KEY_HEADER} header is required`, origin)
  }
  const vault = env.PROFILE_VAULT.get(env.PROFILE_VAULT.idFromName(await vaultName(token)))
  /* Every reader hits the same URL and differs only by a header, which is
   * exactly the shape that leaks through a shared cache. Nothing here is
   * cacheable by anyone, and the response varies by the key. L5. */
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json',
      'access-control-allow-origin': origin,
      'cache-control': 'no-store',
      vary: VAULT_KEY_HEADER,
    },
  })

  if (request.method === 'GET') {
    /* Reads get their own account-wide ceiling, separate again from both the
     * Gemini budget and the save budget. DELETE is deliberately NOT capped:
     * refusing a deletion to slow an abuser is a worse outcome than the
     * abuse, and after the read-only fix in profileVault.ts neither GET nor
     * DELETE allocates any storage. */
    const readLimit = capOf(env.DAILY_VAULT_READ_LIMIT, 20000)
    const reads = await env.DAILY_COUNTER.get(env.DAILY_COUNTER.idFromName('vault-reads')).tryConsume(readLimit)
    if (!reads.allowed) {
      return errorResponse('daily_cap_exceeded', `today's read budget (${reads.limit}) is used up -- try again tomorrow`, origin)
    }
    const record = await vault.load()
    return json({ ok: true, record })
  }

  if (request.method === 'DELETE') {
    // Reported from a read, not from the fact that erase() did not throw:
    // "gone" is a claim about the store's state afterwards.
    const had = await vault.exists()
    await vault.erase()
    const still = await vault.exists()
    if (still) return errorResponse('upstream_failure', 'the record could not be deleted', origin)
    return json({ ok: true, had, gone: true })
  }

  if (request.method !== 'POST') {
    return errorResponse('malformed_input', 'GET, POST or DELETE required', origin)
  }

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return errorResponse('malformed_input', 'request body must be JSON', origin)
  }
  const parsed = parseStoredProfile(body)
  if (!parsed.ok) return errorResponse('malformed_input', parsed.message, origin)

  // A daily ceiling on WRITES, counted account-wide in its own object —
  // separate from the Gemini budget, because a save costs no model call and
  // must not be able to eat one.
  const writeLimit = capOf(env.DAILY_VAULT_WRITE_LIMIT, 2000)
  const counter = env.DAILY_COUNTER.get(env.DAILY_COUNTER.idFromName('vault-writes'))
  const consumed = await counter.tryConsume(writeLimit)
  if (!consumed.allowed) {
    return errorResponse('daily_cap_exceeded', `today's save budget (${consumed.limit}) is used up -- try again tomorrow`, origin)
  }

  const record = await vault.save(parsed.value)
  return json({ ok: true, record, retentionDays: RETENTION_DAYS })
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url)
    const allowedOrigins = splitList(env.ALLOWED_ORIGINS)

    if (request.method === 'OPTIONS') return handleOptions(request, allowedOrigins)
    if (url.pathname === '/analyse') return handleAnalyse(request, env)
    if (url.pathname === '/profile') return handleVault(request, env)
    return new Response('not found', { status: 404 })
  },
} satisfies ExportedHandler<Env>
