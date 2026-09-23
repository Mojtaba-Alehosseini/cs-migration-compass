/* Theme + mode, persisted in localStorage and applied as data attributes on
 * <html>, which is what every token block in tokens.css keys off. */

import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import type { Mode, ThemeName } from '../data/types'
import { placedCardStyle, useCardPlacement } from './useCardPlacement'

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

/* Package 46, Tier 4. The theme and mode controls live in the site footer,
 * not the header. The header was two rows on every phone (96px at 360, 390
 * and 414) and at 561–630px as well, and the one thing it could give up was
 * this pair: 131px of the 316–346px a phone header has. The picker alone was
 * not enough — without it the header still needed 350px at 390, 4px more
 * than it has (10px more in the Warm theme, whose interface face is a serif).
 * Both controls sit in one place at every width, so neither moves when a
 * phone is rotated, and the system's light/dark setting is still followed
 * until a reader overrides it.
 *
 * The picker says what it is. It read "Compass ▾" — the name of the theme,
 * beside a wordmark that also says "Compass" and means the site.
 *
 * The list is a disclosure of toggle buttons, not role="menu": a menu
 * promises arrow-key navigation this never had, and a screen reader that
 * enters one expects it. Tab, Enter and Space are what it answers to, and
 * Escape closes it and puts focus back on the button that opened it. */
export function ThemeSwitcher() {
  const { theme, mode, setTheme, setMode, themes } = useTheme()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)
  const id = useId()
  // It opens from the footer, where there is rarely room below: the shared
  // placement flips it above and keeps it inside the viewport at any width.
  const pos = useCardPlacement(open, triggerRef, cardRef)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setOpen(false)
      triggerRef.current?.focus()
    }
    document.addEventListener('click', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={ref} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      <button
        ref={triggerRef}
        type="button"
        className="pill"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
      >
        Theme: {themes.find((t) => t.id === theme)?.label ?? 'Compass'}<span aria-hidden="true"> ▾</span>
      </button>

      {/* Straight after its trigger in the source, so the next Tab lands in
        * the list rather than on the mode button beside it. It is
        * position: fixed, so it takes no place in this row. */}
      {open && (
        <div
          ref={cardRef}
          id={id}
          role="group"
          aria-label="Theme"
          style={{
            ...placedCardStyle(pos),
            zIndex: 'var(--z-popover)' as never,
            background: 'var(--surface)', border: '1px solid var(--line)',
            borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)',
            padding: 6, width: 250,
          }}
        >
          {themes.map((t) => (
            <button
              key={t.id}
              type="button"
              aria-pressed={t.id === theme}
              onClick={() => { setTheme(t.id); setOpen(false); triggerRef.current?.focus() }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 10px', borderRadius: 'var(--radius-sm)',
                background: t.id === theme ? 'var(--accent-wash)' : 'transparent',
                color: t.id === theme ? 'var(--accent)' : 'var(--ink-1)',
              }}
            >
              <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>{t.label}</span>
              {/* ink-2 on the current theme's wash: ink-3 there measured
                * 4.21-4.49:1 in every theme, under the 4.5:1 12px text needs.
                * Package 46's accessibility review. */}
              <span style={{ display: 'block', fontSize: 'var(--text-2xs)', color: t.id === theme ? 'var(--ink-2)' : 'var(--ink-3)' }}>
                {t.hint}
              </span>
            </button>
          ))}
        </div>
      )}

      <button
        type="button"
        className="pill"
        onClick={() => setMode(mode === 'dark' ? 'light' : 'dark')}
        aria-label={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        {mode === 'dark' ? '◑' : '◐'}
      </button>
    </div>
  )
}
