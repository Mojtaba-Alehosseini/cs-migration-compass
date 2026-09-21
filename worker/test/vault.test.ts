/* NEEDS-DECISION #56 — the gates the Durable Object trusts.
 *
 * The object itself needs a Workers runtime to exercise, but everything
 * that decides WHAT reaches it is ordinary code, and that is the part where
 * being wrong matters: a token format that accepts a guessable string, a
 * digest that is not a digest, a payload parser that lets a caller widen
 * the minimum payload by sending more than two fields.
 *
 * The mint here is the SAME construction site/src/cv/vault.ts uses, written
 * out rather than imported, so the test fails if either side drifts instead
 * of following it.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  RETENTION_DAYS, VAULT_KEY_HEADER, VAULT_KEY_RE, parseStoredProfile, vaultName,
} from '../src/vaultKey.ts'

function mint(): string {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  let s = ''
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

test('every token the browser mints is accepted, across many draws', () => {
  for (let i = 0; i < 500; i++) {
    const t = mint()
    assert.equal(t.length, 43, `a 32-byte token is 43 base64url chars, got ${t.length}`)
    assert.ok(VAULT_KEY_RE.test(t), `minted token rejected: ${t}`)
  }
})

test('anything shorter, longer or outside base64url is refused before it is hashed', () => {
  const bad = [
    '', 'x', 'a'.repeat(42), 'a'.repeat(44),
    'a'.repeat(42) + '+', 'a'.repeat(42) + '/', 'a'.repeat(42) + '=',
    'a'.repeat(42) + ' ', 'a'.repeat(21) + '\n' + 'a'.repeat(21),
    '../../etc/passwd', 'global', 'vault-writes',
  ]
  for (const b of bad) assert.equal(VAULT_KEY_RE.test(b), false, `should be refused: ${JSON.stringify(b)}`)
})

test('the storage name is a SHA-256 digest of the token, and nothing of the token survives in it', async () => {
  // A published vector, so this asserts the real algorithm rather than
  // whatever the function happens to do.
  assert.equal(
    await vaultName('abc'),
    'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
  )
  const token = mint()
  const name = await vaultName(token)
  assert.match(name, /^[0-9a-f]{64}$/)
  assert.ok(!name.includes(token.slice(0, 8)), 'the digest must not carry the token')
  assert.equal(await vaultName(token), name, 'the same token must always reach the same object')
  assert.notEqual(await vaultName(mint()), name, 'different tokens must reach different objects')
})

test('the payload is a closed shape — extra fields are dropped, never stored', () => {
  const r = parseStoredProfile({
    occupation: 'isco08:2512', yearsProfessional: 7,
    // everything a caller might try to widen the minimum payload with
    cvText: 'Jane Doe, 12 Example Street', evidence: '3 roles titled backend engineer',
    email: 'someone@example.com', salary_eur: 400000, education_level: 'masters',
  })
  assert.ok(r.ok)
  assert.deepEqual(r.value, { occupation: 'isco08:2512', yearsProfessional: 7 })
  assert.deepEqual(Object.keys(r.value), ['occupation', 'yearsProfessional'])
})

test('a missing occupation is a real null, not a coerced empty string', () => {
  const r = parseStoredProfile({ yearsProfessional: 0 })
  assert.ok(r.ok)
  assert.equal(r.value.occupation, null)
  assert.equal(r.value.yearsProfessional, 0)
})

test('an out-of-range or wrong-typed years figure is refused, not clamped', () => {
  for (const y of [-1, 81, NaN, Infinity, '7', null, undefined, {}]) {
    const r = parseStoredProfile({ yearsProfessional: y })
    assert.equal(r.ok, false, `should be refused: ${String(y)}`)
  }
})

test('an occupation long enough to be a payload of its own is refused', () => {
  const r = parseStoredProfile({ occupation: 'x'.repeat(65), yearsProfessional: 5 })
  assert.equal(r.ok, false)
  const ok = parseStoredProfile({ occupation: 'x'.repeat(64), yearsProfessional: 5 })
  assert.equal(ok.ok, true)
})

test('a non-object body is refused rather than treated as an empty profile', () => {
  for (const b of [null, undefined, 'a string', 42, true]) {
    assert.equal(parseStoredProfile(b).ok, false, `should be refused: ${String(b)}`)
  }
})

test('the header name carries no capital letters, so a case-sensitive CORS list cannot miss it', () => {
  assert.equal(VAULT_KEY_HEADER, VAULT_KEY_HEADER.toLowerCase())
})

test('the retention period the Worker enforces is the one the site promises', async () => {
  const { readFile } = await import('node:fs/promises')
  const site = await readFile(new URL('../../site/src/cv/vault.ts', import.meta.url), 'utf8')
  const m = site.match(/export const RETENTION_DAYS = (\d+)/)
  assert.ok(m, 'site/src/cv/vault.ts must declare RETENTION_DAYS')
  assert.equal(
    Number(m[1]), RETENTION_DAYS,
    'the number shown at the consent point must be the number the alarm uses',
  )
})
