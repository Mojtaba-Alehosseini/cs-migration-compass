/* Explore · Money's wage-distribution panel — package 9, tier 6.
 *
 * Every number here is DERIVED (converted, annualised, sometimes a component
 * subtracted), so every number opens a <Derived> method card, never a bare
 * figure — the same "no cryptic caption" principle <Figure> holds for sourced
 * numbers, extended to calculated ones.
 *
 * Two independent axes of degradation can affect a row, and both are named
 * plainly rather than hidden:
 *   - occupation-crosswalk depth (crosswalk.compare(), resolved at build time
 *     in scripts/build_wage_distribution.py — Ireland/Qatar/UAE compare only
 *     at 1-digit ISCO major-group depth, Spain at 2-digit)
 *   - pay-composition basis (normalise.comparison_basis()) — five countries
 *     (US/UK/Norway/Australia/Spain) publish a figure that already includes
 *     bonuses and cannot be split into a bonus-excluded "regular pay" figure,
 *     so they are absent specifically on that toggle state, not always
 *   - Canada (both NOC codes) and Qatar/UAE have UNVERIFIED composition
 *     (pay_composition.json's own fields say "unknown") and are therefore
 *     absent on EVERY toggle state — an honest consequence of not having
 *     verified something, not a bug.
 * Switching either segment control visibly changes which rows have a bar and
 * which are a dashed, labelled absence — the interaction itself is the
 * disclosure the owner asked for ("calculate it, but tell users in detail
 * why and how — not at first glance").
 */

import { useMemo, useState } from 'react'
import { Derived } from '../Derived'
import { Seg, ChartFoot, ChartTable, Gap } from './Controls'
import { useAsync } from './useAsync'
import { loadPayComposition } from '../../data/store'
import { comboKey, type Basis, type CurrencyMode, type WageCountry, type WageDistribution } from '../../data/explore'
import { NO_DATA } from '../../data/format'

const cc3 = (c: string) => `var(--c-${c})`

/** Currency-aware, matching format.ts's "null never formats as a number"
 *  rule — format.ts's own money()/moneyShort() are USD-only (Intl
 *  NumberFormat pinned to 'currency: USD'), and this panel shows thirteen
 *  different native currencies as well as USD. */
const fmtCcy = (v: number | null, currency: string, compact = false): string => {
  if (v == null || !Number.isFinite(v)) return NO_DATA
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency, maximumFractionDigits: 0,
      notation: compact ? 'compact' : 'standard',
    }).format(v)
  } catch {
    return `${Math.round(v).toLocaleString()} ${currency}`
  }
}

/** "CA-21231" -> { iso: "CA", suffix: "21231" }; every other row has no suffix. */
function splitRow(country: string): { iso: string; suffix: string | null } {
  const [iso, suffix] = country.split('-')
  return { iso: iso!, suffix: suffix ?? null }
}

const ROW_LABEL: Record<string, string> = {
  'CA-21231': 'Software engineers & designers', 'CA-21232': 'Software developers & programmers',
}

/** A short, chart-safe label for why a row has no bar — the resolver's own
 *  `reason` strings are written for REPORT-P9.md and the CSV export (full
 *  sentences, citing pay_composition.json), too long for an inline SVG
 *  annotation. The full reason is still there, in the row's <title> tooltip. */
function shortAbsence(basis: Basis, reason: string): string {
  if (reason.includes('share no common basis')) return 'composition not verified'
  if (reason.includes('does not publish enough')) {
    return basis === 'regular_pay' ? 'no bonus-excluded figure published' : 'no total-earnings figure published'
  }
  return 'not available on this basis'
}

function degradationNote(row: WageCountry): string | null {
  const cw = row.crosswalk
  if (!cw.comparable) return `not compared — ${cw.reason}`
  if (!cw.degraded_by) return null
  return `${cw.depth}-digit match only (${cw.degraded_by})`
}

