/* Compare — 2 to 6 places side by side.
 *
 * State lives in the URL so a comparison is a shareable link, which is the whole
 * distribution model for this project. Six headline metrics by default; depth is
 * one click away behind the seven theme groups. Nothing is ranked: columns stay
 * in the order the user added them and rows never sort themselves. */

import { useCallback, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AnimatePresence, LayoutGroup, motion } from 'motion/react'
import { Flag, FlagRibbon } from '../components/Flag'
import { Figure } from '../components/Figure'
import { BudgetEditor } from '../components/BudgetEditor'
import { MetricPicker } from '../components/MetricPicker'
import { useData } from '../data/store'
import { HEADLINE_KEYS, METRIC_BY_KEY, METRICS } from '../data/registry'
import { LENS_LABEL, isNeverAffordable, missingInputs, type Budget } from '../data/compute'
import { money, residencyRange } from '../data/format'
import type { Band, City, Lens } from '../data/types'
import { downloadCsv, downloadJson } from '../lib/export'

const MAX_PLACES = 6
const BANDS: Band[] = ['new_grad', 'mid', 'senior']
const BAND_LABEL: Record<Band, string> = {
  new_grad: 'Starting out',
  mid: 'Mid-level (3–5 yrs)',
  senior: 'Senior (6+ yrs)',
}

