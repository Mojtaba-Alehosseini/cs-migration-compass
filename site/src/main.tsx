import { StrictMode, Suspense, lazy, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Navigate, RouterProvider, createHashRouter, useLocation } from 'react-router-dom'
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
const Work = lazy(() => import('./routes/Work').then((m) => ({ default: m.Work })))
const Openings = lazy(() => import('./routes/Openings').then((m) => ({ default: m.Openings })))

/** A redirect that carries the query string with it.
 *
 *  <Navigate to="/work"> drops it, which quietly breaks exactly the links the
 *  redirect exists to save: /position?years=8&occupation=isco08:2512 is a
 *  shareable profile, and arriving at /work with an empty form is a worse
 *  outcome than a 404 because it looks like it worked. Caught by the UI
 *  regression suite, which navigates to /position?years=8 and asserts the years
 *  actually took effect — sixteen checks failed on the first attempt. */
function KeepQuery({ to }: { to: string }) {
  const { search, hash } = useLocation()
  return <Navigate to={{ pathname: to, search, hash }} replace />
}

const PostingsSeed = lazy(() => import('./routes/PostingsSeed').then((m) => ({ default: m.PostingsSeed })))

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
      // Package 17 — /position and /postings are one page. Both old paths
      // REDIRECT rather than 404: they have been linkable since package 9 and
      // package 12 respectively, and a shared link that dies is a worse outcome
      // than a redirect nobody notices. `replace` so the dead path does not
      // sit in history behind the live one.
      { path: 'work', element: lazyRoute(<Work />) },
      // The browsable full list, on its own route so it loads its own weight —
      // /work shows eight examples per country from a 144 KB summary, and this
      // page is the one for which parsing the whole array is the right trade.
      { path: 'openings', element: lazyRoute(<Openings />) },
      { path: 'position', element: <KeepQuery to="/work" /> },
      // NEEDS-DECISION #50, closed package 21: /postings was the browsable
      // list, and redirecting it to /work (eight examples per country, no
      // filters, no map) sent a reader looking for the list to a page that
      // is not one. /openings IS the list this route used to be -- the
      // honest redirect. KeepQuery still preserves the query string, though
      // Openings.tsx does not yet read country/level params from the URL to
      // pre-populate its filters (its filters are local component state) --
      // a real gap, but a distinct one from which PAGE a stale /postings
      // link should land on, which is what this fixes.
      { path: 'postings', element: <KeepQuery to="/openings" /> },
      { path: 'data/postings-seed', element: lazyRoute(<PostingsSeed />) },
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
