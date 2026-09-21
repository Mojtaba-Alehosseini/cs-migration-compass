import { DurableObject } from 'cloudflare:workers'

/** NEEDS-DECISION #56, built in package 45 — the smallest thing that can be
 *  stored and still be worth storing.
 *
 *  ONE Durable Object per capability token, named by the SHA-256 of that
 *  token (index.ts computes the digest; this class never sees the token
 *  itself). So there is no table of users to enumerate, no row that belongs
 *  to a person, and no key that can be recovered from anything this side
 *  keeps: whoever holds the token can reach exactly one object, and nobody
 *  without it can reach any.
 *
 *  What is in it is deliberately two values — the occupation key and the
 *  years figure that the reader confirmed into the form. NOT the file, NOT
 *  the extracted text, NOT the PII-stripped text, and NOT the model's own
 *  `evidence` strings, which are quoted fragments of the CV and would make
 *  this a store of CV text wearing a different name. #56b records the
 *  payload options and what each one would oblige.
 *
 *  Expiry is real, not a policy sentence: `expires_at` is written on every
 *  save and an alarm is set for it. The alarm deletes. A read past the
 *  deadline also deletes and reports nothing, so a missed alarm cannot turn
 *  into indefinite retention.
 *
 *  SQLite for the same reason dailyCounter.ts gives: the SQL API runs
 *  synchronously within the isolate, so the read-check-write in `load()`
 *  cannot interleave with another request against the same object.
 */

import { RETENTION_DAYS, type StoredProfile } from './vaultKey'

export interface VaultRecord extends StoredProfile {
  savedAt: number
  expiresAt: number
}

export class ProfileVault extends DurableObject {
  private sql: SqlStorage

  constructor(ctx: DurableObjectState, env: unknown) {
    super(ctx, env as never)
    this.sql = ctx.storage.sql
    this.ensure()
  }

  /** `erase()` calls `deleteAll()`, which drops the table with everything
   *  else. If the isolate survives the delete — the common case, since the
   *  same request usually reads back to prove the deletion — the next query
   *  would hit a table that no longer exists. So every entry point starts
   *  here rather than trusting the constructor to have been the last thing
   *  that touched storage. */
  private ensure(): void {
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        occupation TEXT,
        years REAL NOT NULL,
        saved_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL
      )
    `)
  }

  /** Replaces whatever was there. A save is not a merge: the reader is
   *  storing the profile they just confirmed, not amending an older one
   *  they can no longer see. */
  async save(p: StoredProfile): Promise<VaultRecord> {
    this.ensure()
    const now = Date.now()
    const expiresAt = now + RETENTION_DAYS * 86_400_000
    this.sql.exec(
      `INSERT INTO profile (id, occupation, years, saved_at, expires_at) VALUES (1, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET occupation = excluded.occupation, years = excluded.years,
         saved_at = excluded.saved_at, expires_at = excluded.expires_at`,
      p.occupation, p.yearsProfessional, now, expiresAt,
    )
    await this.ctx.storage.setAlarm(expiresAt)
    return { ...p, savedAt: now, expiresAt }
  }

  async load(): Promise<VaultRecord | null> {
    this.ensure()
    const row = this.sql
      .exec<{ occupation: string | null; years: number; saved_at: number; expires_at: number }>(
        'SELECT occupation, years, saved_at, expires_at FROM profile WHERE id = 1',
      )
      .toArray()[0]
    if (!row) return null
    if (row.expires_at <= Date.now()) {
      // Past the deadline and still here — the alarm has not run or did not
      // survive. Delete now rather than serve it: the retention period the
      // reader was shown is the promise, not the alarm's reliability.
      await this.erase()
      return null
    }
    return {
      occupation: row.occupation, yearsProfessional: row.years,
      savedAt: row.saved_at, expiresAt: row.expires_at,
    }
  }

  /** Deletes the object's whole storage, not just the row — after this
   *  there is nothing left in it to read, including the alarm. Idempotent,
   *  so a reader who deletes twice gets the same honest answer both times. */
  async erase(): Promise<void> {
    await this.ctx.storage.deleteAlarm()
    await this.ctx.storage.deleteAll()
  }

  /** Does this object hold anything at all? Used by the delete endpoint to
   *  answer "was there something, and is it gone now" truthfully rather
   *  than reporting success for a token that never had a record. */
  async exists(): Promise<boolean> {
    return (await this.load()) != null
  }

  async alarm(): Promise<void> {
    await this.erase()
  }
}