export function WagePanel({ wages }: { wages: WageDistribution }) {
  const { data: payComp } = useAsync(loadPayComposition, 'pay_composition')
  const [currency, setCurrency] = useState<CurrencyMode>('native')
  const [basis, setBasis] = useState<Basis>('regular_pay')

  const key = comboKey(currency, basis)
  // crosswalk.compare() ruling comparable:false (the Netherlands: zero ISCO-08
  // correspondence at any depth) means this occupation genuinely cannot be
  // placed alongside the isco08:2512 reference — excluded from the chart
  // itself, not just flagged like the 1-/2-digit-degraded rows are. Its real
  // data still reaches the country page (CountryProfile.tsx reads
  // wages.countries directly, unfiltered).
  const uncomparable = useMemo(() => wages.countries.filter((c) => !c.crosswalk.comparable), [wages])
  const rows = useMemo(() => {
    return wages.countries.filter((c) => c.crosswalk.comparable).sort((a, b) => {
      const av = a.combos[key], bv = b.combos[key]
      const am = av?.ok ? (av.value.median ?? av.value.mean ?? -1) : -1
      const bm = bv?.ok ? (bv.value.median ?? bv.value.mean ?? -1) : -1
      return bm - am
    })
  }, [wages, key])

  const W = 700, ROW = 40, PL = 190, PR = 60, TOP = 34
  const H = TOP + rows.length * ROW + 30

  // A shared numeric x-axis is only honest when every row is in the SAME
  // unit. In USD mode it is. In native mode it is not — Sweden's 53,500 and
  // the UK's 55,587 are SEK and GBP, nowhere near the same real value, and
  // plotting them at nearly the same x position (worse, under axis ticks
  // that an earlier version of this file labelled in USD regardless of mode)
  // would imply a comparison that does not exist. So native mode draws no
  // bar and no axis at all — just each row's own number, in its own
  // currency, as text. Only usd mode gets the comparable range chart.
  const canCompare = currency === 'usd'

  const domainMax = useMemo(() => {
    if (!canCompare) return 100
    let max = 0
    for (const r of rows) {
      const combo = r.combos[key]
      if (combo?.ok) max = Math.max(max, combo.value.p90 ?? combo.value.mean ?? combo.value.median ?? 0)
    }
    return max > 0 ? max * 1.08 : 100
  }, [rows, key, canCompare])
  const X = (v: number) => PL + (v / domainMax) * (W - PL - PR)

  // Dev-time injectivity check on this panel's own hand-built tick labels —
  // this axis's domain is COMPUTED (varies with the selected combo), unlike
  // most of this file's fixed-label axes, so it is the one most likely to
  // ever produce two ticks reading the same thing. Only meaningful in USD
  // mode — native mode draws no axis (see canCompare above).
  const ticks = useMemo(() => {
    if (!canCompare) return []
    const steps = 4
    const out: [number, string][] = []
    for (let i = 1; i <= steps; i++) {
      const v = (domainMax / 1.08) * (i / steps)
      out.push([v, fmtCcy(v, 'USD', true)])
    }
    return out
  }, [domainMax, canCompare])
  if (import.meta.env.DEV && canCompare) {
    const labels = ticks.map(([, l]) => l)
    if (new Set(labels).size !== labels.length) {
      throw new Error(`WagePanel: x-axis ticks are not injective — ${JSON.stringify(labels)}`)
    }
  }

  const csvRows = rows.map((r) => {
    const combo = r.combos[key]
    return {
      country: r.country, source: r.source_id, comparable: r.crosswalk.comparable,
      currency: combo?.ok ? combo.currency : null,
      p10: combo?.ok ? combo.value.p10 : null, median: combo?.ok ? combo.value.median : null,
      p90: combo?.ok ? combo.value.p90 : null,
      absence_reason: combo?.ok ? null : (combo as { reason: string } | undefined)?.reason ?? null,
    }
  })

  return (
    <div className="panel s6">
      <h2>What the same job actually pays, country by country</h2>
      <div className="sub">
        The primary software-developer occupation in each country's own classification, matched by{' '}
        <a href="#/data">crosswalk</a> to the deepest shared ISCO-08 code both sides support. Switch the
        toggles — a row that disappears is a row that cannot honestly express what you just asked for,
        named below it, not hidden.
      </div>
      <div className="crail">
        <Seg label="Currency" value={currency}
          options={[['native', 'native currency'], ['usd', 'US dollars']]} onChange={setCurrency} />
        <Seg label="Pay basis" value={basis}
          options={[['regular_pay', 'regular pay'], ['total_earnings', 'total earnings']]} onChange={setBasis} />
      </div>

      {!canCompare && (
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 4 }}>
          Native currency: each row is its own currency, so bar position would compare numbers that
          aren't comparable — switch to US dollars to see them on one scale.
        </p>
      )}
      <div className="chart">
        <svg viewBox={`0 0 ${W} ${H}`} role="img"
          aria-label={`Software-developer pay distribution by country, ${currency} ${basis.replace('_', ' ')}`}>
          {canCompare && ticks.map(([v, l]) => (
            <g key={l}>
              <line x1={X(v)} x2={X(v)} y1={TOP - 10} y2={H - 22} className="gridline" />
              <text x={X(v)} y={H - 8} fontSize="10" fill="var(--ink-3)" textAnchor="middle">{l}</text>
            </g>
          ))}
          {rows.map((r, i) => {
            const y0 = TOP + i * ROW + 10
            const { iso, suffix } = splitRow(r.country)
            const col = cc3(iso)
            const combo = r.combos[key]
            const label = ROW_LABEL[r.country] ?? iso
            const note = degradationNote(r)

            return (
              <g key={r.country}>
                <text x={PL - 10} y={y0 + 4} fontSize="10.5" fontWeight={suffix ? 400 : 600}
                  fill={col} textAnchor="end">
                  {iso}{suffix ? ` · ${label}` : ''}
                </text>
                {combo?.ok ? (
                  canCompare ? (
                    <WageRow x={X} y={y0} value={combo.value} color={col} />
                  ) : (
                    <text x={PL} y={y0 + 3.5} fontSize="10" fill={col}>
                      {fmtCcy(combo.value.median ?? combo.value.mean, combo.currency)}
                      {combo.value.p10 != null && combo.value.p90 != null
                        ? ` (${fmtCcy(combo.value.p10, combo.currency)}–${fmtCcy(combo.value.p90, combo.currency)})`
                        : combo.value.p25 != null && combo.value.p75 != null
                          ? ` (${fmtCcy(combo.value.p25, combo.currency)}–${fmtCcy(combo.value.p75, combo.currency)}, p25–p75)`
                          : ''}
                    </text>
                  )
                ) : (
                  <>
                    <line x1={PL} x2={PL + 30} y1={y0} y2={y0} stroke="var(--ink-3)" strokeWidth={1.5}
                      strokeDasharray="2 3" opacity={0.6} />
                    <text x={PL + 36} y={y0 + 3.5} fontSize="9.5" fill="var(--ink-3)" fontStyle="italic">
                      {combo && 'reason' in combo ? shortAbsence(basis, combo.reason) : 'not available'}
                      {combo && 'reason' in combo && <title>{combo.reason}</title>}
                    </text>
                  </>
                )}
                {note && canCompare && (
                  <text x={X(domainMax / 1.08) + 4} y={y0 + 3.5} fontSize="9" fill="var(--ink-3)">{note}</text>
                )}
                {note && !canCompare && (
                  <text x={W - PR} y={y0 + 3.5} fontSize="9" fill="var(--ink-3)" textAnchor="end">{note}</text>
                )}
              </g>
            )
          })}
        </svg>
      </div>

      {rows.some((r) => r.combos[key]?.ok) && payComp && (
        <div style={{ marginTop: 6, fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
          Tap a row's number for the full method — every figure here is calculated, not published as-is.{' '}
          {rows
            .filter((r) => r.combos[key]?.ok)
            .slice(0, 1)
            .map((r) => {
              const combo = r.combos[key]!
              if (!combo.ok) return null
              const comp = payComp.sources.find((s) => s.source_id === r.source_id)
              return (
                <Derived key={r.country} chain={combo.chain}
                  native={{ value: r.native.value.median ?? r.native.value.mean ?? 0,
                    currency: r.native.currency, period: r.native.period, year: r.native.year }}
                  concept={comp ? {
                    name: comp.concept_name, office: comp.office,
                    includes: typeof comp.irregular_bonus === 'string' ? comp.irregular_bonus
                      : comp.irregular_bonus ? 'irregular bonus' : undefined,
                    excludes: comp.employer_social_contributions === false ? 'employer social contributions' : undefined,
                  } : undefined}>
                  example: {r.country}'s own chain →
                </Derived>
              )
            })}
        </div>
      )}

      <ChartFoot csv={{ name: `compass-wages-${currency}-${basis}.csv`, rows: csvRows }}>
        <span className="chip chip-ok">● Official · national statistical offices</span>
        <span className="chip chip-quiet">
          {rows.filter((r) => !r.combos[key]?.ok).length} of {rows.length} rows not shown for this
          toggle — see the dashed reason beside each
        </span>
      </ChartFoot>

      <ChartTable
        caption="Wage distribution by country — the numbers behind this chart"
        head={['Country', 'Currency', 'P10', 'Median', 'P90', 'Comparable']}
        rows={rows.map((r) => {
          const combo = r.combos[key]
          return [
            r.country,
            combo?.ok ? combo.currency : NO_DATA,
            combo?.ok ? fmtCcy(combo.value.p10, combo.currency) : NO_DATA,
            combo?.ok ? fmtCcy(combo.value.median, combo.currency) : NO_DATA,
            combo?.ok ? fmtCcy(combo.value.p90, combo.currency) : NO_DATA,
            r.crosswalk.comparable ? `${r.crosswalk.depth}-digit` : 'no',
          ]
        })}
      />

      {(wages.absent.length > 0 || uncomparable.length > 0) && (
        <Gap title={`${wages.absent.length + uncomparable.length} countries don't appear in this chart`} span="s6"
          where={<>Full account in <a href="#/data">NEEDS-DECISION.md →</a></>}>
          <p>
            {wages.absent.map((a, i) => (
              <span key={a.country}>
                {i > 0 && '; '}<b>{a.country}</b> — {a.reason.split(' — ')[0]}
              </span>
            ))}
            {uncomparable.map((c) => (
              <span key={c.country}>
                {(wages.absent.length > 0 || c !== uncomparable[0]) && '; '}
                <b>{c.country}</b> — has real data (see its <a href={`#/country/${c.country}`}>country page</a>),
                but no ISCO-08 correspondence at any depth to compare it against
              </span>
            ))}. Absence drawn, not implied by a missing row.
          </p>
        </Gap>
      )}
    </div>
  )
}

