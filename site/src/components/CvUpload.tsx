/* Package 22, Tier 3 — wires the CV reader into the existing three-field
 * form (package 10's ProfileForm, Position.tsx) instead of building a
 * different one. The model is a convenience, not an authority: every
 * extracted value is shown for the reader to check before anything is
 * applied, and the form path below this component keeps working
 * identically, with no network at all, whether or not a CV is ever
 * uploaded.
 *
 * AI Act Article 50 applies HERE, and only here — this is the one step
 * where a user interacts with an AI system. It does not apply to the
 * position or the estimate elsewhere on this page: those are published
 * statistics and a regression written in this repo, and labelling THEM as
 * AI-generated would be its own inaccuracy (see data/profile.ts's own
 * header for why the two are already kept in different visual registers).
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { Occupations } from '../data/store'
import { extractCvText } from '../cv/extractText'
import { stripPii, type PiiRedaction } from '../cv/stripPii'
import { renderTurnstile, type TurnstileHandle } from '../cv/turnstile'
import { analyseCv, type CvProfile } from '../cv/analyseCv'
import {
  RETENTION_DAYS, deleteProfile, forgetKey, hasKey, loadProfile, mintKey, saveProfile,
  type VaultRecord,
} from '../cv/vault'

const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY as string | undefined

type Stage =
  | { kind: 'idle' }
  | { kind: 'extracting' }
  | { kind: 'scanned' }
  | { kind: 'reviewing'; text: string; redactions: PiiRedaction[] }
  // The text awaiting analysis lives in pendingTextRef, not here — kept OUT
  // of Stage deliberately: an earlier version carried it in these two
  // variants and read it from a callback ref's own closure, which meant
  // the Turnstile widget got destroyed and re-rendered on the
  // awaiting-turnstile -> analysing transition (a new stage VALUE gives a
  // callback ref a new identity, and React unmounts/remounts on that).
  | { kind: 'awaiting-turnstile' }
  | { kind: 'analysing' }
  | { kind: 'result'; profile: CvProfile; modelUsed: string }
  | { kind: 'error'; code: string; message: string }

const ERROR_COPY: Record<string, string> = {
  turnstile_missing: 'The human check did not complete — try again.',
  turnstile_failed: 'The human check did not pass — try again.',
  rate_limited: 'Too many attempts in a short window — wait a minute and try again.',
  daily_cap_exceeded: 'This site’s CV reader has used up today’s budget — try again tomorrow, or fill in the form below.',
  model_unavailable: 'The CV reader is temporarily unavailable — fill in the form below instead.',
  upstream_failure: 'The CV reader had a problem reading the response — try again, or fill in the form below.',
  malformed_input: 'That file could not be processed — fill in the form below instead.',
  network_error: 'Could not reach the CV reader — check your connection and try again.',
  worker_not_configured: 'The CV reader is not set up on this deployment — fill in the form below instead.',
}

const RED_LABEL: Record<PiiRedaction['category'], string> = {
  email: 'email address', phone: 'phone number', url: 'link', address: 'postal address', name: 'name',
}

function redactionSummary(redactions: PiiRedaction[]): string {
  if (redactions.length === 0) return 'Nothing matching an email, phone number, address, link or name was found to remove.'
  const counts = new Map<PiiRedaction['category'], number>()
  for (const r of redactions) counts.set(r.category, (counts.get(r.category) ?? 0) + 1)
  const parts = [...counts.entries()].map(([cat, n]) => `${n} ${RED_LABEL[cat]}${n > 1 ? (cat === 'address' ? 'es' : 's') : ''}`)
  return `Removed before anything was sent: ${parts.join(', ')}.`
}

export function CvUpload({ occupations, onApply, active }: {
  occupations: Occupations | null
  onApply: (patch: { occupation?: string; yearsProfessional: number }) => void
  /** Whether the panel this lives in is actually open. ProfileLine keeps
   *  this component MOUNTED while collapsed (max-height, not unmount), so
   *  without this the stored-profile read would fire on every /work page
   *  load for a reader who has opted in. Package 22's second property is
   *  that nothing is sent until the reader asks for it; a read that happens
   *  because a page rendered is not the reader asking. */
  active: boolean
}) {
  const [stage, setStage] = useState<Stage>({ kind: 'idle' })
  const fileInputRef = useRef<HTMLInputElement>(null)
  const turnstileContainerRef = useRef<HTMLDivElement>(null)
  const turnstileHandleRef = useRef<TurnstileHandle | null>(null)
  // The reviewed text, stable across the awaiting-turnstile -> analysing
  // transition — a ref rather than component state so mounting the
  // widget (the effect below) does not depend on a value that changes
  // partway through the very flow the widget is running.
  const pendingTextRef = useRef<string | null>(null)

  const handleFile = useCallback(async (file: File) => {
    setStage({ kind: 'extracting' })
    try {
      const extracted = await extractCvText(file)
      if (extracted.scanned) {
        setStage({ kind: 'scanned' })
        return
      }
      const { text, redactions } = stripPii(extracted.text)
      setStage({ kind: 'reviewing', text, redactions })
    } catch {
      setStage({ kind: 'error', code: 'malformed_input', message: ERROR_COPY.malformed_input! })
    }
  }, [])

  const startAnalysis = useCallback((text: string) => {
    pendingTextRef.current = text
    setStage({ kind: 'awaiting-turnstile' })
  }, [])

  // Mounts the Turnstile widget exactly once per entry into
  // awaiting-turnstile (the dependency is stage.KIND, a string, not the
  // Stage object itself, so a later transition to 'analysing' — a
  // DIFFERENT kind — does not re-run this and does not re-mount the
  // widget the first run already created).
  useEffect(() => {
    if (stage.kind !== 'awaiting-turnstile') return
    const node = turnstileContainerRef.current
    if (!node || !TURNSTILE_SITE_KEY) {
      setStage({ kind: 'error', code: 'turnstile_failed', message: 'The human check is not configured on this deployment.' })
      return
    }
    let cancelled = false
    renderTurnstile(node, TURNSTILE_SITE_KEY).then((handle) => {
      if (cancelled) { handle.remove(); return }
      turnstileHandleRef.current = handle
      handle.onToken(async (token) => {
        const text = pendingTextRef.current
        if (text == null) return
        setStage({ kind: 'analysing' })
        const outcome = await analyseCv(text, token)
        handle.reset() // tokens are single-use; a retry needs a fresh one
        if (outcome.ok) setStage({ kind: 'result', profile: outcome.profile, modelUsed: outcome.modelUsed })
        else setStage({ kind: 'error', code: outcome.code, message: ERROR_COPY[outcome.code] ?? outcome.message })
      })
      handle.onError(() => {
        setStage({ kind: 'error', code: 'turnstile_failed', message: ERROR_COPY.turnstile_failed! })
      })
    }).catch(() => {
      if (!cancelled) {
        setStage({ kind: 'error', code: 'turnstile_failed', message: 'Could not load the human check — try again.' })
      }
    })
    return () => { cancelled = true }
  }, [stage.kind])

  const reset = useCallback(() => {
    turnstileHandleRef.current?.remove()
    turnstileHandleRef.current = null
    pendingTextRef.current = null
    if (fileInputRef.current) fileInputRef.current.value = ''
    setStage({ kind: 'idle' })
  }, [])

  // Package 23, Tier 3 — no longer calls reset(). The result used to
  // vanish the instant it was applied (the whole panel snapped back to
  // "Choose File — no file chosen"), so there was nothing left on screen
  // to check the applied values against, no way to re-apply after a
  // second thought, and no way to re-read the model's own evidence
  // sentence. Applying now just forwards the patch upward; the result
  // (and CvResult's own "Applied" confirmation) stays exactly where it
  // was. reset() is still what the explicit Discard button calls — the
  // work order's own "a way to discard deliberately".
  const applyResult = useCallback((patch: { occupation?: string; yearsProfessional: number }) => {
    onApply(patch)
  }, [onApply])

  return (
    <div className="panel" style={{ marginBottom: 14 }}>
      <h2>Read it from a CV instead</h2>
      <div className="sub">
        <span className="chip chip-note" style={{ marginRight: 6 }}>AI-assisted</span>
        A model reads your CV into occupation and years of experience — the same two fields below,
        filled in for you to check, not an authority you have to accept. It never sees or produces a
        pay figure: its own response format has no field for one.
      </div>

      <SavedProfile onApply={onApply} occupations={occupations} active={active} />

      {stage.kind === 'idle' && (
        <div style={{ marginTop: 10 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void handleFile(f) }}
            style={{ fontSize: 'var(--text-xs)' }}
          />
          <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 6 }}>
            PDF only. The file is read in your browser and never uploaded — only the text below, once
            you have checked it, is ever sent anywhere.
          </p>
        </div>
      )}

      {stage.kind === 'extracting' && <p className="nodata">Reading your CV…</p>}

      {stage.kind === 'scanned' && (
        <div style={{ marginTop: 10 }}>
          <p className="nodata">
            This PDF has no readable text (it may be a scanned image) — nothing was sent anywhere.
            Fill in the form below instead.
          </p>
          <button className="btn-accent" onClick={reset} style={{ marginTop: 8 }}>Try another file</button>
        </div>
      )}

      {stage.kind === 'reviewing' && (
        <div style={{ marginTop: 10 }}>
          <p style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-medium)' }}>
            This is exactly what would be sent — nothing has been sent yet.
          </p>
          <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)' }}>{redactionSummary(stage.redactions)}</p>
          <textarea
            readOnly
            value={stage.text}
            rows={10}
            style={{
              width: '100%', marginTop: 6, padding: 8, fontSize: 'var(--text-2xs)',
              fontFamily: 'monospace', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)',
              background: 'var(--surface)', color: 'var(--ink-1)', resize: 'vertical',
            }}
          />
          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
            <button className="btn-accent" onClick={() => startAnalysis(stage.text)}>
              Looks right — analyse it
            </button>
            <button onClick={reset} className="pill">Cancel</button>
          </div>
        </div>
      )}

      {(stage.kind === 'awaiting-turnstile' || stage.kind === 'analysing') && (
        <div style={{ marginTop: 10 }}>
          <div ref={turnstileContainerRef} style={stage.kind === 'analysing' ? { display: 'none' } : undefined} />
          {stage.kind === 'analysing' && (
            <p className="nodata" style={{ marginTop: 8 }}>
              Reading your CV… this takes a few seconds. Your file never left your browser; only the
              text you reviewed above was sent, over a connection this page's own security policy
              only allows to the CV reader itself.
            </p>
          )}
        </div>
      )}

      {stage.kind === 'error' && (
        <div style={{ marginTop: 10 }}>
          <span className="chip chip-risk">{stage.message}</span>
          <div style={{ marginTop: 8 }}>
            <button className="btn-accent" onClick={reset}>Try again</button>
          </div>
        </div>
      )}

      {stage.kind === 'result' && (
        <CvResult
          profile={stage.profile}
          modelUsed={stage.modelUsed}
          occupations={occupations}
          onApply={applyResult}
          onDiscard={reset}
        />
      )}
    </div>
  )
}

