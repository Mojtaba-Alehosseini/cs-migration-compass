import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import { ThemeSwitcher } from './components/Theme'
import { ToastHost } from './components/Toast'
import { SelectionContext, useSelectionState } from './data/selection'
import { REPO_URL } from './lib/fileLink'

/* `short` is what the link SHOWS below 560px (NEEDS-DECISION #77, ruled in
 * package 44). It is never what the link is CALLED: `label` is the accessible
 * name at every width, so a control does not answer to one name on a phone and
 * another on a laptop — which would be a worse inconsistency than the one the
 * ruling is fixing, and the reason option (a) was not chosen was that it
 * created a mismatch of exactly that kind between focus order and visual order.
 *
 * WCAG 2.5.3 (Label in Name) wants the accessible name to contain the visible
 * text: "Openings" is inside "Position & openings" and "Data" is inside
 * "Data & methods", so the short form is a substring of the name in both cases
 * and a speech-input user asking for what they can see still reaches the link. */
const NAV = [
  { to: '/compare', label: 'Compare' },
  // Package 17 — two entries became one, because they were always one
  // question: where would I stand, and what is actually open.
  { to: '/work', label: 'Position & openings', short: 'Openings' },
  { to: '/explore', label: 'Explore' },
  { to: '/data', label: 'Data & methods', short: 'Data' },
] as { to: string; label: string; short?: string }[]

export function App() {
  const { pathname, hash } = useLocation()

  // One selection for the whole session, mounted above both routes: dots picked
  // on the field are the same list as cards ticked in Compare.
  const selection = useSelectionState()

  // Route changes move focus to the main region so keyboard and screen-reader
  // users are not left at the top of a stale document.
  useEffect(() => {
    document.getElementById('main')?.focus({ preventScroll: true })
    // A fragment on a hash route is a real destination, and this used to scroll
    // unconditionally to the top and strand it. /position?years=8#c-DK
    // redirects to /work carrying both — the query took effect and the fragment
    // did nothing, so a shared deep link into a country section landed 9,600px
    // above it. The target usually mounts after this effect (its data is still
    // loading), so retry briefly rather than once.
    if (!hash) { window.scrollTo(0, 0); return }
    const id = hash.slice(1)
    let tries = 0
    const tick = () => {
      const el = document.getElementById(id)
      if (el) { el.scrollIntoView({ block: 'start' }); return }
      if (++tries < 20) window.setTimeout(tick, 150)
    }
    tick()
  }, [pathname, hash])

  // Compare's table header parks under this header while the table scrolls, so
  // it needs the header's real height. It is a wrapping flex row, so the height
  // is a measurement rather than a constant — the CSS carries a sane default
  // and this keeps it honest at any width or zoom.
  const headerRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const el = headerRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const apply = () => document.documentElement.style
      .setProperty('--header-h', `${Math.round(el.getBoundingClientRect().height)}px`)
    apply()
    const ro = new ResizeObserver(apply)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return (
    <SelectionContext.Provider value={selection}>
    <ToastHost>
      {/* A BUTTON, not `href="#main"`. The router is a hash router, so a bare
        * fragment does not address an element — it replaces the route, and the
        * first keyboard-reachable control on every page of this site landed on
        * "That page isn't here". <main> already carries tabIndex={-1} for the
        * route-change focus move above, so focusing it is all this ever needed
        * to do. Adversarial review, package 17. */}
      <button
        type="button"
        className="skip-link"
        onClick={() => {
          const m = document.getElementById('main')
          m?.focus()
          m?.scrollIntoView({ block: 'start' })
        }}
      >Skip to content</button>

      <header
        ref={headerRef}
        style={{
          position: 'sticky', top: 0, zIndex: 'var(--z-sticky)' as never,
          background: 'var(--paper)', borderBottom: '1px solid var(--line)',
        }}
      >
        <div
          className="wrap"
          style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '11px 22px', flexWrap: 'wrap' }}
        >
          <NavLink
            to="/"
            style={{
              display: 'flex', gap: 8, alignItems: 'center', textDecoration: 'none',
              color: 'var(--ink-1)', fontWeight: 600, fontSize: 'var(--text-xs)',
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 10, height: 10, borderRadius: '50%',
                background: 'conic-gradient(var(--accent) 0 60%, var(--warn) 60% 100%)',
              }}
            />
            Compass
          </NavLink>

          {/* gap lives in .mainnav, not here: an inline style would beat the
            * media query that tightens it on a phone, which is the whole
            * mechanism that keeps these four labels on one line at 390px. */}
          <nav className="mainnav" aria-label="Main">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                // Constant across every viewport. Only the SHOWN text changes.
                aria-label={n.short ? n.label : undefined}
                style={({ isActive }) => ({
                  fontSize: 'var(--text-xs)',
                  color: isActive ? 'var(--ink-1)' : 'var(--ink-2)',
                  textDecoration: 'none',
                  borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                  paddingBottom: 2,
                })}
              >
                {n.short ? (
                  <>
                    <span className="nav-long">{n.label}</span>
                    <span className="nav-short">{n.short}</span>
                  </>
                ) : n.label}
              </NavLink>
            ))}
          </nav>

          <div style={{ marginLeft: 'auto' }}>
            <ThemeSwitcher />
          </div>
        </div>
      </header>

      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>
        <Outlet />
      </main>

      <footer
        style={{
          borderTop: '1px solid var(--line)', marginTop: 60, padding: '22px 0 50px',
          fontSize: 'var(--text-2xs)', color: 'var(--ink-3)',
        }}
      >
        <div className="wrap" style={{ display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'baseline' }}>
          <span>
            We show the data. We never rank places or tell you where to go.
          </span>
          <NavLink to="/data" style={{ color: 'var(--ink-2)' }}>How every number is sourced →</NavLink>
          <a
            href={REPO_URL}
            style={{ marginLeft: 'auto', color: 'var(--ink-2)' }}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open source ↗
          </a>
        </div>
      </footer>
    </ToastHost>
    </SelectionContext.Provider>
  )
}
