/* A number that shows its WORKING, not just its source.
 *
 * <Figure> is for a number one office published. This is for a number this
 * site calculated FROM one or more of those — a wage converted currency,
 * annualised, or had a component subtracted. docs/DESIGN.md's honesty
 * principle for <Figure> ("the only way a sourced number is rendered")
 * extends here: <Derived> is the only way a CALCULATED number is rendered,
 * and it shows every step, not a bare result. Package 9's normalise.py rule
 * 7: "the chain is inspectable... uncertainty compounds and the site says
 * so." This component is where that chain becomes visible.
 *
 * Same popover mechanics as <Figure> deliberately (open state, dismiss on
 * outside-click or Escape, ink-1-on-paper card, dashed-underline trigger) —
 * a derived number should feel like the same design language, not a
 * different affordance the reader has to learn twice. It differs only where
 * the content genuinely differs: an ORDERED chain of steps instead of one
 * source blurb, because a derivation has a method, not a single citation. */

import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import type { ChainStep } from '../data/explore'

export interface DerivedConcept {
  /** The office's own term, in its own language — e.g. "Standardberegnet månedsfortjeneste". */
  name: string
  office: string
  /** One plain sentence: what this figure includes that others might not. */
  includes?: string
  /** One plain sentence: what it excludes. */
  excludes?: string
}

export interface DerivedNative {
  value: number
  currency: string
  period: 'hour' | 'month' | 'year'
  year: number
}

interface Props {
  children: ReactNode
  chain: ChainStep[]
  native?: DerivedNative
  concept?: DerivedConcept
  /** Sourced background from pay_composition.json's pay_cycle_context — WHY
   *  this source differs from others, kept visually separate from the chain
   *  itself since it explains, it never adjusts a number. */
  payCycleNote?: string
  className?: string
}

const PERIOD_LABEL: Record<DerivedNative['period'], string> = { hour: '/hour', month: '/month', year: '/year' }

export function Derived({ children, chain, native, concept, payCycleNote, className }: Props) {
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
        <span className="visually-hidden"> — show how this number was calculated</span>
      </button>

      {open && (
        <span
          id={id}
          role="dialog"
          aria-label={concept ? `Method: ${concept.name}` : 'Method'}
          style={{
            position: 'absolute', left: 0, top: 'calc(100% + 7px)', zIndex: 'var(--z-popover)' as never,
            background: 'var(--ink-1)', color: 'var(--paper)', borderRadius: 'var(--radius-md)',
            padding: '11px 14px', width: 300, display: 'block', boxShadow: 'var(--shadow-lg)',
            fontFamily: 'var(--font-ui)', fontSize: 'var(--text-2xs)', fontWeight: 400,
            lineHeight: 'var(--leading-normal)', letterSpacing: 0, whiteSpace: 'normal',
          }}
        >
          {concept && (
            <>
              <b style={{ display: 'block' }}>{concept.name}</b>
              <span style={{ display: 'block', opacity: 0.7, marginBottom: 6 }}>{concept.office}</span>
              {concept.includes && (
                <span style={{ display: 'block', opacity: 0.85 }}>Includes: {concept.includes}</span>
              )}
              {concept.excludes && (
                <span style={{ display: 'block', opacity: 0.85, marginBottom: 6 }}>Excludes: {concept.excludes}</span>
              )}
            </>
          )}

          <span style={{ display: 'block', marginTop: concept ? 6 : 0, opacity: 0.6, fontSize: 'var(--text-2xs)' }}>
            HOW THIS NUMBER WAS CALCULATED
          </span>
          <ol style={{ margin: '4px 0 0', paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {native && (
              <li style={{ opacity: 0.85 }}>
                published: {native.value.toLocaleString()} {native.currency}{PERIOD_LABEL[native.period]} ({native.year})
              </li>
            )}
            {chain.map((step, i) => (
              <li key={i} style={{ opacity: 0.85 }}>{step.detail}</li>
            ))}
          </ol>

          {payCycleNote && (
            <span style={{ display: 'block', marginTop: 8, opacity: 0.7, borderTop: '1px solid rgba(255,255,255,0.15)', paddingTop: 6 }}>
              {payCycleNote}
            </span>
          )}
        </span>
      )}
    </span>
  )
}
