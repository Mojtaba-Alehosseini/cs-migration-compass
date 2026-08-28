// Package 22, Tier 1 — stripPii() is the client-side PII removal the work
// order requires before any CV text leaves the browser. Real-shaped
// examples, not synthetic strings chosen to flatter the regexes.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { stripPii } from '../src/cv/stripPii.ts'

test('email is redacted, wherever it appears', () => {
  const { text, redactions } = stripPii('Contact: jane.doe+cv@example.co.uk for details.')
  assert.equal(text, 'Contact: [EMAIL] for details.')
  assert.deepEqual(redactions.map((r) => r.category), ['email'])
})

test('a real http URL and a bare linkedin/github profile are both redacted', () => {
  const { text, redactions } = stripPii(
    'Portfolio: https://janedoe.dev/work\nlinkedin.com/in/janedoe\ngithub.com/janedoe',
  )
  assert.ok(!text.includes('janedoe.dev'))
  assert.ok(!text.includes('linkedin.com'))
  assert.ok(!text.includes('github.com'))
  assert.equal(redactions.filter((r) => r.category === 'url').length, 3)
})

test('a phone number with real-world punctuation is redacted', () => {
  const { text } = stripPii('Mobile: +45 12 34 56 78')
  assert.ok(!text.includes('12 34 56 78'))
  assert.ok(text.includes('[PHONE]'))
})

test('a short digit run that is NOT a phone number survives untouched', () => {
  // "5 years", a section numbered "2.", and a date range must not trip the
  // phone pattern -- it requires 7+ actual digits, not just any digits.
  const { text, redactions } = stripPii('5 years of experience. 2. Senior Engineer, 03/2020 - 06/2023')
  assert.equal(redactions.filter((r) => r.category === 'phone').length, 0)
  assert.ok(text.includes('5 years of experience'))
})

test('a street address line is redacted; ordinary prose with a number is not', () => {
  const { text, redactions } = stripPii(
    '123 Example Street, Springfield\nLed a team of 12 engineers across 3 products',
  )
  assert.ok(text.includes('[ADDRESS]'))
  assert.ok(text.includes('Led a team of 12 engineers'))
  assert.equal(redactions.filter((r) => r.category === 'address').length, 1)
})

test('a US ZIP-shaped token on its own line is redacted', () => {
  const { text } = stripPii('Springfield, IL 62704')
  assert.ok(text.includes('[ADDRESS]'))
})

test('a plausible name on the first line is redacted; a generic header is left alone', () => {
  const withName = stripPii('Jane Doe\nSoftware Engineer\n5 years experience')
  assert.equal(withName.text.split('\n')[0], '[NAME]')
  assert.equal(withName.redactions[0]!.category, 'name')

  const withHeader = stripPii('Curriculum Vitae\nSoftware Engineer')
  assert.equal(withHeader.text.split('\n')[0], 'Curriculum Vitae')
})

test('a job title as the first line is not mistaken for a name', () => {
  // Not 2-4 title-cased words that read as a personal name -- "Senior
  // Backend Engineer" is exactly the kind of false positive the
  // first-line heuristic must not create for every CV that leads with a
  // role instead of a name.
  const { text } = stripPii('Senior Backend Engineer at Acme\nBuilt distributed systems')
  assert.equal(text.split('\n')[0], 'Senior Backend Engineer at Acme')
})

test('every category can be redacted together without interfering', () => {
  const cv = [
    'Jane Doe',
    'jane.doe@example.com | +1 415 555 0100 | linkedin.com/in/janedoe',
    '123 Example Street, Springfield, IL 62704',
    'Software Engineer with 8 years of experience in distributed systems.',
  ].join('\n')
  const { text, redactions } = stripPii(cv)
  assert.ok(text.includes('[NAME]'))
  assert.ok(text.includes('[EMAIL]'))
  assert.ok(text.includes('[PHONE]'))
  assert.ok(text.includes('[URL]'))
  assert.ok(text.includes('[ADDRESS]'))
  assert.ok(text.includes('8 years of experience in distributed systems'))
  const categories = new Set(redactions.map((r) => r.category))
  assert.deepEqual([...categories].sort(), ['address', 'email', 'name', 'phone', 'url'])
})
