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
  /** Ordered arithmetic steps, when this figure involved real computation
   *  over the cited source's own numbers (e.g. package 11's personalised
   *  position: an age band's own value, ranked against this same source's
   *  own percentile table) — still ONE source, still <Figure>'s own
   *  "actual" register, just showing its working rather than a bare
   *  citation. <Derived>'s own chain is for numbers a METHOD produced, not
   *  a single source's own real numbers; this is for the latter. Omit for
   *  a plain citation with nothing to reproduce by hand. */
  steps?: string[]
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

  // Finding F16, adversarial review: a fixed-width, left-anchored-to-trigger
  // popover can extend past a narrow viewport's own right edge when its
  // trigger sits anywhere but the far left of the row — confirmed live at
  // 390px (a trigger at left:143 + a 300px popover = right:443, 53px past
  // the 390px viewport), not just the reviewer's own reasoned risk. Below
  // this width the popover switches from anchored-under-trigger to
  // centered-on-viewport, which cannot overflow regardless of where the
  // trigger sits.
  const [narrow, setNarrow] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 480px)')
    const update = () => setNarrow(mq.matches)
    update()
    mq.addEventListener('change', update)
    return () => mq.removeEventListener('change', update)
  }, [])

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
          style={narrow ? {
            position: 'fixed', left: '50%', top: '50%', transform: 'translate(-50%, -50%)',
            zIndex: 'var(--z-popover)' as never,
            background: 'var(--ink-1)', color: 'var(--paper)', borderRadius: 'var(--radius-md)',
            padding: '10px 13px', width: 'calc(100vw - 32px)', maxHeight: '80vh', overflowY: 'auto',
            display: 'block', boxShadow: 'var(--shadow-lg)',
            fontFamily: 'var(--font-ui)', fontSize: 'var(--text-2xs)', fontWeight: 400,
            lineHeight: 'var(--leading-normal)', letterSpacing: 0, whiteSpace: 'normal',
          } : {
            position: 'absolute', left: 0, top: 'calc(100% + 7px)', zIndex: 'var(--z-popover)' as never,
            background: 'var(--ink-1)', color: 'var(--paper)', borderRadius: 'var(--radius-md)',
            padding: '10px 13px', width: source.steps ? 300 : 250, display: 'block', boxShadow: 'var(--shadow-lg)',
            fontFamily: 'var(--font-ui)', fontSize: 'var(--text-2xs)', fontWeight: 400,
            lineHeight: 'var(--leading-normal)', letterSpacing: 0, whiteSpace: 'normal',
          }}
        >
          <b style={{ display: 'block', marginBottom: 3 }}>{label}</b>
          {source.what && <span style={{ display: 'block', opacity: 0.85 }}>{source.what}</span>}
          {source.sample && (
            <span style={{ display: 'block', opacity: 0.85, marginTop: 3 }}>{source.sample}</span>
          )}
          {source.steps && source.steps.length > 0 && (
            <>
              <span style={{ display: 'block', marginTop: 6, opacity: 0.6 }}>
                HOW THIS NUMBER WAS CALCULATED
              </span>
              {/* <ol>/<li> here used to nest inside this popover's own <span
                  role="dialog">, which HTML5 does not allow (span is
                  phrasing content only; ol is flow content) — browsers
                  render it via error-recovery either way, so this was never
                  visibly broken, but it is not spec-valid markup (finding
                  F15, adversarial review). Same visual result, built from
                  phrasing-content-only spans, ordinal shown as plain text. */}
              <span style={{ margin: '4px 0 0', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {source.steps.map((step, i) => (
                  // Leading/trailing spaces are real characters here, not just
                  // visual gap — sibling spans concatenate with NO inserted
                  // whitespace in .textContent (flexbox `gap` is paint-only),
                  // so "...same basis" immediately followed by "5." immediately
                  // followed by "55,500" read back as one run-on token to
                  // anything doing plain-text extraction — a screen reader's
                  // accessible-name computation, copy-paste, or (caught by)
                  // this package's own gate-1 arithmetic-reproduction check,
                  // which silently mismatched two adjacent numbers into one
                  // unparseable string. Found re-verifying this same fix
                  // (finding F15's remediation), not by the original review.
                  <span key={i} style={{ display: 'flex', gap: 6, opacity: 0.85 }}>
                    <span style={{ opacity: 0.6, flexShrink: 0 }}>{` ${i + 1}.`}</span>
                    <span>{` ${step}`}</span>
                  </span>
                ))}
              </span>
            </>
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
