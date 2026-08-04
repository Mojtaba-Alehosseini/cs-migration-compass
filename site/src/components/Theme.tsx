/* Theme + mode, persisted in localStorage and applied as data attributes on
 * <html>, which is what every token block in tokens.css keys off. */

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import type { Mode, ThemeName } from '../data/types'

const THEMES: { id: ThemeName; label: string; hint: string }[] = [
  { id: 'compass', label: 'Compass', hint: 'Warm paper, deep green — the default' },
  { id: 'editorial', label: 'Editorial', hint: 'White, ink and thin rules' },
  { id: 'terminal', label: 'Terminal', hint: 'Deep surfaces, glowing accent' },
  { id: 'warm', label: 'Warm', hint: 'Cream, serif and terracotta' },
]

interface Ctx {
  theme: ThemeName
  mode: Mode
  setTheme: (t: ThemeName) => void
  setMode: (m: Mode) => void
  themes: typeof THEMES
}

const ThemeContext = createContext<Ctx | null>(null)

const KEY_THEME = 'compass:theme'
const KEY_MODE = 'compass:mode'

function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key) as T | null
    return v && allowed.includes(v) ? v : fallback
  } catch {
    return fallback
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>(() =>
    readStored(KEY_THEME, ['compass', 'editorial', 'terminal', 'warm'] as const, 'compass'),
  )
  const [mode, setModeState] = useState<Mode>(() => {
    const stored = readStored(KEY_MODE, ['light', 'dark'] as const, '' as Mode)
    if (stored) return stored
    return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light'
  })

  useEffect(() => {
    const root = document.documentElement
    root.dataset.theme = theme
    root.dataset.mode = mode
    root.style.colorScheme = mode
  }, [theme, mode])

  const setTheme = useCallback((t: ThemeName) => {
    setThemeState(t)
    try { localStorage.setItem(KEY_THEME, t) } catch { /* private mode */ }
  }, [])

  const setMode = useCallback((m: Mode) => {
    setModeState(m)
    try { localStorage.setItem(KEY_MODE, m) } catch { /* private mode */ }
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, mode, setTheme, setMode, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): Ctx {
  const c = useContext(ThemeContext)
  if (!c) throw new Error('useTheme must be used inside <ThemeProvider>')
  return c
}

export function ThemeSwitcher() {
  const { theme, mode, setTheme, setMode, themes } = useTheme()
  const [open, setOpen] = useState(false)

  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', position: 'relative' }}>
      <button
        className="pill"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        title="Change the look of the site"
      >
        {themes.find((t) => t.id === theme)?.label ?? 'Theme'} ▾
      </button>
      <button
        className="pill"
        onClick={() => setMode(mode === 'dark' ? 'light' : 'dark')}
        aria-label={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {mode === 'dark' ? '◑' : '◐'}
      </button>

      {open && (
        <div
          role="menu"
          style={{
            position: 'absolute', top: 'calc(100% + 8px)', right: 0, zIndex: 'var(--z-popover)' as never,
            background: 'var(--surface)', border: '1px solid var(--line)',
            borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)',
            padding: 6, width: 250,
          }}
        >
          {themes.map((t) => (
            <button
              key={t.id}
              role="menuitemradio"
              aria-checked={t.id === theme}
              onClick={() => { setTheme(t.id); setOpen(false) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 10px', borderRadius: 'var(--radius-sm)',
                background: t.id === theme ? 'var(--accent-wash)' : 'transparent',
                color: t.id === theme ? 'var(--accent)' : 'var(--ink-1)',
              }}
            >
              <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>{t.label}</span>
              <span style={{ display: 'block', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
                {t.hint}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
