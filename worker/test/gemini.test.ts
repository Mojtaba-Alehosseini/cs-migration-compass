// Package 22, Tier 2 — pure-logic tests for gemini.ts, no network access
// and no API key needed. The real fallback chain, against the live
// Gemini API with a real sample CV and a real prompt-injection attempt,
// was verified directly and is recorded as evidence in REPORT-P22.md —
// not repeated here as an automated test, since that would spend real
// daily quota on every CI run for a check this file's own isValidProfile
// tests already cover without a network call.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { isValidProfile, MODEL_CHAIN, analyseWithFallback, type CvProfile } from '../src/gemini.ts'

const VALID: CvProfile = {
  status: 'ok',
  occupation: { isco08: '2512', confidence: 'high', evidence: 'three roles titled engineer' },
  years_professional: 6,
  skills: ['python', 'kubernetes'],
  education_level: 'masters',
  languages: ['en', 'da-basic'],
}

test('a well-formed profile validates', () => {
  assert.equal(isValidProfile(VALID), true)
})

test('status must be exactly "ok" or "incomplete"', () => {
  assert.equal(isValidProfile({ ...VALID, status: 'done' }), false)
})

test('a missing occupation field is rejected, not defaulted', () => {
  const { occupation: _occupation, ...rest } = VALID
  assert.equal(isValidProfile(rest), false)
})

test('years_professional must be a number, not a numeric string', () => {
  assert.equal(isValidProfile({ ...VALID, years_professional: '6' }), false)
})

test('skills must be an array of strings, not a comma-joined string', () => {
  assert.equal(isValidProfile({ ...VALID, skills: 'python, kubernetes' }), false)
  assert.equal(isValidProfile({ ...VALID, skills: [1, 2] }), false)
})

test('a pay-shaped field appearing anywhere does not change validity either way', () => {
  // The real defense is structural (the schema sent TO the model has no
  // such field at all, so nothing well-formed can even name one) -- this
  // just confirms isValidProfile() does not accidentally start requiring
  // or specially handling one if a future edit ever adds it by mistake.
  const withExtra = { ...VALID, salary_eur: 400000 }
  assert.equal(isValidProfile(withExtra), true) // extra fields don't invalidate
})

test('MODEL_CHAIN starts with the two 500-RPD Lite models before any 20-RPD model', () => {
  assert.deepEqual(MODEL_CHAIN.slice(0, 2), ['gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'])
})

test('MODEL_CHAIN never repeats a model', () => {
  assert.equal(new Set(MODEL_CHAIN).size, MODEL_CHAIN.length)
})

test('Gemma is not in the chain — GEMINI-LIMITS.md rules it out for CV text (16K TPM)', () => {
  assert.equal(MODEL_CHAIN.some((m) => m.includes('gemma')), false)
})

// Gate 7 — "the fallback chain fires... show it moving to the next model
// rather than retrying the exhausted one." A mocked fetch, not a live
// call burning real daily quota to NATURALLY trigger a 429 (which would
// mean deliberately exhausting the primary model, the opposite of what
// this account's own quota discipline is for) — this tests the ACTUAL
// decision logic in analyseWithFallback() directly: on 429, advance
// exactly one model, do not re-call the one that just failed.
function mockGeminiResponse(profile: CvProfile): Response {
  const body = { candidates: [{ content: { parts: [{ text: JSON.stringify(profile) }] } }] }
  return new Response(JSON.stringify(body), { status: 200 })
}

test('on a 429 from the primary model, the SECOND model in the chain answers — not a retry of the first', async () => {
  const calls: string[] = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input)
    calls.push(url)
    if (url.includes(MODEL_CHAIN[0])) return new Response('rate limited', { status: 429 })
    if (url.includes(MODEL_CHAIN[1])) return mockGeminiResponse(VALID)
    throw new Error(`unexpected model called: ${url}`)
  }) as typeof fetch
  try {
    const outcome = await analyseWithFallback('some cv text', 'fake-key-for-this-test')
    assert.equal(outcome.ok, true)
    if (outcome.ok) assert.equal(outcome.modelUsed, MODEL_CHAIN[1])
    // Exactly one call per model, in chain order — not a retry of the
    // first model after its own 429.
    assert.equal(calls.filter((c) => c.includes(MODEL_CHAIN[0])).length, 1)
    assert.equal(calls.filter((c) => c.includes(MODEL_CHAIN[1])).length, 1)
    assert.equal(calls.length, 2)
  } finally {
    globalThis.fetch = originalFetch
  }
})

// Package 23, Gate 4 — the request body actually carries the determinism
// settings, not just the comment claiming it does. Five real runs against
// the live API (REPORT-P23.md) proved the OUTCOME; this proves the CODE
// PATH that outcome depends on, without spending quota on every CI run.
test('the request to the model pins temperature, topP, topK and seed for determinism', async () => {
  let capturedBody: Record<string, unknown> | null = null
  const originalFetch = globalThis.fetch
  globalThis.fetch = (async (_input: RequestInfo | URL, init?: RequestInit) => {
    capturedBody = JSON.parse(String(init?.body))
    return mockGeminiResponse(VALID)
  }) as typeof fetch
  try {
    await analyseWithFallback('some cv text', 'fake-key-for-this-test')
    const config = (capturedBody as { generationConfig?: Record<string, unknown> } | null)
      ?.generationConfig
    assert.equal(config?.temperature, 0)
    assert.equal(config?.topP, 1)
    assert.equal(config?.topK, 1)
    assert.equal(config?.seed, 42)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('429s all the way down the chain produce a distinguishable "all models exhausted" outcome', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = (async () => new Response('rate limited', { status: 429 })) as typeof fetch
  try {
    const outcome = await analyseWithFallback('some cv text', 'fake-key-for-this-test')
    assert.equal(outcome.ok, false)
    if (!outcome.ok) assert.equal(outcome.reason, 'all_models_exhausted')
  } finally {
    globalThis.fetch = originalFetch
  }
})
