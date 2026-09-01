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
 *   - pay-composition basis (normalise.comparison_basis(), re-checked live
 *     against wage_distribution.json rather than assumed — an earlier
 *     version of this comment named a stale five-country group that
 *     predated package 10 tier 0.3's Norway fix and was already wrong about
 *     which toggle US was absent on even before that; package 11 tier 2
 *     added Germany as a fourth dual-basis country, re-checked live again
 *     rather than assumed unaffected). GB, AU, and ES publish a figure that
 *     already includes bonuses and cannot be split into a bonus-excluded
 *     "regular pay" figure, so they are absent specifically on THAT toggle.
 *     SE, US, and IE publish the opposite — bonus already excluded, with no
 *     source to add one back (normalise.py's own rule 2 forbids
 *     synthesising a component no source measured) — so they are absent
 *     specifically on "total earnings" instead. DK, NO, FI, and DE publish
 *     BOTH bases natively (DK via a real subtraction, NO/FI/DE via
 *     genuinely separate published fields, see _figure_for_basis) and are
 *     absent on neither.
 *   - Canada (both NOC codes) and Qatar/UAE have UNVERIFIED composition
 *     (pay_composition.json's own fields say "unknown") and are therefore
 *     absent on EVERY toggle state — an honest consequence of not having
 *     verified something, not a bug.
 * Switching either segment control visibly changes which rows have a bar and
 * which are a dashed, labelled absence — the interaction itself is the
 * disclosure the owner asked for ("calculate it, but tell users in detail
 * why and how — not at first glance").
 */

import { readableAbsentReason } from '../../data/profile'
import { useMemo, useState } from 'react'
import { Derived, type DerivedConcept } from '../Derived'
import { Seg, ChartFoot, ChartTable, Gap } from './Controls'
import { useAsync } from './useAsync'
import { loadPayComposition, type PayComposition } from '../../data/store'
import { comboKey, CA_NOC_DISTINCTION, type Basis, type CurrencyMode, type WageDistribution } from '../../data/explore'
import { computeYearSpread } from '../../data/yearSpread'
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

// Full occupation titles ("Software engineers & designers") overflowed the
// SVG's left edge at PL=190 — caught by reading an actual rendered
// screenshot, not by eyeballing the code (the string is well under any
// character-count limit that looks safe in isolation; it only overflows in
// context, against this specific label column width). The NOC code is short
// and unambiguous on its own; the full title moves to a <title> tooltip.
const ROW_LABEL: Record<string, string> = { 'CA-21231': '21231', 'CA-21232': '21232' }
const ROW_LABEL_FULL: Record<string, string> = {
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

/* Package 14 — this file used to carry degradationNote()/degradationNoteFull()
 * here, an inline "1-digit match" style note beside a row whose own depth
 * was shallower than the reference's. Removed: resolve_set() (crosswalk.py)
 * now requires an EXACT depth match for a row to be comparable at all (an
 * adversarial review's own finding — a "degraded" row still carried its own
 * un-degraded VALUE underneath, which these notes were papering over, not
 * disclosing). `rows` below is already filtered to chart_comparable.comparable,
 * and every comparable row's own depth now equals the resolved depth by
 * construction, so there is nothing left for a per-row note to say — the
 * resolved depth is stated once, above the chart, and every EXCLUDED
 * country's own reason renders in the disclosure section instead. */

/** The composition badge for the basis actually shown in THIS card — not a
 *  stale echo of the source's raw, pre-basis pay_composition.json entry.
 *  Safe to derive purely from `basis`: normalise.py's comparison_basis()
 *  only ever grants a row's combo `ok: true` when its composition already
 *  matches the basis's own canonical meaning (regular_pay: bonus AND
 *  employer contributions excluded; total_earnings: bonus included,
 *  contributions excluded) — whether the combo got there natively, through
 *  Denmark's subtraction (subtract_component()), or through Finland/
 *  Norway's own dual-published fields (_figure_for_basis's
 *  "basis_total_earnings" branch). Employer contributions are excluded on
 *  EVERY basis this pipeline ever renders (comparison_basis()'s bases()
 *  requires contrib is False for both regular_pay and total_earnings), so
 *  that half of the badge never varies by basis.
 *
 *  Previously this badge echoed comp.irregular_bonus/employer_social_
 *  contributions directly regardless of which basis was selected, so
 *  Denmark's post-subtraction regular_pay card and Norway's AvtaltManedslonn
 *  (regular_pay) card both still said "Includes: irregular bonus" — true of
 *  the SOURCE's raw, un-adjusted headline figure, not of the number the
 *  card was actually showing underneath it. */
function conceptForBasis(comp: PayComposition['sources'][number], basis: Basis): DerivedConcept {
  // BLS's and the UK's own irregular_bonus is prose, not a clean boolean,
  // because their real composition doesn't collapse to a full include/
  // exclude (BLS: production/incentive pay is in, discretionary bonuses are
  // out). Each renders under exactly one basis (comparison_basis()'s own
  // hardcoded override table — bls_oews -> regular_pay, salary_uk ->
  // total_earnings), so this detail is never shown next to a mismatched
  // basis; it replaces the generic wording rather than sitting beside a
  // wrong one.
  const bonusDetail = typeof comp.irregular_bonus === 'string' ? comp.irregular_bonus : null
  if (basis === 'regular_pay') {
    return {
      name: comp.concept_name, office: comp.office,
      includes: bonusDetail ?? undefined,
      excludes: bonusDetail ? 'employer social contributions' : 'irregular bonus, employer social contributions',
    }
  }
  return {
    name: comp.concept_name, office: comp.office,
    includes: bonusDetail ?? 'irregular bonus',
    excludes: 'employer social contributions',
  }
}

export function WagePanel({ wages }: { wages: WageDistribution }) {
  const { data: payComp } = useAsync(loadPayComposition, 'pay_composition')
  const [currency, setCurrency] = useState<CurrencyMode>('native')
  const [basis, setBasis] = useState<Basis>('regular_pay')

  const key = comboKey(currency, basis)
  // Package 14, Tier 1 (external audit Finding 1, SEVERE): chart_comparable
  // is resolved SET-WIDE (crosswalk.resolve_set(), at build time) — the
  // deepest occupation depth a real quorum of these countries actually
  // share, not each row's own pairwise-against-Sweden depth. A row below
  // that resolved depth cannot honestly sit on the same axis as one that
  // meets it (Ireland's own source is ISCO major group 2 — "all
  // professionals," not software specifically) and is excluded from the
  // chart itself, by name, with its own reason — never just labelled and
  // left in. Its real data still reaches the country page (CountryProfile.tsx
  // reads wages.countries directly, unfiltered, and uses the OTHER verdict,
  // row.crosswalk, which is still the correct pairwise answer there).
  const uncomparable = useMemo(() => wages.countries.filter((c) => !c.chart_comparable.comparable), [wages])
  const rows = useMemo(() => {
    const comparable = wages.countries.filter((c) => c.chart_comparable.comparable)
    // FIXED (tier 7, adversarial review finding F17): native mode draws no
    // shared axis because different currencies aren't positionally
    // comparable (see canCompare below) — but this sort still ranked rows
    // by raw magnitude across those same different currencies, so the
    // ordering itself was the same false comparison the axis fix removed,
    // just moved from geometry into row order. Native mode sorts by
    // country code instead — a neutral order that doesn't imply anything
    // about relative pay. USD mode, where magnitude really is comparable,
    // keeps the ranked "who pays the most" order.
    if (currency !== 'usd') {
      return comparable.sort((a, b) => a.country.localeCompare(b.country))
    }
    return comparable.sort((a, b) => {
      const av = a.combos[key], bv = b.combos[key]
      const am = av?.ok ? (av.value.median ?? av.value.mean ?? -1) : -1
      const bm = bv?.ok ? (bv.value.median ?? bv.value.mean ?? -1) : -1
      return bm - am
    })
  }, [wages, key, currency])

  // Package 14, Tier 2 (external audit Finding 2, HIGH) — reference years
  // across this panel's own countries span 2009-2025 (2018-2025 excluding
  // the UAE); nominal pay rose ~20-30% across that window, the same order
  // of magnitude as the cross-country gap the chart draws. Computed over
  // whichever rows actually SHOW a bar on the current toggle (combo.ok) —
  // a row absent on this basis isn't part of what the reader is looking
  // at right now. No deflator is applied (see NEEDS-DECISION.md #34 for
  // why one was investigated and declined): this is disclosure, not a
  // correction to any number. computeYearSpread() itself lives in
  // data/yearSpread.ts, pure, zero-dependency, and unit-tested (a real
  // gap M6 found: it used to claim "unit-tested" from inside this file's
  // own store.ts import chain, which plain Node can't load at all) —
  // Tier 1's own set-wide crosswalk fix already excludes this chart's
  // widest-vintage countries (Ireland, Spain), so this rarely fires on
  // the live chart today; see that function's own docstring.
  const yearSpread = useMemo(
    () => computeYearSpread(rows.filter((r) => r.combos[key]?.ok).map((r) => ({ country: r.country, year: r.native.year }))),
    [rows, key],
  )

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
      country: r.country, source: r.source_id, comparable: r.chart_comparable.comparable,
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
        <a href="#/data">crosswalk</a> to the deepest ISCO-08 code a real quorum of these countries all
        share — currently <b>{wages.resolved_comparison.depth ?? '—'}-digit</b>
        {wages.resolved_comparison.shared_key ? ` (${wages.resolved_comparison.shared_key})` : ''}.
        A country whose own classification doesn't reach that depth is excluded from this chart, named
        below, not shown at a shallower depth beside ones that reach it. Switch the toggles — a row that
        disappears is a row that cannot honestly express what you just asked for, named below it too.
      </div>
      <div className="crail">
        <Seg label="Currency" value={currency}
          options={[['native', 'native currency'], ['usd', 'US dollars']]} onChange={setCurrency} />
        <Seg label="Pay basis" value={basis}
          options={[['regular_pay', 'regular pay'], ['total_earnings', 'total earnings']]} onChange={setBasis} />
      </div>

      {yearSpread && yearSpread.spread > 3 && (
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', background: 'var(--surface-sunk)',
                    borderRadius: 6, padding: '6px 10px', marginTop: 6 }}>
          <b>{yearSpread.spread}-year spread</b> across the rows shown here — {yearSpread.newest.country}'s
          figure is {yearSpread.newest.year}, {yearSpread.oldest.country}'s is {yearSpread.oldest.year}.
          Nominal pay moved materially over that window in every country this panel covers; no adjustment
          for it is applied below — each figure is shown exactly as its own source published it, for its
          own year, shown beside every value.
        </p>
      )}

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

            return (
              <g key={r.country}>
                <text x={PL - 10} y={y0 + 4} fontSize="10.5" fontWeight={suffix ? 400 : 600}
                  fill={col} textAnchor="end">
                  {iso}{suffix ? ` · ${label}` : ''}
                  {/* Package 14, Tier 2 (Finding 2) — the reference year, on
                      every row, at first glance, not only inside the
                      collapsed "open each row's own method" card below. */}
                  <tspan fontSize="8.5" fontWeight={400} fill="var(--ink-3)"> '{String(r.native.year).slice(2)}</tspan>
                  {suffix && ROW_LABEL_FULL[r.country] && (
                    <title>
                      {ROW_LABEL_FULL[r.country]}
                      {CA_NOC_DISTINCTION[r.country] ? ` — ${CA_NOC_DISTINCTION[r.country]}` : ''}
                    </title>
                  )}
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
              </g>
            )
          })}
        </svg>
      </div>

      {rows.some((r) => r.combos[key]?.ok) && payComp && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', cursor: 'pointer' }}>
            Every figure here is calculated — open each row's own method
          </summary>
          {/* FIXED (tier 7, adversarial review finding F12): a single example row —
              and that row's card never stated the calculated RESULT, only the steps
              leading to it — has grown into one real, tappable trigger per comparable
              row, each showing its own year (finding F13: no figure on the panel
              named its vintage anywhere outside an opened card). Real DOM list, not
              SVG — keyboard- and touch-reachable. Package 14: the chart no longer has
              degradation labels to disclose (SVG <title> or otherwise) — resolve_set()
              now requires an EXACT depth match to be comparable at all, so every row
              in the ChartTable's own "Comparable" column below is either the resolved
              depth or "no"; a row that can't meet it is excluded from the chart
              entirely and its reason moves to the Gap disclosure section further
              down, as a real DOM element, not a tooltip. */}
          <ul style={{ listStyle: 'none', padding: 0, margin: '6px 0 0', display: 'flex',
                       flexDirection: 'column', gap: 4, fontSize: 'var(--text-2xs)' }}>
            {rows.filter((r) => r.combos[key]?.ok).map((r) => {
              const combo = r.combos[key]!
              if (!combo.ok) return null
              const comp = payComp.sources.find((s) => s.source_id === r.source_id)
              return (
                <li key={r.country} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                  <span style={{ fontWeight: 600, color: cc3(splitRow(r.country).iso), minWidth: 32 }}>
                    {r.country}
                  </span>
                  <Derived chain={combo.chain}
                    native={{ value: r.native.value.median ?? r.native.value.mean ?? 0,
                      currency: r.native.currency, period: r.native.period, year: r.native.year }}
                    result={{ value: combo.value.median ?? combo.value.mean ?? 0, currency: combo.currency }}
                    concept={comp ? conceptForBasis(comp, basis) : undefined}
                    payCycleNote={CA_NOC_DISTINCTION[r.country] ?? payComp.pay_cycle_context[splitRow(r.country).iso]}>
                    {fmtCcy(combo.value.median ?? combo.value.mean, combo.currency)} ({r.native.year})
                  </Derived>
                </li>
              )
            })}
          </ul>
        </details>
      )}

      <ChartFoot csv={{ name: `compass-wages-${currency}-${basis}.csv`, rows: csvRows }}>
        <span className="chip chip-ok">● Official · national statistical offices</span>
        <span className="chip chip-quiet">
          {rows.filter((r) => !r.combos[key]?.ok).length} of {rows.length} rows not shown for this
          toggle — see the dashed reason beside each
        </span>
      </ChartFoot>

      {/* Package 12, tier 0 follow-up: Canada's two NOC rows have UNVERIFIED
       *  composition (see this file's own module docstring), so combos[key]
       *  is never .ok on ANY toggle and neither row ever enters the "open
       *  each row's own method" list above — CA_NOC_DISTINCTION's own text
       *  is otherwise reachable only via the SVG row label's hover-only
       *  <title>. Verified live (not assumed) before adding this: clicking
       *  every toggle combination confirmed CA never appears in that list.
       *  A plain, unconditionally visible line closes the gap for keyboard/
       *  touch readers on this panel specifically — the country page has
       *  carried this as visible text since tier 0 shipped; this is the one
       *  spot on Explore/Money that still needed it. */}
      {rows.some((r) => CA_NOC_DISTINCTION[r.country]) && (
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 8, maxWidth: '68ch' }}>
          {rows.filter((r) => CA_NOC_DISTINCTION[r.country]).map((r) => (
            <span key={r.country} style={{ display: 'block', marginTop: 2 }}>
              <b>{r.country}</b> — {CA_NOC_DISTINCTION[r.country]}
            </span>
          ))}
        </p>
      )}

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
            r.chart_comparable.comparable ? `${r.chart_comparable.depth}-digit` : 'no',
          ]
        })}
      />

      {(wages.absent.length > 0 || uncomparable.length > 0) && (
        <Gap title={`${wages.absent.length + uncomparable.length} countries don't appear in this chart`} span="s6"
          where={<>Full account in <a href="#/data">NEEDS-DECISION.md →</a></>}>
          <p>
            {wages.absent.map((a, i) => (
              <span key={a.country}>
                {i > 0 && '; '}<b>{a.country}</b> — {readableAbsentReason(a.reason)}
              </span>
            ))}
            {uncomparable.map((c) => (
              <span key={c.country}>
                {(wages.absent.length > 0 || c !== uncomparable[0]) && '; '}
                <b>{c.country}</b> — has real data (see its <a href={`#/country/${c.country}`}>country page</a>),
                but {c.chart_comparable.comparable ? '' : c.chart_comparable.reason}
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
