// Package 47, NEEDS-DECISION #88 — every /work row per year. The rules under
// test are the ones the card states to a reader: the factor is the
// pipeline's (build_wage_distribution.py's annualise() call), measured hours
// round to three significant figures, a defined multiplier (twelve months,
// Denmark's 37-hour week) does not round, a row the pipeline could not
// convert keeps its published period and says why, and a published-annual
// row passes through untouched. Rows are built by hand with the fields the
// function reads; the numbers are the real 2024-2025 ones from the served
// wage file, so each case reads as the page does.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { estimatePerYear } from '../src/data/perYear.ts'

type Row = Parameters<typeof estimatePerYear>[2]
const row = (period: 'hour' | 'month' | 'year', per_year: unknown): Row =>
  ({ native: { period, per_year } } as unknown as Row)

test('measured hours: Canada, 56.49 an hour x 39.8 x 52, shown to three significant figures', () => {
  const v = estimatePerYear(56.49, 'CAD', row('hour', {
    ok: true, from: 'hour', factor: 2069.6, hours_per_week: 39.8, hours_year: 2024, hours_flag: null,
    hours_scope: 'Statistics Canada, all industries — not the hours of this occupation.', hours_kind: 'measured',
  }))
  assert.equal(v.period, 'year')
  assert.equal(v.value, 117000) // 116,911.70 exact
  assert.match(v.steps[0]!.detail, /56\.49 CAD an hour × 39\.8 hours a week × 52 weeks = 116,912 CAD a year/)
  assert.match(v.steps[0]!.detail, /three significant figures, because the hours are measured to three/)
  assert.match(v.steps[1]!.detail, /^The hours \(2024\): Statistics Canada/)
  assert.equal(v.concept, undefined)
})

test("a defined week: Denmark's 37 hours is exact, so the year is not rounded", () => {
  const v = estimatePerYear(393.81, 'DKK', row('hour', {
    ok: true, from: 'hour', factor: 1924, hours_per_week: 37, hours_year: 2024, hours_flag: null,
    hours_scope: "Danmarks Statistik's own standard full-time week.", hours_kind: 'definition',
  }))
  assert.ok(Math.abs(v.value - 757690.44) < 1e-6)
  assert.match(v.steps[0]!.detail, /= 757,690\.44 DKK a year — the hours are a definition, not a measurement/)
})

test('twelve months: the year is exact, and the card says what twelve months count and leave out', () => {
  const v = estimatePerYear(49672.5, 'SEK', row('month', {
    ok: true, from: 'month', factor: 12, office: 'Statistics Sweden (SCB)',
    counts: "twelve months of SCB's monthly salary", leaves_out: 'overtime pay; a 13th or 14th month',
    citation_url: 'https://www.scb.se/', checked_at_source: '2026-09-24, package 47',
  }))
  assert.equal(v.value, 596070)
  assert.match(v.steps[0]!.detail, /^49,672\.5 SEK a month × 12 = 596,070 SEK a year\./)
  assert.deepEqual(v.concept, {
    name: 'What twelve months of it count',
    office: 'Statistics Sweden (SCB), checked at the source on 2026-09-24',
    includes: "twelve months of SCB's monthly salary",
    excludes: 'overtime pay; a 13th or 14th month',
  })
})

test('twelve months where the office never said what it counts: converted, and the gap stated', () => {
  const v = estimatePerYear(20000, 'QAR', row('month', {
    ok: true, from: 'month', factor: 12, office: 'Qatar PSA', counts: null, leaves_out: null,
    citation_url: null, checked_at_source: null,
  }))
  assert.equal(v.value, 240000)
  assert.equal(v.concept, undefined)
  assert.match(v.steps[1]!.detail, /could not be established at the source/)
})

test('no sourced conversion: the row keeps its published period and says why', () => {
  const v = estimatePerYear(34.8, 'EUR', row('hour', {
    ok: false, from: 'hour', reason: 'no sourced usual-weekly-hours figure for ZZ',
  }))
  assert.equal(v.period, 'hour')
  assert.equal(v.value, 34.8)
  assert.match(v.steps[0]!.detail, /^Not put on a year: no sourced usual-weekly-hours figure for ZZ\. Shown per hour, as published\./)
})

test('an older served file with no per_year at all degrades to the published period, not to a guess', () => {
  const v = estimatePerYear(5100, 'EUR', row('month', undefined))
  assert.equal(v.period, 'month')
  assert.equal(v.value, 5100)
})

test('a published-annual row passes through untouched, with nothing added to its card', () => {
  const v = estimatePerYear(135980, 'USD', row('year', { ok: true, from: 'year', factor: 1 }))
  assert.deepEqual(v, { value: 135980, period: 'year', steps: [] })
})
