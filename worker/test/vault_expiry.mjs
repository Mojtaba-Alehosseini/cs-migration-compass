/* #56 · does the retention period actually delete anything?
 * Run against a build whose RETENTION_DAYS is temporarily 3 seconds. */
const BASE = 'http://127.0.0.1:8789/profile'
const H = (token) => ({ Origin: 'http://localhost:4173', 'CF-Connecting-IP': '10.1.0.1', 'x-compass-vault-key': token })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const token = Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString('base64url')

for (let i = 0; i < 40; i++) {
  try { await fetch('http://127.0.0.1:8789/profile', { method: 'GET' }); break } catch { await wait(500) }
}
const save = await (await fetch(BASE, {
  method: 'POST', headers: { ...H(token), 'content-type': 'application/json' },
  body: JSON.stringify({ occupation: 'isco08:2512', yearsProfessional: 7 }),
})).json()
const ttl = save.record.expiresAt - save.record.savedAt
console.log(`saved, ttl = ${ttl}ms`)

const now = await (await fetch(BASE, { headers: H(token) })).json()
console.log(now.record ? 'PASS  before the deadline the record is there' : 'FAIL  it was gone immediately')

await wait(ttl + 2500)
const after = await (await fetch(BASE, { headers: H(token) })).json()
console.log(after.record === null
  ? 'PASS  past the deadline the record is gone, with nothing asked of it but time'
  : `FAIL  still present past its deadline: ${JSON.stringify(after.record)}`)