const day = (ms: number) => new Date(ms).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })

/* NEEDS-DECISION #56 — what a returning reader sees, and the only reason
 * storing anything is worth doing.
 *
 * It renders NOTHING unless this browser holds a token, so a reader who has
 * never opted in never sees a control about storage, and a reader who
 * deleted sees it disappear. The record is read once on mount; a failure to
 * reach the store is shown as a failure, never as "nothing saved", because
 * those two mean opposite things to someone deciding whether to upload
 * their CV again.
 */
function SavedProfile({ onApply, occupations, active }: {
  onApply: (patch: { occupation?: string; yearsProfessional: number }) => void
  occupations: Occupations | null
  active: boolean
}) {
  const [state, setState] = useState<
    | { kind: 'none' } | { kind: 'loading' } | { kind: 'have'; record: VaultRecord }
    | { kind: 'failed'; message: string } | { kind: 'deleted' }
  >(() => (hasKey() ? { kind: 'loading' } : { kind: 'none' }))
  const [busy, setBusy] = useState(false)

  // Once, on the first open — not on every re-render of an open panel, and
  // not at all while it is closed.
  const asked = useRef(false)
  useEffect(() => {
    if (!active || asked.current || !hasKey()) return
    asked.current = true
    let cancelled = false
    void loadProfile().then((r) => {
      if (cancelled) return
      if (!r.ok) setState({ kind: 'failed', message: r.message })
      else if (r.value.record) setState({ kind: 'have', record: r.value.record })
      else setState({ kind: 'none' })
    })
    return () => { cancelled = true }
  }, [active])

  const remove = async () => {
    setBusy(true)
    const gone = await deleteProfile()
    if (!gone.ok) {
      setState({ kind: 'failed', message: gone.message })
      setBusy(false)
      return
    }
    // Verified, not assumed: read it back with the key still in hand before
    // dropping the key. A delete path that reports success from the fact
    // that the request did not throw is not a delete path.
    const after = await loadProfile()
    if (after.ok && after.value.record) {
      setState({ kind: 'failed', message: 'The store still returns a record — it has not been deleted.' })
      setBusy(false)
      return
    }
    forgetKey()
    setState({ kind: 'deleted' })
    setBusy(false)
  }

  if (state.kind === 'none') return null
  if (state.kind === 'loading') return <p className="nodata" style={{ marginTop: 10 }}>Checking what you saved…</p>
  if (state.kind === 'deleted') {
    return (
      <p className="nodata" style={{ marginTop: 10 }}>
        Deleted. The record is gone from the store and this browser no longer holds the key to it.
      </p>
    )
  }
  if (state.kind === 'failed') {
    return (
      <p style={{ marginTop: 10 }}>
        <span className="chip chip-risk">{state.message}</span>
      </p>
    )
  }

  const { record } = state
  const title = record.occupation ? occupations?.shared_keys[record.occupation]?.title : null
  return (
    <div className="panel" style={{ marginTop: 10, background: 'var(--surface-sunk)' }}>
      <p style={{ fontSize: 'var(--text-xs)', margin: 0 }}>
        <strong>Saved from this browser on {day(record.savedAt)}.</strong>{' '}
        {record.occupation
          ? <>Occupation <strong>{title ?? record.occupation}</strong> and </>
          : <>No occupation, and </>}
        <strong>{record.yearsProfessional}</strong> {record.yearsProfessional === 1 ? 'year' : 'years'} of
        experience. That is all of it — no CV, no text from one. It deletes itself on {day(record.expiresAt)}.
      </p>
      <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button
          className="btn-accent"
          onClick={() => onApply(record.occupation
            ? { occupation: record.occupation, yearsProfessional: record.yearsProfessional }
            : { yearsProfessional: record.yearsProfessional })}
        >
          Put it back in the form
        </button>
        <button className="pill" onClick={() => void remove()} disabled={busy}>
          {busy ? 'Deleting…' : 'Delete it'}
        </button>
      </div>
    </div>
  )
}

