/* The optional profile.
 *
 * Rules from the brief, enforced here:
 *   - it appears only AFTER the first data interaction, never before
 *   - it is dismissible and stays dismissed
 *   - it only affects computed lenses; it never hides or filters away data
 *   - every filter is off by default, including visa feasibility, because a
 *     remote worker comparing places has no visa question at all */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const KEY = 'compass:profile-dismissed'

export function ProfileNudge({ active }: { active: boolean }) {
  const [dismissed, setDismissed] = useState(true)

  useEffect(() => {
    try { setDismissed(localStorage.getItem(KEY) === '1') } catch { setDismissed(false) }
  }, [])

  if (!active || dismissed) return null

  return (
    <div
      className="panel"
      style={{
        marginTop: 12, display: 'flex', gap: 14, alignItems: 'baseline', flexWrap: 'wrap',
        borderStyle: 'dashed',
      }}
    >
      <div style={{ flex: 1, minWidth: 260 }}>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>
          Want the numbers adjusted to you?
        </div>
        <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginTop: 3 }}>
          Experience level, whether you have a family, your passport, how much language learning you
          are up for. It only changes the calculated figures — nothing gets hidden or filtered out,
          and you can skip it entirely.
        </p>
      </div>
      <Link className="pill" to="/compare?profile=1" style={{ textDecoration: 'none' }}>
        Set it up
      </Link>
      <button
        className="pill"
        onClick={() => {
          setDismissed(true)
          try { localStorage.setItem(KEY, '1') } catch { /* private mode */ }
        }}
      >
        No thanks
      </button>
    </div>
  )
}