export function Compare() {
  const data = useData()
  const [params, setParams] = useSearchParams()

  const placeIds = useMemo(() => {
    const raw = params.get('places')
    const ids = raw ? raw.split(',').filter((id) => data.cityById.has(id)) : []
    return ids.length ? ids.slice(0, MAX_PLACES) : ['berlin', 'toronto'].filter((id) => data.cityById.has(id))
  }, [params, data])

  const metricKeys = useMemo(() => {
    const raw = params.get('metrics')
    const keys = raw ? raw.split(',').filter((k) => METRIC_BY_KEY.has(k)) : []
    return keys.length ? keys : HEADLINE_KEYS
  }, [params])

  const band = (params.get('band') as Band) ?? 'mid'
  const lens = (params.get('lens') as Lens) ?? 'gross'
  const view = params.get('view') === 'chart' ? 'chart' : 'table'

  const [budget, setBudget] = useState<Budget>({})
  const [pickerOpen, setPickerOpen] = useState(false)

  const cities = placeIds.map((id) => data.cityById.get(id)!).filter(Boolean)
  const metrics = metricKeys.map((k) => METRIC_BY_KEY.get(k)!).filter(Boolean)

  const update = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(params)
      for (const [k, v] of Object.entries(patch)) {
        if (v == null) next.delete(k)
        else next.set(k, v)
      }
      setParams(next, { replace: true })
    },
    [params, setParams],
  )

  const addCity = (id: string) => {
    if (placeIds.includes(id) || placeIds.length >= MAX_PLACES) return
    update({ places: [...placeIds, id].join(',') })
  }
  const removeCity = (id: string) => {
    const next = placeIds.filter((p) => p !== id)
    if (next.length >= 1) update({ places: next.join(',') })
  }

  const rows = useMemo(
    () =>
      metrics.map((m) => ({
        metric: m,
        values: cities.map((city) => ({
          city,
          value: m.value(city, data.countryById.get(city.country), band),
        })),
      })),
    [metrics, cities, band, data],
  )

  const exportRows = () =>
    rows.map((r) => {
      const row: Record<string, string | number | null> = { metric: r.metric.label }
      for (const v of r.values) row[v.city.name] = v.value
      return row
    })

  return (
    <div className="wrap" style={{ paddingTop: 24 }}>
      <div className="kicker">Compare · {cities.length} of {MAX_PLACES} places</div>
      <h1 style={{ fontSize: 'var(--text-xl)', marginTop: 4 }}>Side by side</h1>
      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', margin: '6px 0 16px', maxWidth: '68ch' }}>
        Columns stay in the order you added them. Nothing here is ranked or scored —
        tap any number to see exactly where it came from.
      </p>

      {/* ---- controls ---- */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>Experience</span>
        {BANDS.map((b) => (
          <button key={b} className="pill" aria-pressed={band === b} onClick={() => update({ band: b })}>
            {BAND_LABEL[b]}
          </button>
        ))}

        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginLeft: 10 }}>Salary shown as</span>
        {(['gross', 'net', 'after'] as Lens[]).map((l) => (
          <button key={l} className="pill" aria-pressed={lens === l} onClick={() => update({ lens: l })}>
            {l === 'gross' ? 'Gross' : l === 'net' ? 'After tax' : 'After living costs'}
          </button>
        ))}

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="pill" aria-pressed={view === 'chart'}
            onClick={() => update({ view: view === 'chart' ? 'table' : 'chart' })}>
            {view === 'chart' ? '⇄ table' : '⇄ chart'}
          </button>
          <button className="pill" onClick={() => downloadCsv('compass-compare.csv', exportRows())}>
            ⤓ CSV
          </button>
          <button className="pill" onClick={() => downloadJson('compass-compare.json', { band, lens, cities: cities.map((c) => c.id), rows: exportRows() })}>
            ⤓ JSON
          </button>
        </div>
      </div>

      <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginBottom: 10 }}>
        Salary rows currently show: <b style={{ color: 'var(--ink-2)' }}>{LENS_LABEL[lens]}</b>
      </p>

      {/* ---- city chips ---- */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14, alignItems: 'center' }}>
        {cities.map((c) => (
          <span key={c.id} className="chip chip-quiet"
            style={{ display: 'inline-flex', gap: 7, alignItems: 'center', padding: '5px 9px 5px 5px' }}>
            <Flag cc={c.country} size={16} />
            <Link to={`/city/${c.id}`} style={{ textDecoration: 'none', color: 'inherit', fontWeight: 600 }}>
              {c.name}
            </Link>
            {cities.length > 1 && (
              <button onClick={() => removeCity(c.id)} aria-label={`Remove ${c.name}`}
                style={{ color: 'var(--ink-3)', padding: '0 2px' }}>✕</button>
            )}
          </span>
        ))}
        {cities.length < MAX_PLACES && <AddCity onAdd={addCity} exclude={placeIds} />}
      </div>

      {/* ---- the comparison ---- */}
      {view === 'table' ? (
        <div className="panel" style={{ overflowX: 'auto', padding: 0 }}>
          {/* minWidth keeps columns readable on a phone and lets the panel scroll
              horizontally instead of squeezing the label column to two words a line.
              The page body never scrolls sideways — only this container does. */}
          <table style={{
            width: '100%', minWidth: 620, borderCollapse: 'separate', borderSpacing: 0,
            fontSize: 'var(--text-xs)',
          }}>
            <thead>
              <tr>
                <th style={{ ...th, width: 200, minWidth: 160 }}>Metric</th>
                {cities.map((c) => (
                  <th key={c.id} style={th}>
                    <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <Flag cc={c.country} size={16} />
                      <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--ink-1)' }}>
                        {c.name}
                      </span>
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ metric, values }) => (
                <tr key={metric.key}>
                  <td style={{ ...td, color: 'var(--ink-2)' }}>
                    {metric.label}
                    <small style={{ display: 'block', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 2 }}>
                      {metric.hint}
                    </small>
                  </td>
                  {values.map(({ city, value }) => (
                    <td key={city.id} style={td}>
                      <Cell metric={metric} city={city} value={value} band={band} />
                    </td>
                  ))}
                </tr>
              ))}
              <tr>
                <td style={{ ...td, color: 'var(--ink-2)' }}>
                  Staying permanently
                  <small style={{ display: 'block', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 2 }}>
                    Typical — real cases vary
                  </small>
                </td>
                {cities.map((c) => {
                  const k = data.countryById.get(c.country)
                  return (
                    <td key={c.id} style={td}>
                      <ResidencyBar cc={c.country} pr={k?.pr_years_typical ?? null}
                        cit={k?.citizenship_years_typical ?? null} />
                      <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 4 }}>
                        {k?.dual_citizenship.allowed
                          ? 'You can keep your other passport'
                          : k?.dual_citizenship.allowed === false
                            ? 'Dual citizenship normally not allowed'
                            : ''}
                      </div>
                    </td>
                  )
                })}
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        <ChartView rows={rows} />
      )}

      <button className="pill" style={{ marginTop: 12, borderStyle: 'dashed' }}
        onClick={() => setPickerOpen(true)}>
        + add a metric
      </button>

      {pickerOpen && (
        <MetricPicker
          selected={metricKeys}
          onClose={() => setPickerOpen(false)}
          onChange={(keys) => update({ metrics: keys.length ? keys.join(',') : null })}
        />
      )}

      <BudgetEditor cities={cities} budget={budget} onChange={setBudget} band={band} />
    </div>
  )
}

const th: React.CSSProperties = {
  padding: '10px 12px', textAlign: 'left', fontSize: 'var(--text-2xs)',
  fontWeight: 500, color: 'var(--ink-3)', letterSpacing: 'var(--tracking-wide)',
  textTransform: 'uppercase', borderBottom: '1px solid var(--line)',
}
const td: React.CSSProperties = {
  padding: '11px 12px', textAlign: 'left', verticalAlign: 'top',
  borderTop: '1px solid var(--line)',
}

