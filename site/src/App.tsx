import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { ThemeSwitcher } from './components/Theme'

const NAV = [
  { to: '/compare', label: 'Compare' },
  { to: '/explore', label: 'Explore' },
  { to: '/data', label: 'Data & methods' },
]

export function App() {
  const { pathname } = useLocation()

  // Route changes move focus to the main region so keyboard and screen-reader
  // users are not left at the top of a stale document.
  useEffect(() => {
    document.getElementById('main')?.focus({ preventScroll: true })
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>

      <header
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
    </>
  )
}
