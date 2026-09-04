/* Explore — seven themes, one chart language.
 *
 * Every theme opens with three numbers computed from its own data, then the
 * charts that earn them. Each chart carries one deliberate control, a title
 * that states a finding, a sub-line that explains the method, and a footer with
 * its confidence, its caveat and its CSV.
 *
 * Where a dataset does not exist, is blocked, or does not mean what a curve
 * would imply, the panel says so in words. There is no blank panel anywhere on
 * this page: a visitor must always be able to tell a deliberate absence from a
 * broken pipeline.
 */

import { Suspense, lazy } from 'react'
import { Link, useParams } from 'react-router-dom'
import { THEMES, type ThemeKey } from '../data/registry'
import { WeightsTool } from '../components/WeightsTool'
import { ClimateMatcher } from '../components/ClimateMatcher'
import { DeferUntilVisible } from '../components/DeferUntilVisible'
import { Hero, ChartSkeleton } from '../components/explore/Controls'
import { useAsync } from '../components/explore/useAsync'
import { useData } from '../data/store'
import { loadMoney, loadJobs, loadHousing, loadPeople, loadLife } from '../data/explore'
import { moneyHero, MoneyTheme } from '../components/explore/Money'
import { visaHero, VisasTheme } from '../components/explore/Visas'
import { jobsHero, JobsTheme } from '../components/explore/Jobs'
import { housingHero, HousingTheme } from '../components/explore/Housing'
import { peopleHero, PeopleTheme, lifeHero, LifeTheme } from '../components/explore/PeopleLife'
import { weatherHero, WeatherTheme } from '../components/explore/Weather'

const ScatterBuilder = lazy(() =>
  import('../components/ExploreCharts').then((m) => ({ default: m.ScatterBuilder })))

/** The one-line statement of what a theme is for. */
const INTRO: Record<ThemeKey, string> = {
  money: 'What you’d earn, what economies are doing, and where one institution honestly thinks they’re going.',
  visa: 'Rules, not trends. Every figure is dated, because these change by decree.',
  jobs: 'How many tech jobs exist — and whether anyone is posting new ones this month.',
  housing: 'Half a century of house prices, and real city series where they truly exist.',
  people: 'Who already moved, how policy treats them, and how full each country will be.',
  life: 'Happiness and press freedom, measured yearly — and what we refuse to average.',
  climate: 'Thirty-year averages. The question is February, not the mean.',
}

export function Explore() {
  const { theme } = useParams()
  const active = (THEMES.find((t) => t.key === theme)?.key ?? 'money') as ThemeKey

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <div className="kicker">Explore</div>
      <h1 className="pg">{THEMES.find((t) => t.key === active)?.label}</h1>
      <p className="oneline">{INTRO[active]}</p>

      {/* Remounting per theme is deliberate: the numbers count up on arrival,
          which is how a theme announces what it is about. */}
      <ThemeHero key={active} theme={active} />

      <div className="themesbar">
        <div className="wrap rail">
          {THEMES.map((t) => (
            <Link key={t.key} to={`/explore/${t.key}`} className="tchip"
              aria-current={t.key === active ? 'page' : undefined}>
              {t.label}
            </Link>
          ))}
        </div>
      </div>

      <section className="tsec">
        <div className="egrid">
          {active === 'money' && <MoneyTheme />}
          {active === 'visa' && <VisasTheme />}
          {active === 'jobs' && <JobsTheme />}
          {active === 'housing' && <HousingTheme />}
          {active === 'people' && <PeopleTheme />}
          {active === 'life' && <LifeTheme />}
          {active === 'climate' && <WeatherTheme />}
        </div>
      </section>

      {active === 'climate' && (
        <DeferUntilVisible minHeight={360} label="Climate matcher">
          <ClimateMatcher />
        </DeferUntilVisible>
      )}

      {/* Both tools live on every theme — the owner's ruling on NEEDS-DECISION #64,
          kept as-is. What changed in package 29 is that each now opens on the
          question ITS OWN theme is about, instead of the same two housing metrics
          everywhere; a visitor's own question replaces that and follows them. */}
      <DeferUntilVisible minHeight={520} label="Scatter builder">
        <Suspense fallback={<ChartSkeleton height={520} />}><ScatterBuilder theme={active} /></Suspense>
      </DeferUntilVisible>
      <DeferUntilVisible minHeight={200} label="Weights tool">
        <WeightsTool theme={active} />
      </DeferUntilVisible>
    </div>
  )
}

/* Each theme's heroes come from its own data, so they load with it rather than
   holding the page. A theme whose data is still arriving reserves their height
   instead of collapsing. */
function ThemeHero({ theme }: { theme: ThemeKey }) {
  switch (theme) {
    case 'money': return <AsyncHero load={loadMoney} k="money" to={moneyHero} />
    case 'jobs': return <AsyncHero load={loadJobs} k="jobs" to={jobsHero} />
    case 'housing': return <AsyncHero load={loadHousing} k="housing" to={housingHero} />
    case 'people': return <AsyncHero load={loadPeople} k="people" to={peopleHero} />
    case 'life': return <AsyncHero load={loadLife} k="life" to={lifeHero} />
    case 'visa': return <CoreHero kind="visa" />
    case 'climate': return <CoreHero kind="climate" />
    default: return null
  }
}

function AsyncHero<T>({ load, k, to }: { load: () => Promise<T>; k: string; to: (d: T) => ReturnType<typeof moneyHero> }) {
  const { data, error } = useAsync(load, k)
  if (error) return <div className="hero" aria-hidden="true" />
  // Same three lines as a loaded card, so the numbers arriving change nothing
  // about the page's shape.
  if (!data) {
    return (
      <div className="hero" aria-busy="true">
        {[0, 1, 2].map((i) => (
          <div className="hstat" key={i}>
            <div className="v tnum">&nbsp;</div>
            <div className="l">&nbsp;</div>
            <div className="s">&nbsp;</div>
          </div>
        ))}
      </div>
    )
  }
  return <Hero stats={to(data)} />
}

/** Visas and Weather read core.json, which is already loaded — no fetch, no wait. */
function CoreHero({ kind }: { kind: 'visa' | 'climate' }) {
  const data = useData()
  return <Hero stats={kind === 'visa' ? visaHero(data.countries) : weatherHero(data.cities)} />
}