function Cell({ metric, city, value, band }:
  { metric: typeof METRICS[number]; city: City; value: number | null; band: Band }) {
  const data = useData()
  const country = data.countryById.get(city.country)

  // years-to-home has a third state: computable inputs, but nothing is saved.
  if (metric.key === 'years_to_home' && value == null && isNeverAffordable(city, band)) {
    return (
      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--warn)' }}>
        never on this salary
        <small style={{ display: 'block', color: 'var(--ink-3)', marginTop: 2 }}>
          nothing is left over after rent and living costs
        </small>
      </span>
    )
  }

  if (value == null) {
    const missing = metric.theme === 'housing' || metric.key === 'savings'
      ? missingInputs(city, band)
      : []
    return (
      <Figure missing missingReason={
        missing.length ? `We have no ${missing.join(' or ')} figure for ${city.name}.` : undefined
      }>{null}</Figure>
    )
  }

  const src = metric.source?.(city, country)
  const body = <span className="big">{metric.format(value)}</span>

  return src
    ? <Figure source={{ ...src, asOf: city.as_of, confidence: metric.confidence }}>{body}</Figure>
    : body
}

function ResidencyBar({ cc, pr, cit }: { cc: string; pr: number | null; cit: number | null }) {
  if (pr == null) {
    return (
      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--warn)' }}>
        {cc === 'AE' ? 'golden visa only — no citizenship path' : 'no permanent path'}
      </span>
    )
  }
  const scale = 9
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
      <FlagRibbon cc={cc} width={Math.max(12, pr * scale)} />
      {cit != null && cit > pr && (
        <span aria-hidden="true" style={{
          width: (cit - pr) * scale, height: 5, borderRadius: 3, opacity: 0.5,
          background: 'repeating-linear-gradient(90deg, var(--ink-2) 0 4px, transparent 4px 8px)',
        }} />
      )}
      <b style={{ fontWeight: 500 }}>{residencyRange(pr, cit)}</b>
    </span>
  )
}

function AddCity({ onAdd, exclude }: { onAdd: (id: string) => void; exclude: string[] }) {
  const data = useData()
  const [q, setQ] = useState('')
  const matches = q.length > 1
    ? data.cities.filter((c) => c.name.toLowerCase().includes(q.toLowerCase()) && !exclude.includes(c.id)).slice(0, 6)
    : []

  return (
    <span style={{ position: 'relative' }}>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="+ add a city"
        aria-label="Add a city to the comparison"
        style={{
          border: '1px dashed var(--line-strong)', background: 'transparent',
          borderRadius: 'var(--radius-pill)', padding: '6px 13px', fontSize: 'var(--text-2xs)', width: 130,
        }} />
      {matches.length > 0 && (
        <ul style={{
          position: 'absolute', top: 'calc(100% + 5px)', left: 0, zIndex: 'var(--z-popover)' as never,
          listStyle: 'none', margin: 0, padding: 5, minWidth: 190,
          background: 'var(--surface)', border: '1px solid var(--line)',
          borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)',
        }}>
          {matches.map((c) => (
            <li key={c.id}>
              <button onClick={() => { onAdd(c.id); setQ('') }}
                style={{ display: 'flex', gap: 8, alignItems: 'center', width: '100%', padding: '7px 9px', textAlign: 'left' }}>
                <Flag cc={c.country} size={15} />
                <span style={{ fontSize: 'var(--text-2xs)' }}>{c.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </span>
  )
}

/** Bar chart view of the same rows — one small multiple per metric. */
function ChartView({ rows }: { rows: { metric: typeof METRICS[number]; values: { city: City; value: number | null }[] }[] }) {
  return (
    <LayoutGroup>
    <motion.div layout
      style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
      <AnimatePresence mode="popLayout">
      {rows.map(({ metric, values }) => {
        const nums = values.map((v) => v.value).filter((v): v is number => v != null)
        const max = nums.length ? Math.max(...nums) : 0
        return (
          // Cards spring into place when a metric or a city is added or removed.
          // Motion respects prefers-reduced-motion globally via MotionConfig.
          <motion.div key={metric.key} className="panel" layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 380, damping: 32 }}>
            <h2>{metric.label}</h2>
            <div className="sub">{metric.hint}</div>
            {values.map(({ city, value }) => (
              <div key={city.id} style={{ margin: '9px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>
                  <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <Flag cc={city.country} size={13} />{city.name}
                  </span>
                  <span className="tnum" style={{ fontWeight: 600, color: 'var(--ink-1)' }}>
                    {metric.format(value)}
                  </span>
                </div>
                <div style={{ height: 9, background: 'var(--surface-sunk)', borderRadius: 'var(--radius-sm)', marginTop: 4, overflow: 'hidden' }}>
                  {value != null && max > 0 && (
                    <div style={{
                      height: '100%', width: `${Math.max(2, (value / max) * 100)}%`,
                      background: `var(--c-${city.country})`, borderRadius: 'var(--radius-sm)',
                      transition: 'width var(--dur-slow) var(--ease-out)',
                    }} />
                  )}
                </div>
              </div>
            ))}
            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 8 }}>
              Bars are scaled to the largest value shown, not to a ranking.
              {values.some((v) => v.value == null) && ' Cities with no data have no bar.'}
            </div>
          </motion.div>
        )
      })}
      </AnimatePresence>
    </motion.div>
    </LayoutGroup>
  )
}

export { money }
