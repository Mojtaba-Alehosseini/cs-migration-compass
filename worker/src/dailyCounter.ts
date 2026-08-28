import { DurableObject } from 'cloudflare:workers'

/** The real spend cap — the work order's own words: "per-IP limits do not
 *  bound aggregate usage." wrangler.jsonc's BURST_LIMITER stops one client
 *  hammering the endpoint; this stops the ACCOUNT'S total daily Gemini
 *  usage from running past what the fallback chain can actually serve,
 *  regardless of how many distinct clients ask.
 *
 *  A SINGLE Durable Object instance (index.ts always calls
 *  `idFromName("global")`, never per-IP or per-day) holds every day's own
 *  row, so "today's count" is one query against one object's own storage —
 *  not an aggregation across many objects, which would need its own
 *  consistency story.
 *
 *  SQLite, not the older KV storage backend, for two reasons the work
 *  order names directly: SQLite is what the work order asks for, and —
 *  more load-bearing — Cloudflare's own SQL API executes synchronously
 *  within one isolate, "and do not yield the event loop, so they execute
 *  atomically without it" (verified against current docs before writing
 *  this). The read-then-write in tryConsume() below has no `await` between
 *  the SELECT and the INSERT/UPDATE, so two requests hitting this same
 *  object cannot interleave and both pass the same under-limit check —
 *  the exact race a naive KV get()-then-put() (both async) would have. */
export class DailyCounter extends DurableObject {
  private sql: SqlStorage

  constructor(ctx: DurableObjectState, env: unknown) {
    super(ctx, env as never)
    this.sql = ctx.storage.sql
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS daily_count (
        day TEXT PRIMARY KEY,
        count INTEGER NOT NULL DEFAULT 0
      )
    `)
  }

  private today(): string {
    return new Date().toISOString().slice(0, 10) // UTC, "YYYY-MM-DD"
  }

  /** Atomically checks today's count against `limit` and, only if under it,
   *  records one more use. Returns the post-check state either way, so the
   *  caller can render "N of LIMIT used today" without a second query. */
  tryConsume(limit: number): { allowed: boolean; count: number; limit: number } {
    const day = this.today()
    // One cheap hygiene sweep per call, not a scheduled alarm — this
    // table gains at most one row per calendar day, so unbounded growth
    // was never a real risk; this just keeps it at exactly one live row.
    this.sql.exec('DELETE FROM daily_count WHERE day != ?', day)

    const row = this.sql
      .exec<{ count: number }>('SELECT count FROM daily_count WHERE day = ?', day)
      .toArray()[0]
    const current = row?.count ?? 0

    if (current >= limit) {
      return { allowed: false, count: current, limit }
    }
    this.sql.exec(
      `INSERT INTO daily_count (day, count) VALUES (?, 1)
       ON CONFLICT(day) DO UPDATE SET count = count + 1`,
      day,
    )
    return { allowed: true, count: current + 1, limit }
  }

  /** Read-only — Tier 4 gate 2 needs to drive the cap to its limit and
   *  observe the refusal without every probe itself counting as a real
   *  analysis attempt. */
  peek(limit: number): { count: number; limit: number } {
    const day = this.today()
    const row = this.sql
      .exec<{ count: number }>('SELECT count FROM daily_count WHERE day = ?', day)
      .toArray()[0]
    return { count: row?.count ?? 0, limit }
  }
}
