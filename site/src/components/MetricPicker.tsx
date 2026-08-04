/* "+ add a metric" — the progressive-disclosure hinge.
 *
 * Default views stay small; everything else lives here, grouped by the seven
 * themes so depth is one click away and never a wall. */

import { useEffect, useState } from 'react'
import { METRICS, THEMES, type ThemeKey } from '../data/registry'

interface Props {
  selected: string[]
  onChange: (keys: string[]) => void
  onClose: () => void
}

export function MetricPicker({ selected, onChange, onClose }: Props) {
  const [open, setOpen] = useState<ThemeKey>('money')
  const [local, setLocal] = useState<string[]>(selected)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const toggle = (key: string) =>
    setLocal((cur) => (cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]))

  return (
    <>
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, background: 'rgba(20,19,15,.35)', zIndex: 'var(--z-sheet)' as never,
      }} />
      <div role="dialog" aria-label="Add metrics" style={{
        position: 'fixed', left: '50%', bottom: 0, transform: 'translateX(-50%)',
        width: 'min(860px, 96vw)', maxHeight: '82vh', overflow: 'auto',
        background: 'var(--surface)', borderRadius: 'var(--radius-lg) var(--radius-lg) 0 0',
        border: '1px solid var(--line)', zIndex: 'calc(var(--z-sheet) + 1)' as never,
        padding: '20px 24px 26px',
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <h3 style={{ fontSize: 'var(--text-md)' }}>Add metrics</h3>
          <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
            {local.length} shown · adding a metric never hides anything
          </span>
          <button onClick={onClose} aria-label="Close"
            style={{ marginLeft: 'auto', fontSize: 16, color: 'var(--ink-2)' }}>✕</button>
        </div>

        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', margin: '14px 0 12px' }}>
          {THEMES.map((t) => (
            <button key={t.key} className="pill" aria-pressed={open === t.key} onClick={() => setOpen(t.key)}>
              {t.label}
            </button>
          ))}
        </div>
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginBottom: 10 }}>
          {THEMES.find((t) => t.key === open)?.blurb}
        </p>

        <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))' }}>
          {METRICS.filter((m) => m.theme === open).map((m) => {
            const on = local.includes(m.key)
            return (
              <button key={m.key} onClick={() => toggle(m.key)} aria-pressed={on}
                style={{
                  textAlign: 'left', padding: '10px 12px', borderRadius: 'var(--radius-md)',
                  border: `1px solid ${on ? 'var(--accent)' : 'var(--line)'}`,
                  background: on ? 'var(--accent-wash)' : 'var(--surface)',
                }}>
                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: on ? 'var(--accent)' : 'var(--ink-1)' }}>
                  {on ? '✓ ' : '+ '}{m.label}
                </span>
                <span style={{ display: 'block', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 2 }}>
                  {m.hint}
                </span>
              </button>
            )
          })}
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 18 }}>
          <button className="btn-accent" onClick={() => { onChange(local); onClose() }}>
            Show these {local.length}
          </button>
          <button className="pill" onClick={() => setLocal([])}>Clear all</button>
        </div>
      </div>
    </>
  )
}
