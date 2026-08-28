// Package 22, Tier 1 — sortIntoReadingOrder() is the fix for the exact
// failure the work order names: a two-column CV's text items arrive from
// PDF.js in content-stream order, which interleaves the two columns line
// by line once flattened. Tested directly against synthetic positioned
// items (real x/y coordinates a PDF would carry), not through a real PDF
// fixture — this isolates the sorting algorithm itself from pdf.js's own
// browser-only extraction pipeline, which needs a real browser to verify
// (done separately, live, once Tier 3 wires up a real upload).
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { sortIntoReadingOrder, stripInvisibleChars, type PositionedItem } from '../src/cv/extractText.ts'

const item = (str: string, x: number, y: number, height = 10): PositionedItem => ({ str, x, y, height })

test('single column, top to bottom, already in order', () => {
  const items = [
    item('Jane Doe', 50, 750),
    item('Software Engineer', 50, 730),
    item('5 years experience', 50, 710),
  ]
  assert.equal(sortIntoReadingOrder(items), 'Jane Doe\nSoftware Engineer\n5 years experience')
})

test('a two-column layout, interleaved in content-stream order, sorts to left-column-then-right per row', () => {
  // A real two-column CV: left column (skills) and right column (experience)
  // at the SAME row heights, but PDF.js would hand these back in whatever
  // order the content stream drew them -- here deliberately shuffled, not
  // already grouped by column, to prove the sort does the work.
  const items = [
    item('Experience', 300, 750),
    item('Skills', 50, 750),
    item('Senior Engineer, Acme', 300, 720),
    item('Python, Kubernetes', 50, 720),
  ]
  const result = sortIntoReadingOrder(items)
  assert.equal(result, 'Skills Experience\nPython, Kubernetes Senior Engineer, Acme')
})

test('rows are grouped by Y with tolerance, not exact equality', () => {
  // Real PDFs rarely give every item on "one line" the identical baseline
  // -- a font's own ascent/descent quirks produce y values a point or two
  // apart that a human still reads as one row.
  const items = [
    item('Left', 50, 700.0, 10),
    item('Right', 300, 700.6, 10),
  ]
  assert.equal(sortIntoReadingOrder(items), 'Left Right')
})

test('a real gap in Y starts a new row, not a merge', () => {
  const items = [
    item('Line one', 50, 700, 10),
    item('Line two', 50, 685, 10),
  ]
  assert.equal(sortIntoReadingOrder(items), 'Line one\nLine two')
})

test('empty input returns empty text, not a crash', () => {
  assert.equal(sortIntoReadingOrder([]), '')
})

test('stripInvisibleChars removes zero-width and bidi control characters', () => {
  const withZwsp = 'Soft​ware Engineer'
  const withBidi = '‮reversed‬ text'
  assert.equal(stripInvisibleChars(withZwsp), 'Software Engineer')
  assert.equal(stripInvisibleChars(withBidi), 'reversed text')
})

test('stripInvisibleChars leaves ordinary unicode (accents, non-Latin scripts) untouched', () => {
  const text = 'Søren Ørsted — 経験豊富なエンジニア'
  assert.equal(stripInvisibleChars(text), text)
})
