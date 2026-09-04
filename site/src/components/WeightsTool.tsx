/* The custom-weights tool — opt-in, and the only place the site produces an
 * ordering.
 *
 * Three rules make this defensible rather than a ranking in disguise:
 *   1. It is off until you open it. Nothing on the site is weighted by default.
 *   2. The presets are labelled "example lenses", not recommendations. They
 *      exist to show the control works, not to suggest what matters.
 *   3. Where a place is missing a metric, its weight is REDISTRIBUTED across
 *      the metrics that remain, and the amount moved is stated per place.
 *      Scoring a missing value as zero would silently punish thin data.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Flag } from './Flag'
import { useData } from '../data/store'
import { METRICS, METRIC_BY_KEY, THEMES, type ThemeKey } from '../data/registry'
import { UNSTABLE_METRIC_KEYS, composite, stabilityOf, type WeightedInput } from '../data/compute'
import { downloadCsv } from '../lib/export'

/* Deliberately varied so no single lens reads as the site's opinion. */
const EXAMPLE_LENSES: { name: string; note: string; weights: Record<string, number> }[] = [
  {
    name: 'Build savings fast',
    note: 'pay and what is left over, little else',
    weights: { salary_gross: 3, savings: 3, years_to_home: 2, rent_outside: 1 },
  },
  {
    name: 'Settle permanently',
    note: 'weights the legal road over the money',
    weights: { pr_years: 3, citizenship_years: 3, foreign_born: 2, english_work: 1 },
  },
  {
    name: 'Warm and liveable',
    note: 'sun and daily life ahead of pay',
    weights: { sunshine: 3, happiness_rank: 2, summer_high: 1, healthcare: 2 },
  },
  {
    name: 'Land a first job',
    note: 'market size and working language',
    weights: { ict_specialists: 3, ict_share: 2, english_work: 3, salary_gross: 1 },
  },
]

/* Which of the example lenses a theme opens on (package 29, the owner's
 * ruling on NEEDS-DECISION #64). The tool stays OFF by default — that is the
 * whole point of it, and its own copy says so — but when a visitor opens it
 * from a theme, it starts from the lens that theme is about instead of from
 * an empty set of sliders. Every lens below already existed; nothing new is
 * asserted about what matters, and the visitor's first slider replaces it. */
const LENS_FOR_THEME: Record<ThemeKey, string> = {
  money: 'Build savings fast',
  housing: 'Build savings fast',
  visa: 'Settle permanently',
  people: 'Settle permanently',
  jobs: 'Land a first job',
  life: 'Warm and liveable',
  climate: 'Warm and liveable',
}

