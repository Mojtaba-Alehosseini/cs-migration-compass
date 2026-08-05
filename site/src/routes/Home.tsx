/* Home = the dot field.
 *
 * The visualisation is the product, so it opens the site. The title stays small
 * and quiet, the search sits above the field, and everything else is the data:
 * 73 cities as flag-dots, answering one plain question at a time.
 *
 * Selection persists across questions on purpose — picking Berlin and Toronto on
 * "who pays the most?" and then switching to "where can you buy a home?" is the
 * entire point of the thing.
 *
 * Nothing here ranks anything. A dot's position is its value on the axis you
 * chose, and the footnote says exactly that.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Flag } from '../components/Flag'
import { SwarmField } from '../components/SwarmField'
import { BudgetEditor } from '../components/BudgetEditor'
import { ProfileNudge } from '../components/ProfileNudge'
import { useData } from '../data/store'
import { QUESTIONS, SUMMER_AXIS, pickColor } from '../data/questions'
import type { SecondAxis } from '../data/questions'
import { money, years } from '../data/format'
import { savingsPerYear, yearsToHome, type Budget } from '../data/compute'
import { downloadCsv } from '../lib/export'
import type { City } from '../data/types'

const prefersReduced = () =>
  typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

export function Home() {
  const data = useData()
  const navigate = useNavigate()

  const [qi, setQi] = useState(0)
  const [selected, setSelected] = useState<string[]>([])
  const [secondOn, setSecondOn] = useState(false)
  const [season, setSeason] = useState<'winter' | 'summer'>('winter')
  const [tableOpen, setTableOpen] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [budget, setBudget] = useState<Budget>({})
  const [query, setQuery] = useState('')
  const [intro, setIntro] = useState(() => !prefersReduced())
  const introTimer = useRef<number>(0)

  const question = QUESTIONS[qi]!
  const countryOf = useCallback((c: City) => data.countryById.get(c.country), [data])

  // The flag-strip intro: dots arrive scattered and rotated, then settle onto
  // the axis. Skippable, and never runs under reduced motion.
  useEffect(() => {
    if (!intro) return
    introTimer.current = window.setTimeout(() => setIntro(false), 1300)
    return () => window.clearTimeout(introTimer.current)
  }, [intro])

  // A second axis only exists for questions that have an approved partner, and
  // never for the PR/citizenship bars.
  const secondAxis: SecondAxis | null = useMemo(() => {
    if (!secondOn || !question.secondAxis) return null
    if (question.secondAxis.seasonSwitch && season === 'summer') return SUMMER_AXIS
    return question.secondAxis
  }, [secondOn, question, season])

  const toggle = useCallback((id: string) => {
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]))
  }, [])

  const selectedCities = useMemo(
    () => selected.map((id) => data.cityById.get(id)).filter((c): c is City => !!c),
    [selected, data],
  )

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) return []
    return data.cities.filter((c) => c.name.toLowerCase().includes(q)).slice(0, 6)
  }, [query, data])

  const rows = useMemo(() => {
    const withV = data.cities.map((c) => ({ city: c, v: question.value(c, countryOf(c)) }))
    return withV.sort((a, b) => {
      if (a.v == null) return 1
      if (b.v == null) return -1
      return a.v - b.v
    })
  }, [data.cities, question, countryOf])

  return (
    <div className="wrap" style={{ paddingTop: 22, paddingBottom: 90 }}>
      {/* quiet title — the field is the hero, not this */}
      <h1 style={{ fontSize: 'var(--text-lg)', fontWeight: 550, letterSpacing: '-0.01em' }}>
        How far one developer salary goes.
      </h1>
      <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginTop: 3 }}>
        {data.cities.length} cities, {data.countries.length} countries. Ask a question — the dots answer.
        Tap any to compare.
      </p>

      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap', margin: '12px 0 4px', position: 'relative', maxWidth: 460 }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Find a city or country…"
          aria-label="Find a city or country"
          style={{
            flex: 1, minWidth: 200, border: '1px solid var(--line-strong)',
            background: 'var(--surface)', borderRadius: 'var(--radius-md)',
            padding: '8px 12px', fontSize: 'var(--text-xs)',
          }}
        />
        {matches.length > 0 && (
          <ul style={{
            position: 'absolute', top: 'calc(100% + 5px)', left: 0, right: 0, zIndex: 'var(--z-popover)' as never,
            listStyle: 'none', margin: 0, padding: 5, background: 'var(--surface)',
            border: '1px solid var(--line)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)',
          }}>
            {matches.map((c) => (
              <li key={c.id} style={{ display: 'flex', gap: 4 }}>
                <button onClick={() => { toggle(c.id); setQuery('') }}
                  style={{ display: 'flex', gap: 8, alignItems: 'center', flex: 1, padding: '7px 9px', textAlign: 'left' }}>
                  <Flag cc={c.country} size={15} />
                  <span style={{ fontSize: 'var(--text-2xs)' }}>{c.name}</span>
                  <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--ink-3)' }}>add to picks</span>
                </button>
                <button onClick={() => navigate(`/city/${c.id}`)} title={`Open ${c.name}`}
                  style={{ padding: '0 8px', color: 'var(--ink-3)', fontSize: 12 }}>→</button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* the five plain questions */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '14px 0 4px' }}>
        {QUESTIONS.map((q, i) => (
          <button key={q.id} className="pill" aria-pressed={i === qi}
            onClick={() => { setQi(i); setSecondOn(false) }}>
            {q.q}
          </button>
        ))}
      </div>
      <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', minHeight: 18 }}>
        {question.sub}
      </div>

      {/* the stage */}
      <div className="swarm-stage">
        {intro && (
          <button className="pill" onClick={() => setIntro(false)}
            style={{ position: 'absolute', right: 10, top: 8, zIndex: 5, fontSize: 12 }}>
            skip intro
          </button>
        )}

        <div style={{
          display: 'flex', justifyContent: 'space-between', fontSize: 11.5,
          color: 'var(--ink-2)', padding: '4px 2px',
        }}>
          <span>{question.axisL}</span>
          <span style={{ color: 'var(--accent)', fontWeight: 550 }}>{question.dir}</span>
          <span>{question.axisR}</span>
        </div>

        <SwarmField
          cities={data.cities}
          countryOf={countryOf}
          question={question}
          secondAxis={secondAxis}
          selected={selected}
          onToggle={toggle}
          intro={intro}
        />

        {/* scorecard — your picks, on this question */}
        {selected.length > 0 && (
          <div style={{
            position: 'absolute', left: 14, top: 40, width: 214, zIndex: 12,
            background: 'var(--surface)', border: '1px solid var(--line)',
            borderRadius: 'var(--radius-lg)', padding: '12px 14px',
            fontSize: 'var(--text-2xs)', boxShadow: 'var(--shadow-md)',
          }}>
            <h2 style={{
              fontSize: 11, color: 'var(--ink-3)', fontWeight: 500, marginBottom: 6,
              textTransform: 'uppercase', letterSpacing: 'var(--tracking-wide)', fontFamily: 'var(--font-ui)',
            }}>Your picks</h2>
            {selectedCities.map((c, ix) => (
              <div key={c.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '4px 0', borderTop: ix ? '1px solid var(--line)' : 'none',
              }}>
                <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span aria-hidden="true" style={{
                    width: 8, height: 8, borderRadius: '50%', background: pickColor(ix), flex: 'none',
                  }} />
                  {c.name}
                </span>
                <span>
                  <b className="tnum">{question.fmt(question.value(c, countryOf(c)))}</b>{' '}
                  <button onClick={() => toggle(c.id)} aria-label={`Remove ${c.name}`}
                    style={{ color: 'var(--ink-3)', padding: '0 2px' }}>✕</button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* controls under the field */}
      <div style={{
        display: 'flex', gap: 10, alignItems: 'center', padding: '10px 0 0',
        flexWrap: 'wrap', fontSize: 'var(--text-2xs)', color: 'var(--ink-2)',
      }}>
        <span>Every dot wears its country's flag — hover for names, tap to compare.</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {question.secondAxis && (
            <button className="pill" aria-pressed={secondOn} onClick={() => setSecondOn((v) => !v)}>
              {secondOn ? `↕ ${secondAxis?.label ?? ''} on` : '+ second axis'}
            </button>
          )}
          {secondOn && secondAxis?.seasonSwitch && (
            <button className="pill" onClick={() => setSeason((s) => (s === 'winter' ? 'summer' : 'winter'))}>
              {season === 'winter' ? '❄ winter' : '☀ summer'}
            </button>
          )}
          <button className="pill" aria-pressed={tableOpen} onClick={() => setTableOpen((v) => !v)}>
            ⇄ table
          </button>
        </div>
      </div>
      {secondOn && secondAxis && (
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 6 }}>
          {secondAxis.hint}. Cities missing either value sit in the gutter rather than at zero.
        </p>
      )}

      {/* table view of the same question */}
      {tableOpen && (
        <div className="panel" style={{ marginTop: 12, overflowX: 'auto', padding: 0 }}>
          <table style={{ width: '100%', minWidth: 460, borderCollapse: 'separate', borderSpacing: 0, fontSize: 'var(--text-xs)' }}>
            <thead>
              <tr>
                {['City', question.q, 'Salary (mid)', 'Kept / yr'].map((h) => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '9px 12px', fontSize: 11.5, fontWeight: 500,
                    color: 'var(--ink-3)', borderBottom: '1px solid var(--line)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ city, v }) => (
                <tr key={city.id} style={{ background: selected.includes(city.id) ? 'var(--accent-wash)' : undefined }}>
                  <td style={cell}>
                    <Link to={`/city/${city.id}`} style={{ display: 'flex', gap: 7, alignItems: 'center', textDecoration: 'none', color: 'var(--ink-1)' }}>
                      <Flag cc={city.country} size={14} />{city.name}
                    </Link>
                  </td>
                  <td style={cell}><span className="tnum">{question.fmt(v)}</span></td>
                  <td style={cell}><span className="tnum">{money(city.salary_usd_year.mid)}</span></td>
                  <td style={cell}><span className="tnum">{money(savingsPerYear(city, 'mid'))}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', padding: '16px 0 0', maxWidth: '76ch', lineHeight: 1.7 }}>
        <b style={{ color: 'var(--ink-2)' }}>Honest by design:</b> a city with no value for a question parks in
        the “no data” gutter instead of vanishing — Oslo has no sunshine figure, Aarhus no purchase price.
        Dubai's residency bar says “no citizenship path” rather than pretending. Cities past 130 years to a
        home read “≈never”, because the arithmetic answer invites you to treat it as a real wait.
        Position on an axis is a value, never a ranking. <Link to="/data">Where every number comes from →</Link>
      </p>

      <ProfileNudge active={selected.length > 0} />

      {/* bottom tray */}
      {selected.length > 0 && (
        <div style={{
          position: 'fixed', left: '50%', bottom: 14, transform: 'translateX(-50%)',
          background: 'var(--ink-1)', color: 'var(--paper)', borderRadius: 'var(--radius-lg)',
          padding: '10px 14px', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
          zIndex: 'var(--z-tray)' as never, boxShadow: 'var(--shadow-lg)', maxWidth: '92vw',
        }}>
          <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>
            {selected.length} {selected.length === 1 ? 'city' : 'cities'}
          </span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {selectedCities.map((c, ix) => (
              <span key={c.id} style={{
                fontSize: 12, background: 'color-mix(in srgb, var(--paper) 12%, transparent)',
                borderRadius: 'var(--radius-xl)', padding: '4px 10px',
                display: 'flex', gap: 6, alignItems: 'center',
              }}>
                <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: '50%', background: pickColor(ix) }} />
                {c.name}
              </span>
            ))}
          </div>
          <button className="btn-accent" style={{ padding: '8px 14px', fontSize: 13 }}
            onClick={() => setSheetOpen(true)}>
            Full breakdown →
          </button>
          <Link to={`/compare?places=${selected.slice(0, 6).join(',')}`} className="pill"
            style={{ background: 'transparent', color: 'var(--paper)', borderColor: 'var(--ink-3)', textDecoration: 'none' }}>
            Compare
          </Link>
          <button className="pill" onClick={() => setSelected([])}
            style={{ background: 'transparent', color: 'var(--paper)', borderColor: 'var(--ink-3)' }}>
            Clear
          </button>
        </div>
      )}

      {/* breakdown sheet */}
      {sheetOpen && (
        <>
          <div onClick={() => setSheetOpen(false)} style={{
            position: 'fixed', inset: 0, background: 'rgba(20,19,15,.35)', zIndex: 'var(--z-sheet)' as never,
          }} />
          <div role="dialog" aria-label="Full breakdown" style={{
            position: 'fixed', left: '50%', bottom: 0, transform: 'translateX(-50%)',
            width: 'min(880px, 96vw)', maxHeight: '84vh', overflow: 'auto',
            background: 'var(--surface)', borderRadius: 'var(--radius-lg) var(--radius-lg) 0 0',
            border: '1px solid var(--line)', zIndex: 'calc(var(--z-sheet) + 1)' as never,
            padding: '20px 24px 30px',
          }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 4 }}>
              <h2 style={{ fontSize: 'var(--text-md)' }}>Side by side — your assumptions</h2>
              <button onClick={() => setSheetOpen(false)} aria-label="Close"
                style={{ marginLeft: 'auto', fontSize: 16, color: 'var(--ink-2)' }}>✕</button>
            </div>
            <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginBottom: 12 }}>
              Move the sliders and every figure recalculates. Salary is gross mid-level; the net share is
              each country's real tax model.
            </p>
            <BudgetEditor cities={selectedCities} budget={budget} onChange={setBudget} band="mid" />
            <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
              <button className="pill" onClick={() => downloadCsv('compass-picks.csv', selectedCities.map((c) => ({
                city: c.name,
                country: countryOf(c)?.name ?? '',
                [question.q]: question.value(c, countryOf(c)),
                salary_mid_usd: c.salary_usd_year.mid,
                kept_per_year_usd: savingsPerYear(c, 'mid'),
                years_to_home: yearsToHome(c, 'mid'),
              })))}>⤓ CSV</button>
              <Link className="pill" to={`/compare?places=${selected.slice(0, 6).join(',')}`}
                style={{ textDecoration: 'none' }}>Open in Compare →</Link>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

const cell: React.CSSProperties = {
  padding: '8px 12px', borderTop: '1px solid var(--line)', verticalAlign: 'middle',
}

export { years }