const SELECT_STYLE = {
  display: 'block', width: '100%', marginTop: 2, padding: '5px 6px',
  border: '1px solid var(--line)', background: 'var(--surface)',
  borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)', color: 'var(--ink-1)',
} as const

function CvResult({ profile, modelUsed, occupations, onApply, onDiscard }: {
  profile: CvProfile
  modelUsed: string
  occupations: Occupations | null
  onApply: (patch: { occupation?: string; yearsProfessional: number }) => void
  onDiscard: () => void
}) {
  const key = `isco08:${profile.occupation.isco08}`
  const resolved = occupations?.shared_keys[key]
  // Package 23, Tier 3 — the model's own reading is a starting point, not
  // an authority: both fields are edited HERE, in local state, before
  // anything reaches the form below. An unresolved code starts the select
  // on the placeholder rather than guessing a real occupation for the
  // reader — the code below still tracks that this is initialised ONCE
  // per fresh result (a new analysis mounts a new CvResult instance), not
  // re-derived on every render.
  const [years, setYears] = useState(profile.years_professional)
  const [occupationKey, setOccupationKey] = useState(resolved ? key : '')
  const [applied, setApplied] = useState(false)
  /* NEEDS-DECISION #56, Tier 4 — a SECOND consent, not the Article 50 chip
   * widened. That chip says a model read this; this says a copy is kept.
   * They are different processing purposes and the reader agrees to them
   * separately, so this starts false and nothing above it can set it. */
  const [keepIt, setKeepIt] = useState(false)
  const [saveState, setSaveState] = useState<
    { kind: 'idle' } | { kind: 'saving' } | { kind: 'saved'; expiresAt: number } | { kind: 'failed'; message: string }
  >({ kind: 'idle' })

  if (profile.status === 'incomplete') {
    return (
      <div style={{ marginTop: 10 }}>
        <p className="nodata">
          Not enough was found in this CV to confidently fill in occupation and years of experience.
          Fill in the form below instead.
        </p>
        <button className="btn-accent" onClick={onDiscard} style={{ marginTop: 8 }}>Try another file</button>
      </div>
    )
  }

  const options = occupations
    ? Object.entries(occupations.shared_keys)
      .sort((a, b) => a[1].level - b[1].level || a[1].title.localeCompare(b[1].title))
    : []

  const handleApply = () => {
    onApply(occupationKey ? { occupation: occupationKey, yearsProfessional: years }
      : { yearsProfessional: years })
    setApplied(true)
    if (keepIt) void store()
  }

  /* NEEDS-DECISION #56, Tier 4. Minting the token here and not earlier is
   * deliberate: until this runs, this browser carries no identifier for
   * this site at all. */
  const store = async () => {
    setSaveState({ kind: 'saving' })
    if (!mintKey()) {
      setSaveState({ kind: 'failed', message: 'This browser will not keep the key, so there is nothing to save to.' })
      return
    }
    const r = await saveProfile({ occupation: occupationKey || null, yearsProfessional: years })
    if (!r.ok) {
      // A token that was minted for a save that never happened is an
      // identifier with no purpose. Drop it again.
      forgetKey()
      setSaveState({ kind: 'failed', message: r.message })
      return
    }
    setSaveState({ kind: 'saved', expiresAt: r.value.record.expiresAt })
  }

  return (
    <div style={{ marginTop: 10 }}>
      <table style={{ width: '100%', fontSize: 'var(--text-xs)', borderCollapse: 'collapse' }}>
        <tbody>
          <tr>
            <td style={{ padding: '4px 8px 4px 0', color: 'var(--ink-2)', verticalAlign: 'top' }}>Occupation</td>
            <td style={{ padding: '4px 0' }}>
              <select value={occupationKey} onChange={(e) => setOccupationKey(e.target.value)} style={SELECT_STYLE}>
                {!resolved && (
                  <option value="">
                    unclassified — ISCO-08 {profile.occupation.isco08} (not mapped yet; pick one or leave
                    the form's current occupation unchanged)
                  </option>
                )}
                {options.map(([k, meta]) => (
                  <option key={k} value={k}>{meta.title} ({k})</option>
                ))}
              </select>
              {!resolved && !occupationKey && (
                <span style={{ display: 'block', marginTop: 4, color: 'var(--ink-3)', fontSize: 'var(--text-2xs)' }}>
                  This site does not yet have wage data mapped to that code, so the form's occupation
                  will not change unless you pick one above.
                </span>
              )}
            </td>
          </tr>
          <tr>
            <td style={{ padding: '4px 8px 4px 0', color: 'var(--ink-2)' }}>Confidence</td>
            <td style={{ padding: '4px 0' }}>{profile.occupation.confidence}</td>
          </tr>
          <tr>
            <td style={{ padding: '4px 8px 4px 0', color: 'var(--ink-2)', verticalAlign: 'top' }}>Evidence</td>
            <td style={{ padding: '4px 0' }}>{profile.occupation.evidence}</td>
          </tr>
          <tr>
            <td style={{ padding: '4px 8px 4px 0', color: 'var(--ink-2)', verticalAlign: 'top' }}>Years of experience</td>
            <td style={{ padding: '4px 0' }}>
              <input
                type="number" min={0} max={50} step={0.5} value={years}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  if (Number.isFinite(v) && v >= 0) setYears(v)
                }}
                style={{ ...SELECT_STYLE, width: 90 }}
              />
              {/* Package 23, Tier 5 — years_professional is a total-career
                  elapsed figure the model can get wrong in genuinely
                  ambiguous ways (a gap, an overlap, a CV's own narrower
                  stated figure); years_evidence is where it says what the
                  number came from instead of presenting it with false
                  confidence, shown here so a reader can judge it before
                  applying, the same way occupation's own evidence is shown
                  above. */}
              <span style={{ display: 'block', marginTop: 4, color: 'var(--ink-3)', fontSize: 'var(--text-2xs)' }}>
                Based on: {profile.years_evidence}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 6 }}>
        Read by {modelUsed} — check this against your own CV, correct it above if needed, before
        applying it below.
      </p>
      {/* The record, in the words it is kept in — before the box that agrees
          to keep it, not in a policy page behind a link. */}
      <label
        style={{
          display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 10, padding: '8px 10px',
          border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)',
          background: 'var(--surface-sunk)', fontSize: 'var(--text-2xs)', color: 'var(--ink-2)',
        }}
      >
        <input
          type="checkbox"
          checked={keepIt}
          onChange={(e) => setKeepIt(e.target.checked)}
          style={{ marginTop: 2 }}
        />
        <span>
          <strong style={{ color: 'var(--ink-1)' }}>Also keep these two values, so this browser can
          fill them in next time.</strong> Kept: the occupation
          {occupationKey ? <> (<span className="tnum">{occupationKey}</span>)</> : ' (none — you have not picked one)'}
          {' '}and the number {years}. Not kept: your CV, its text, or anything the model quoted from
          it. It is stored against a random key this browser generates now and holds only here — not
          an account, and not something that can be matched to you. It is deleted automatically after{' '}
          <strong>{RETENTION_DAYS} days</strong>, and you can delete it yourself at any time from the
          panel above. Leave this unticked and nothing is kept.
          {' '}<span style={{ color: 'var(--ink-3)' }}>
            The other side of that: clear this browser&rsquo;s data and the key goes with it, so
            nobody can reach the record again — not you, not this site. It then expires unread.
          </span>
        </span>
      </label>

      <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="btn-accent" onClick={handleApply}>
          Apply {occupationKey ? 'occupation and ' : ''}years of experience to the form below
          {keepIt ? ', and keep them' : ''}
        </button>
        <button onClick={onDiscard} className="pill">Discard</button>
        {applied && <span className="chip chip-note">Applied ✓ — edit above and apply again anytime</span>}
        {saveState.kind === 'saving' && <span className="nodata">Saving…</span>}
        {saveState.kind === 'saved' && (
          <span className="chip chip-note">Kept ✓ — deletes itself on {day(saveState.expiresAt)}</span>
        )}
        {saveState.kind === 'failed' && <span className="chip chip-risk">{saveState.message}</span>}
      </div>
    </div>
  )
}
