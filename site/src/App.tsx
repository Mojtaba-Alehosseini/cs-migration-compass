import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import { ThemeSwitcher } from './components/Theme'
import { ToastHost } from './components/Toast'
import { SelectionContext, useSelectionState } from './data/selection'

const NAV = [
  { to: '/compare', label: 'Compare' },
  // Package 17 — two entries became one, because they were always one
  // question: where would I stand, and what is actually open.
  { to: '/work', label: 'Position & openings' },
  { to: '/explore', label: 'Explore' },
  { to: '/data', label: 'Data & methods' },
]

export function App() {
  const { pathname } = useLocation()

  // One selection for the whole session, mounted above both routes: dots picked
  // on the field are the same list as cards ticked in Compare.
  const selection = useSelectionState()

  // Route changes move focus to the main region so keyboard and screen-reader
  // users are not left at the top of a stale document.
  useEffect(() => {
    document.getElementById('main')?.focus({ preventScroll: true })
    window.scrollTo(0, 0)
  }, [pathname])

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

          <nav style={{ display: 'flex', gap: 14 }} aria-label="Main">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                style={({ isActive }) => ({
                  fontSize: 'var(--text-xs)',
                  color: isActive ? 'var(--ink-1)' : 'var(--ink-2)',
                  textDecoration: 'none',
                  borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                  paddingBottom: 2,
                })}
              >
                {n.label}
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
            href="https://github.com/"
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
