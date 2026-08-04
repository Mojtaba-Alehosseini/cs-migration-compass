import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider, createHashRouter } from 'react-router-dom'
import { MotionConfig } from 'motion/react'
import './styles/base.css'
import { App } from './App'
import { ThemeProvider } from './components/Theme'
import { DataContext, indexCore, loadCore, type Dataset } from './data/store'
import { Home } from './routes/Home'
import { Compare } from './routes/Compare'
import { Explore } from './routes/Explore'
import { CityProfile } from './routes/CityProfile'
import { CountryProfile } from './routes/CountryProfile'
import { DataMethods } from './routes/DataMethods'
import { NotFound } from './routes/NotFound'

/* Hash routing: GitHub Pages serves a 404 for unknown paths, and comparison
   links are meant to be pasted into Reddit and Telegram and just work. A hash
   route survives that without any server config. */
const router = createHashRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Home /> },
      { path: 'compare', element: <Compare /> },
      { path: 'explore', element: <Explore /> },
      { path: 'explore/:theme', element: <Explore /> },
      { path: 'city/:id', element: <CityProfile /> },
      { path: 'country/:id', element: <CountryProfile /> },
      { path: 'data', element: <DataMethods /> },
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
