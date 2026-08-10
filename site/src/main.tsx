import { StrictMode, Suspense, lazy, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider, createHashRouter } from 'react-router-dom'
import { MotionConfig } from 'motion/react'
import './styles/base.css'
import { App } from './App'
import { ThemeProvider } from './components/Theme'
import { DataContext, indexCore, loadCore, type Dataset } from './data/store'
import { Home } from './routes/Home'
import { NotFound } from './routes/NotFound'

/* Home is eager — it is the landing surface and must paint immediately.
   Everything else is lazy so that Recharts (111 KB) only downloads for the two
   routes that actually draw charts, instead of riding along on every page. */
const Compare = lazy(() => import('./routes/Compare').then((m) => ({ default: m.Compare })))
const Explore = lazy(() => import('./routes/Explore').then((m) => ({ default: m.Explore })))
const CityProfile = lazy(() => import('./routes/CityProfile').then((m) => ({ default: m.CityProfile })))
const CountryProfile = lazy(() => import('./routes/CountryProfile').then((m) => ({ default: m.CountryProfile })))
const DataMethods = lazy(() => import('./routes/DataMethods').then((m) => ({ default: m.DataMethods })))

/* A fixed-height placeholder, not a spinner: it reserves the space the page is
   about to occupy so the swap does not shove the layout around.
   A full viewport, not most of one — every real route is taller than the fold,
   so anything less leaves the footer inside the viewport and then drops it when
   the route arrives, which is a layout shift the reader sees. */
function RouteFallback() {
  return (
    <div className="wrap" style={{ paddingTop: 22, minHeight: '100vh' }} aria-busy="true">
      <div className="kicker">Loading…</div>
    </div>
  )
}

const lazyRoute = (el: React.ReactNode) => <Suspense fallback={<RouteFallback />}>{el}</Suspense>

/* Hash routing: GitHub Pages serves a 404 for unknown paths, and comparison
   links are meant to be pasted into Reddit and Telegram and just work. A hash
   route survives that without any server config. */
const router = createHashRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Home /> },
      { path: 'compare', element: lazyRoute(<Compare />) },
      { path: 'explore', element: lazyRoute(<Explore />) },
      { path: 'explore/:theme', element: lazyRoute(<Explore />) },
      { path: 'city/:id', element: lazyRoute(<CityProfile />) },
      { path: 'country/:id', element: lazyRoute(<CountryProfile />) },
      { path: 'data', element: lazyRoute(<DataMethods />) },
      { path: '*', element: <NotFound /> },
    ],
  },
])

function Boot() {
  const [data, setData] = useState<Dataset | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadCore()
      .then((core) => setData(indexCore(core)))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  if (error) {
    return (
      <div className="wrap" style={{ paddingTop: 60, maxWidth: 560 }}>
        <h1 style={{ fontSize: 'var(--text-lg)' }}>The data didn’t load</h1>
        <p style={{ color: 'var(--ink-2)', marginTop: 8 }}>{error}</p>
        <p style={{ color: 'var(--ink-3)', marginTop: 8, fontSize: 'var(--text-xs)' }}>
          If you are running this locally, <code>npm run data</code> rebuilds the bundle from{' '}
          <code>data/</code>.
        </p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="wrap" style={{ paddingTop: 80 }} aria-busy="true">
        <div className="kicker">Loading 15 countries and 73 cities…</div>
      </div>
    )
  }

  return (
    <DataContext.Provider value={data}>
      <RouterProvider router={router} />
    </DataContext.Provider>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* reducedMotion="user" makes every Motion animation honour the OS setting,
        so the reduced-motion path is guaranteed rather than remembered. */}
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <Boot />
      </ThemeProvider>
    </MotionConfig>
  </StrictMode>,
)