/** Three tiers, each drawing exactly what the source actually published —
 *  never widening a partial spread to look like a full one, never collapsing
 *  a real box down to a point just because the outer whiskers are missing
 *  (Denmark and Norway publish p25/median/p75 but not p10/p90; an earlier
 *  version of this component treated that the same as "no spread at all"
 *  and drew a bare dot, discarding two real published numbers — caught by
 *  reading this panel's own rendered output against the source data, not
 *  assumed correct because it compiled). */
function WageRow({ x, y, value, color }: {
  x: (v: number) => number; y: number
  value: { mean: number | null; median: number | null; p10: number | null; p25: number | null; p75: number | null; p90: number | null }
  color: string
}) {
  const { p10, p25, median, p75, p90, mean } = value
  const medianTick = median != null && (
    <line x1={x(median)} x2={x(median)} y1={y - 6} y2={y + 6} stroke={color} strokeWidth={2.4} />
  )

  if (p10 != null && p90 != null) {
    return (
      <g>
        <line x1={x(p10)} x2={x(p90)} y1={y} y2={y} stroke={color} strokeWidth={2} opacity={0.35} />
        {p25 != null && p75 != null && (
          <rect x={x(p25)} y={y - 4} width={Math.max(0, x(p75) - x(p25))} height={8} rx={2} fill={color} opacity={0.45}>
            <title>{`p10 ${p10} · p25 ${p25} · median ${median} · p75 ${p75} · p90 ${p90}`}</title>
          </rect>
        )}
        {medianTick}
      </g>
    )
  }

  if (p25 != null && p75 != null) {
    return (
      <g>
        <rect x={x(p25)} y={y - 4} width={Math.max(0, x(p75) - x(p25))} height={8} rx={2} fill={color} opacity={0.45}>
          <title>{`p25 ${p25} · median ${median} · p75 ${p75} (p10/p90 not published)`}</title>
        </rect>
        {medianTick}
        <text x={x(p75) + 6} y={y + 3.5} fontSize="8.5" fill="var(--ink-3)">p25–p75</text>
      </g>
    )
  }

  const point = median ?? mean
  if (point == null) return null
  return (
    <g>
      <circle cx={x(point)} cy={y} r={4} fill={color} opacity={0.85}>
        <title>{median != null ? `median ${median}` : `mean ${mean} (central tendency only — no spread published)`}</title>
      </circle>
      <text x={x(point) + 8} y={y + 3.5} fontSize="9" fill="var(--ink-3)">
        {median != null ? 'median' : 'mean'} only
      </text>
    </g>
  )
}
