/* A number that can explain itself.
 *
 * The design review was explicit: no cryptic strings like "○ crowd · talent.com
 * · 2026-08" under a figure. Instead the figure is tappable and opens a small
 * card — source name, what it measures, sample size where known, date, and a
 * link that opens. This component is the only way numbers with provenance get
 * rendered, so the rule holds everywhere by construction. */

import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { CONFIDENCE_LABEL, CONFIDENCE_MARK, NO_DATA, asOfLabel, sourceName } from '../data/format'
import type { Confidence } from '../data/types'

export interface SourceInfo {
  /** Human name; derived from the URL when omitted. */
  name?: string
  url?: string
  asOf?: string
  confidence?: Confidence
  /** e.g. "10,000+ German listings" or "n = 2,024 responses" */
  sample?: string
  /** One plain sentence about what the number actually measures. */
  what?: string
  /** Shown as a warning when the figure is older than its staleness rule. */
  stale?: boolean
}

interface Props {
  children: ReactNode
  source?: SourceInfo
  /** Rendered instead of children when the value is missing. */
  missing?: boolean
  missingReason?: string
  className?: string
}

export function Figure({ children, source, missing, missingReason, className }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  const id = useId()

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('click', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (missing) {
    return (
      <span className={className}>
        <span className="nodata">{NO_DATA}</span>
        {missingReason && (
          <span style={{ display: 'block', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 3 }}>
            {missingReason}
          </span>
        )}
      </span>
    )
  }

  if (!source) return <span className={className}>{children}</span>

  const label = source.name ?? (source.url ? sourceName(source.url) : 'Source')

  return (
    <span ref={ref} className={className} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o) }}
        style={{
          borderBottom: '1px dashed var(--ink-3)',
          font: 'inherit',
          color: 'inherit',
          textAlign: 'left',
          lineHeight: 'inherit',
        }}
      >
        {children}
        <span className="visually-hidden"> — show where this number comes from</span>
      </button>

      {open && (
        <span
          id={id}
          role="dialog"
          aria-label={`Source: ${label}`}
          style={{
            position: 'absolute', left: 0, top: 'calc(100% + 7px)', zIndex: 'var(--z-popover)' as never,
            background: 'var(--ink-1)', color: 'var(--paper)', borderRadius: 'var(--radius-md)',
            padding: '10px 13px', width: 250, display: 'block', boxShadow: 'var(--shadow-lg)',
            fontFamily: 'var(--font-ui)', fontSize: 'var(--text-2xs)', fontWeight: 400,
            lineHeight: 'var(--leading-normal)', letterSpacing: 0, whiteSpace: 'normal',
          }}
        >
          <b style={{ display: 'block', marginBottom: 3 }}>{label}</b>
          {source.what && <span style={{ display: 'block', opacity: 0.85 }}>{source.what}</span>}
          {source.sample && (
            <span style={{ display: 'block', opacity: 0.85, marginTop: 3 }}>{source.sample}</span>
          )}
          <span style={{ display: 'block', marginTop: 6, opacity: 0.7 }}>
            {source.confidence && (
              <>
                {CONFIDENCE_MARK[source.confidence]} {CONFIDENCE_LABEL[source.confidence]}
                {' · '}
              </>
            )}
            {asOfLabel(source.asOf)}
          </span>
          {source.stale && (
            <span style={{ display: 'block', marginTop: 6, color: 'var(--warn)' }}>
              ⚑ Older than our freshness rule for this kind of figure — check the source before relying on it.
            </span>
          )}
          {source.url && (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--accent)', display: 'inline-block', marginTop: 6 }}
            >
              Open source ↗
            </a>
          )}
        </span>
      )}
    </span>
  )
}

/** The small tier mark used in tables and chart footers. */
export function ConfidenceChip({ tier }: { tier: Confidence }) {
  const cls = tier === 'official' ? 'chip-ok' : tier === 'index' ? 'chip-note' : 'chip-quiet'
  return (
    <span className={`chip ${cls}`} style={{ fontSize: 11, padding: '2px 9px' }}>
      {CONFIDENCE_MARK[tier]} {CONFIDENCE_LABEL[tier]}
    </span>
  )
}
