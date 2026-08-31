/* Package 24, Tier 1b — "Drop a CV, or set it yourself," one line, in place
 * of the old page's two always-open panels (the CV upload block, then the
 * three-field form beneath it). Collapsed by default — the profile is
 * already meaningfully "filled" the moment the page loads, whether that is
 * DEFAULT_OCCUPATION/DEFAULT_YEARS or a shared link's own query params, so
 * there is nothing to wait on before showing a summary. Expands only when
 * tapped; a CV apply collapses it back afterward (a real completion
 * signal), a manual form edit does not (the reader is still using the
 * open panel, and auto-collapsing mid-edit would be the wrong kind of
 * "helpful"). CvUpload's own Art 50 disclosure lives inside the expanded
 * body, unchanged — required on the reading step, and this line's own
 * collapsed summary is not that step.
 */

import { useState } from 'react'
import type { Occupations } from '../../data/store'
import type { Profile } from '../../data/profile'
import { CvUpload } from '../CvUpload'
import { ProfileForm } from '../../routes/Position'

export function ProfileLine({ profile, occupations, countryName, onProfileChange }: {
  profile: Profile
  occupations: Occupations | null
  countryName: (cc: string) => string
  onProfileChange: (patch: Partial<Profile>) => void
}) {
  const [open, setOpen] = useState(false)

  // Only the RESOLVED title, never the key it resolves from: until
  // occupations.json lands, `shared_keys[...]` misses and the old fallback
  // (`?? profile.occupation`) printed the internal identifier itself —
  // "isco08:2512 · 8 yrs" on screen, caught in the loading state rather
  // than by review. The years and country come from the profile and are
  // known immediately, so the honest collapsed line is those alone until
  // the title is real.
  const occTitle = occupations?.shared_keys[profile.occupation]?.title
  const summary = [occTitle, `${profile.yearsProfessional} yrs`,
    profile.country ? countryName(profile.country) : null].filter(Boolean).join(' · ')

  return (
    <div className="panel profline" data-open={open} style={{ padding: 0, overflow: 'clip' }}>
      <button
        type="button"
        className="profline-head"
        aria-expanded={open}
        aria-controls="profline-body"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 10, width: '100%', padding: '13px 16px',
          textAlign: 'left', fontSize: 'var(--text-sm)',
        }}
      >
        <span style={{ flex: 1, fontWeight: open ? 'var(--weight-normal)' : 'var(--weight-medium)', fontVariantNumeric: 'tabular-nums' }}>
          {open ? 'Drop a CV, or set it yourself.' : summary}
        </span>
        <span aria-hidden="true" style={{
          color: 'var(--ink-3)', transition: 'transform var(--dur-fast) var(--ease-out)',
          transform: open ? 'rotate(180deg)' : undefined,
        }}>▾</span>
      </button>
      <div
        id="profline-body"
        // Accessibility review, Tier 5: max-height:0 hides this panel
        // visually (via the outer wrapper's own overflow:clip) but does
        // NOT remove its inputs from the tab order — confirmed live, a
        // keyboard user tabbing past the collapsed header landed straight
        // inside the occupation/years/country fields with no visible
        // focus anywhere on screen. `inert` removes the whole collapsed
        // subtree from focus and interaction without touching the CSS
        // transition (unlike display:none, which would break it).
        {...(open ? {} : { inert: '' })}
        style={{
          maxHeight: open ? 600 : 0, opacity: open ? 1 : 0,
          // Tier 4's own ceiling for this transition is <250ms; --dur-base
          // (260ms) narrowly misses it, --dur-fast (160ms) does not — both
          // properties on the same token rather than inventing a one-off
          // value between them (Tier 4: reduced motion stays structural,
          // via duration tokens, not a second motion contract).
          transition: 'max-height var(--dur-fast) var(--ease-out), opacity var(--dur-fast) var(--ease-out)',
        }}
      >
        <div style={{ padding: '0 16px 16px', borderTop: open ? '1px solid var(--line)' : undefined }}>
          <div style={{ marginTop: 12 }}>
            <CvUpload occupations={occupations} onApply={(patch) => { onProfileChange(patch); setOpen(false) }} />
          </div>
          <ProfileForm profile={profile} occupations={occupations} onChange={onProfileChange} />
        </div>
      </div>
    </div>
  )
}