export function WeightsTool({ theme }: { theme: ThemeKey }) {
  const data = useData()
  const [open, setOpen] = useState(false)
  const [weights, setWeights] = useState<Record<string, number>>({})
  const [activeLens, setActiveLens] = useState<string | null>(null)
  /* Set once the visitor moves a slider or picks a lens themselves. Until
   * then the theme's lens seeds the tool on open; afterwards their weights
   * are theirs and survive every theme switch. */
  const [ownWeights, setOwnWeights] = useState(false)

  const themeLens = EXAMPLE_LENSES.find((l) => l.name === LENS_FOR_THEME[theme])
  const openWith = () => {
    if (!ownWeights && themeLens) {
      setWeights({ ...themeLens.weights })
      setActiveLens(themeLens.name)
    }
    setOpen(true)
  }

  const active = Object.entries(weights).filter(([, w]) => w > 0)

  const results = useMemo(() => {
    if (active.length === 0) return []

    // Normalise each metric across the cities being scored, so a dollar figure
    // and a rank can sit in the same composite without one swamping the other.
    const ranges = new Map<string, { min: number; max: number }>()
    for (const [key] of active) {
      const m = METRIC_BY_KEY.get(key)
      if (!m) continue
      // A figure the site has flagged as smaller than the rounding on its own
      // inputs must not set this range. Here that matters more than on a chart:
      // a bad extreme does not merely draw badly, it changes the normalised
      // score of every other city. The flagged city still gets scored — it just
      // does not define the scale it is scored against.
      const risky = UNSTABLE_METRIC_KEYS.has(key)
      const vals = data.cities
        .filter((c) => !(risky && stabilityOf(c, 'mid') === 'unstable'))
        .map((c) => m.value(c, data.countryById.get(c.country), 'mid'))
        .filter((v): v is number => v != null)
      if (vals.length) ranges.set(key, { min: Math.min(...vals), max: Math.max(...vals) })
    }

    return data.cities
      .map((city) => {
        const inputs: Record<string, WeightedInput> = {}
        for (const [key, weight] of active) {
          const m = METRIC_BY_KEY.get(key)
          const r = ranges.get(key)
          if (!m || !r) continue
          inputs[m.label] = {
            value: m.value(city, data.countryById.get(city.country), 'mid'),
            weight,
            higherIsBetter: m.direction === 'higher_better',
            min: r.min,
            max: r.max,
          }
        }
        return { city, ...composite(inputs) }
      })
      .filter((r) => r.score != null)
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
  }, [active, data])

  const totalWeight = active.reduce((s, [, w]) => s + w, 0)

  if (!open) {
    return (
      <div className="panel" style={{ marginTop: 12, borderStyle: 'dashed' }}>
        <h2>Weigh things yourself</h2>
        <div className="sub">
          The one place this site produces an ordering — and only because you built it. Off by default,
          and it stays off until you open it.
          {themeLens && !ownWeights && (
            <> It will start from <b>{themeLens.name}</b> — {themeLens.note} — which you can change or clear.</>
          )}
        </div>
        <button className="pill" onClick={openWith}>Open the weights tool</button>
      </div>
    )
  }

  return (
    <div className="panel" style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h2>Weigh things yourself</h2>
        <button className="pill" style={{ marginLeft: 'auto' }} onClick={() => setOpen(false)}>Close</button>
      </div>
      <div className="sub">
        Give the things you care about a weight. The order below is yours, not ours — change a slider
        and it changes.
      </div>

      <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', margin: '4px 0 12px', alignItems: 'center' }}>
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>Example lenses —</span>
        {EXAMPLE_LENSES.map((l) => (
          <button key={l.name} className="pill" aria-pressed={activeLens === l.name}
            title={l.note}
            onClick={() => { setWeights(l.weights); setActiveLens(l.name); setOwnWeights(true) }}>
            {l.name}
          </button>
        ))}
        {active.length > 0 && (
          <button className="pill" onClick={() => { setWeights({}); setActiveLens(null); setOwnWeights(true) }}>Clear</button>
        )}
      </div>
      <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginBottom: 12 }}>
        These are examples of how the control works, not suggestions about what should matter.
      </p>

      {/* sliders, grouped by theme */}
      <div style={{ display: 'grid', gap: 14, gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))' }}>
        {THEMES.map((t) => {
          const metrics = METRICS.filter((m) => m.theme === t.key && m.direction !== 'neutral')
          if (!metrics.length) return null
          return (
            <div key={t.key}>
              <div className="kicker" style={{ marginBottom: 5 }}>{t.label}</div>
              {metrics.map((m) => (
                <label key={m.key} style={{
                  display: 'flex', gap: 8, alignItems: 'center', fontSize: 'var(--text-2xs)',
                  color: 'var(--ink-2)', padding: '3px 0',
                }}>
                  <input
                    type="range" min={0} max={3} step={1}
                    value={weights[m.key] ?? 0}
                    onChange={(e) => {
                      setWeights((w) => ({ ...w, [m.key]: Number(e.target.value) }))
                      setActiveLens(null)
                      setOwnWeights(true)
                    }}
                    style={{ width: 74, accentColor: 'var(--accent)' }}
                    aria-label={`Weight for ${m.label}`}
                  />
                  <span style={{ flex: 1 }}>{m.label}</span>
                  <b className="tnum" style={{ color: weights[m.key] ? 'var(--accent)' : 'var(--ink-3)' }}>
                    {weights[m.key] ?? 0}
                  </b>
                </label>
              ))}
            </div>
          )
        })}
      </div>

      {active.length === 0 ? (
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 14 }}>
          Nothing is weighted yet, so there is no order to show.
        </p>
      ) : (
        <>
          <div style={{
            display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap',
            margin: '16px 0 8px', paddingTop: 12, borderTop: '1px solid var(--line)',
          }}>
            <h3 style={{ fontSize: 'var(--text-sm)', fontFamily: 'var(--font-display)' }}>
              Your order — {active.length} {active.length === 1 ? 'thing' : 'things'} weighted
            </h3>
            <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
              this ordering exists because you built it
            </span>
            <button className="pill" style={{ marginLeft: 'auto' }}
              onClick={() => downloadCsv('compass-my-weighting.csv', results.map((r, i) => ({
                position: i + 1,
                city: r.city.name,
                score_0_to_1: r.score?.toFixed(4),
                weight_used: r.usedWeight,
                weight_redistributed: r.missingWeight,
                metrics_missing: r.missingKeys.join('; '),
              })))}>⤓ CSV</button>
          </div>

          <ol style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {results.slice(0, 15).map((r, i) => (
              <li key={r.city.id} style={{
                display: 'flex', gap: 10, alignItems: 'center',
                padding: '6px 0', borderTop: i ? '1px solid var(--line)' : 'none',
              }}>
                <span className="tnum" style={{ width: 22, color: 'var(--ink-3)', fontSize: 'var(--text-2xs)' }}>
                  {i + 1}
                </span>
                <Flag cc={r.city.country} size={15} />
                <Link to={`/city/${r.city.id}`} style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-1)', textDecoration: 'none' }}>
                  {r.city.name}
                </Link>

                <span style={{ flex: 1, height: 7, background: 'var(--surface-sunk)', borderRadius: 4, marginLeft: 6 }}>
                  <span style={{
                    display: 'block', height: '100%', width: `${(r.score ?? 0) * 100}%`,
                    background: `var(--c-${r.city.country})`, borderRadius: 4,
                    transition: 'width var(--dur-slow) var(--ease-out)',
                  }} />
                </span>

                {r.missingWeight > 0 && (
                  <span className="chip chip-note" style={{ fontSize: 10, padding: '1px 7px' }}
                    title={`No value for: ${r.missingKeys.join(', ')}. That weight was spread across the metrics this city does have.`}>
                    {Math.round((r.missingWeight / totalWeight) * 100)}% redistributed
                  </span>
                )}
              </li>
            ))}
          </ol>

          <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 10, lineHeight: 1.7 }}>
            Where a city has no value for something you weighted, that weight is spread across the
            metrics it does have, and the chip says how much moved. Scoring a blank as zero would
            quietly punish cities for having thin data, which is a different claim from the one this
            tool appears to make. Showing the top 15 of {results.length} scored.
          </p>
        </>
      )}
    </div>
  )
}
