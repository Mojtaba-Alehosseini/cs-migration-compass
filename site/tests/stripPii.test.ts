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

test('a decorative divider before the name does not put the name out of reach', () => {
  // Found live: a template that opens with a rule of dashes/bullets left
  // the real name on the SECOND line unredacted, because the first
  // version of this scan stopped at the first non-empty line
  // unconditionally, decorative or not.
  const withDivider = stripPii('=====\nJane Doe\nSoftware Engineer')
  assert.equal(withDivider.text, '=====\n[NAME]\nSoftware Engineer')

  const withBullets = stripPii('• • •\nJane Doe')
  assert.equal(withBullets.text, '• • •\n[NAME]')
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

// Package 23, Gate 1 -- the real leak: a bare "firstname-lastname.github.io"
// (no scheme, no www., not a github.com/ path) went to the model in full
// while the panel claimed the name had been removed.
test('a bare personal domain with no scheme is redacted -- the real leak that shipped', () => {
  const cv = [
    'Jane Doe',
    'DATA SCIENTIST',
    'https://linkedin.com/in/jane-doe · github.com/jane-doe · jane-doe.github.io',
  ].join('\n')
  const { text } = stripPii(cv)
  assert.ok(!/jane-doe/i.test(text), `name survived in: ${text}`)
  assert.ok(!text.includes('jane-doe.github.io'))
})

// Package 23, Gate 11 -- adversarial review found a second real gap of the
// same shape Gate 1 fixed: LinkedIn's own short-link domain, lnkd.in, has
// a TLD (.in) not on BARE_DOMAIN_RE's curated list (adding it generally
// would make the ordinary English word "in" a TLD-match risk), so it is
// special-cased alongside the other known profile hosts instead.
test('LinkedIn\'s own lnkd.in short-link domain is redacted, with or without a path', () => {
  const { text: withPath } = stripPii('Jane Doe\nProfile: lnkd.in/janedoe')
  assert.ok(!withPath.includes('lnkd.in'))
  const { text: bare } = stripPii('Jane Doe\nSee lnkd.in for details')
  assert.ok(!bare.includes('lnkd.in'))
})

test('bare-domain redaction does not eat ordinary technical prose', () => {
  const cv = [
    'Jane Doe',
    '5 years of Node.js and React.js development.',
    '5 years of ASP.NET development, and Python 3.11 experience.',
    'I used React. My next project was different.',
    'Shipped v3.11.2 of the library.',
  ].join('\n')
  const { text } = stripPii(cv)
  assert.ok(text.includes('Node.js'))
  assert.ok(text.includes('React.js'))
  assert.ok(text.includes('ASP.NET'))
  assert.ok(text.includes('Python 3.11'))
  assert.ok(text.includes('React. My next project'))
  assert.ok(text.includes('v3.11.2'))
})

test('a bare domain in a common TLD outside .com/.io still redacts (e.g. .dev, .me, .co.uk)', () => {
  const { text: t1 } = stripPii('Jane Doe\nSee jane-doe.dev for my work.')
  assert.ok(!t1.includes('jane-doe.dev'))
  const { text: t2 } = stripPii('Jane Doe\nPortfolio at janedoe.me')
  assert.ok(!t2.includes('janedoe.me'))
  const { text: t3 } = stripPii('Jane Doe\nContact via example.co.uk please')
  assert.ok(!t3.includes('example.co.uk'))
})

// Package 23, Gate 2 -- once the name is known from its line, every OTHER
// occurrence is swept too, not just the line it was first found on.
test('the name is redacted everywhere it appears, not only on its own line', () => {
  const cv = [
    'Jane Doe',
    'Reach me: jane.doe@company.com',
    'Portfolio: jane-doe.example-hosting.zzz',
    'Slides prepared by JANE DOE, 2026.',
  ].join('\n')
  const { text } = stripPii(cv)
  assert.ok(!/jane/i.test(text), `name survived in: ${text}`)
  assert.ok(!/doe/i.test(text), `name survived in: ${text}`)
  // The domain's own host label is unusual enough (.zzz) that only the
  // name-sweep -- not the bare-domain pattern's own curated TLD list --
  // could have closed it, proving the two fixes are independent layers,
  // not one merely duplicating the other.
  assert.ok(text.includes('.example-hosting.zzz'), 'the non-PII part of the domain should survive')
})

test('a first name alone, with no surname beside it, is still swept', () => {
  const { text } = stripPii('Jane Doe\nData Scientist\n\nJane worked at Acme as a developer.')
  assert.ok(!text.includes('Jane worked'))
  assert.ok(text.includes('worked at Acme as a developer'))
})

test('the redaction count is honest -- a name appearing several times is counted that many times', () => {
  const cv = [
    'Jane Doe',
    'Data Scientist',
    'Contact Jane Doe at jane-doe.example.zzz for more',
    'Slides prepared by JANE DOE, 2026',
  ].join('\n')
  const { redactions } = stripPii(cv)
  // 1 (the name line) + 2 (both occurrences on the "Contact..." line: the
  // plain-text mention and the domain) + 1 (the closing credit line) = 4,
  // not silently collapsed to 1 the way the shipped bug's own panel copy
  // claimed happened.
  const nameCount = redactions.filter((r) => r.category === 'name').length
  assert.equal(nameCount, 4)
})
