// Package 22, Tier 2 — pure-logic tests for gemini.ts, no network access
// and no API key needed. The real fallback chain, against the live
// Gemini API with a real sample CV and a real prompt-injection attempt,
// was verified directly and is recorded as evidence in REPORT-P22.md —
// not repeated here as an automated test, since that would spend real
// daily quota on every CI run for a check this file's own isValidProfile
// tests already cover without a network call.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { isValidProfile, MODEL_CHAIN, type CvProfile } from '../src/gemini.ts'

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
