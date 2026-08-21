// Package 14 — real unit tests for computeYearSpread(), replacing a false
// "unit-tested" claim an independent adversarial review caught (M6). Run
// with `npm test` (or `node --test tests/`) from site/ — Node 22.6+ strips
// this file's own type annotations natively, no transpile step and no new
// devDependency.
//
// Lives outside src/ deliberately: tsconfig.json's own
// allowImportingTsExtensions is false (correct for the app itself — Vite's
// bundler resolution never wants a literal .ts in an import), but node
// --test's own ESM resolver, unlike tsc/Vite, requires the real extension
// on a relative specifier. Keeping this file out of src/ (tsc's own
// "include") means the two tools' opposite requirements never collide.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { computeYearSpread } from '../src/data/yearSpread.ts'

test('fewer than two rows returns null — no spread to compute', () => {
  assert.equal(computeYearSpread([]), null)
  assert.equal(computeYearSpread([{ country: 'US', year: 2024 }]), null)
})

test('two rows the same year have a zero spread, not null', () => {
  // reduce()'s own strict > / < comparisons keep the FIRST row on a tie
  // for both oldest and newest — both land on US here, not one each.
  const result = computeYearSpread([
    { country: 'US', year: 2024 },
    { country: 'SE', year: 2024 },
  ])
  assert.deepEqual(result, {
    spread: 0,
    oldest: { country: 'US', year: 2024 },
    newest: { country: 'US', year: 2024 },
  })
})

test('real Explore shape — the >3-year caveat this rule exists to trigger', () => {
  // Ireland 2022 vs a 2025 majority — the live gap Tier 2's own module
  // docstring names, before Tier 1's crosswalk fix excludes IE from the
  // comparable set entirely.
  const result = computeYearSpread([
    { country: 'IE', year: 2022 },
    { country: 'US', year: 2025 },
    { country: 'SE', year: 2024 },
  ])
  assert.equal(result?.spread, 3)
  assert.equal(result?.oldest.country, 'IE')
  assert.equal(result?.newest.country, 'US')
})

test('oldest/newest pick the first match on a tie, not an arbitrary one', () => {
  // Two rows share the newest year (2025) — reduce()'s own left-to-right
  // fold must consistently keep the FIRST one seen, not flip between runs.
  const result = computeYearSpread([
    { country: 'US', year: 2025 },
    { country: 'DE', year: 2025 },
    { country: 'IE', year: 2020 },
  ])
  assert.equal(result?.newest.country, 'US')
  assert.equal(result?.oldest.country, 'IE')
})

test('spread is never negative regardless of input order', () => {
  const result = computeYearSpread([
    { country: 'US', year: 2025 },
    { country: 'IE', year: 2018 },
  ])
  assert.equal(result?.spread, 7)
})
