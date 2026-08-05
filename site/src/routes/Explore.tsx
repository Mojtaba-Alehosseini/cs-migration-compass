/* Explore — per-theme deep dives.
 *
 * Two things here carry the most weight:
 *   1. History charts overlay a REAL institutional forecast (solid, with an
 *      attribution chip) alongside our naive extrapolation (hatched band,
 *      labelled "not a forecast"). They are never averaged.
 *   2. The scatter builder lets any metric meet any other. Presets exist as
 *      examples, never as a default lens the site pushes. */

import { Suspense, lazy } from 'react'
import { Link, useParams } from 'react-router-dom'
import { THEMES, type ThemeKey } from '../data/registry'
import { WeightsTool } from '../components/WeightsTool'
import { ClimateMatcher } from '../components/ClimateMatcher'
import { DeferUntilVisible } from '../components/DeferUntilVisible'

const EconomyHistory = lazy(() =>
  import('../components/ExploreCharts').then((m) => ({ default: m.EconomyHistory })))
const ScatterBuilder = lazy(() =>
  import('../components/ExploreCharts').then((m) => ({ default: m.ScatterBuilder })))

export function Explore() {
  const { theme } = useParams()
  const active = (THEMES.find((t) => t.key === theme)?.key ?? 'money') as ThemeKey

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <div className="kicker">Explore</div>
      <h1 style={{ fontSize: 'var(--text-xl)', marginTop: 4 }}>
        {THEMES.find((t) => t.key === active)?.label}
      </h1>
      <p style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', margin: '6px 0 14px' }}>
        {THEMES.find((t) => t.key === active)?.blurb}
      </p>

      <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginBottom: 16 }}>
        {THEMES.map((t) => (
          <Link key={t.key} to={`/explore/${t.key}`} className="pill"
            aria-current={t.key === active ? 'page' : undefined}
            style={{
              textDecoration: 'none',
              background: t.key === active ? 'var(--ink-1)' : 'var(--surface)',
              color: t.key === active ? 'var(--paper)' : 'var(--ink-2)',
              borderColor: t.key === active ? 'var(--ink-1)' : 'var(--line)',
            }}>
            {t.label}
          </Link>
        ))}
      </div>

      {/* Each panel mounts as it comes into reach. Rendering all three up front
          cost ~580 ms of blocked main thread for charts below the fold. */}
      {active === 'money' && (
        <DeferUntilVisible minHeight={430} label="Income history and forecasts">
          <Suspense fallback={null}><EconomyHistory /></Suspense>
        </DeferUntilVisible>
      )}
      {active === 'climate' && (
        <DeferUntilVisible minHeight={360} label="Climate matcher">
          <ClimateMatcher />
        </DeferUntilVisible>
      )}
      <DeferUntilVisible minHeight={520} label="Scatter builder">
        <Suspense fallback={null}><ScatterBuilder /></Suspense>
      </DeferUntilVisible>
      <DeferUntilVisible minHeight={200} label="Weights tool">
        <WeightsTool />
      </DeferUntilVisible>
    </div>
  )
}
