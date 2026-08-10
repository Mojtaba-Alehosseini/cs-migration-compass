/* People like you, and Daily life.
 *
 * The WHR panel carries the argument of the whole site in one control: the same
 * fifteen years read as a score and as a rank. Neither is more true, and the
 * morph between them is what shows they are the same data — a place can hold
 * its score and still slide, because everyone else moved.
 */

import { useMemo, useState } from 'react'
import { Chart } from '../chart/Chart'
import type { ChartCfg, Series } from '../chart/engine'
import { Seg, Picker, ChartFoot, ChartTable, Gap, ThemeSkeleton, ChartPlaceholder, type HeroStat } from './Controls'
import { useAsync } from './useAsync'
import { loadPeople, loadLife, type PeopleData, type LifeData, type Pair } from '../../data/explore'

const cc = (c: string) => `var(--c-${c})`
const last = <T,>(a: T[]) => a[a.length - 1]!

/* --------------------------------------------------------------- people --- */

export function peopleHero(d: PeopleData): HeroStat[] {
  const ca = d.mipex.CA ? last(d.mipex.CA) : null
  const de = d.wpp.DE ? last(d.wpp.DE) : null
  const au = d.wpp.AU ? last(d.wpp.AU) : null
  const deNow = d.wpp.DE?.find((p) => !p[2]) ? last(d.wpp.DE!.filter((p) => !p[2])) : null
  const auNow = d.wpp.AU?.find((p) => !p[2]) ? last(d.wpp.AU!.filter((p) => !p[2])) : null
  return [
    { value: ca?.[1] ?? null, format: (v) => `${v.toFixed(0)} / 100`,
      label: 'Canada’s integration-policy score, best here', source: `MIPEX ${ca?.[0] ?? ''}` },
    { value: de?.[1] ?? null, format: (v) => `${v.toFixed(0)}m`,
      label: `Germans projected for 2100 — from ${deNow ? deNow[1].toFixed(0) : '—'}m today`, source: 'UN WPP medium' },
    { value: au?.[1] ?? null, format: (v) => `${v.toFixed(0)}m`,
      label: `Australians projected for 2100 — from ${auNow ? auNow[1].toFixed(0) : '—'}m`, source: 'UN WPP medium' },
  ]
}

const MIPEX_PICKS = ['CA', 'IE', 'DE', 'NL', 'FI', 'ES']
const WPP_PICKS = ['DE', 'CA', 'AU']

export function PeopleTheme() {
  const { data, error } = useAsync(loadPeople, 'people')
  if (error) {
    return <div className="panel s6"><p className="nodata">
      Policy and population history could not be loaded ({error}). Nothing is drawn rather than something approximate.
    </p></div>
  }
  if (!data) return <ThemeSkeleton panels={[['s4', 409], ['s2', 409], ['s6', 434]]} />

  const mipexCfg: ChartCfg = {
    aria: 'MIPEX integration policy score, 2020 to 2024',
    w: 620, h: 250, padR: 44,
    x: { min: 2020, max: 2024, ticks: [[2020, '2020'], [2022, '2022'], [2024, '2024']] },
    y: { min: 40, max: 92, ticks: [[50, '50'], [70, '70'], [90, '90']] },
    series: MIPEX_PICKS.filter((c) => data.mipex[c]?.length)
      .map((c) => ({ key: c, label: c, color: cc(c), markers: true, pts: data.mipex[c]!, hoverLabel: c })),
    fmtX: (v) => String(v),
    fmtV: (p) => `${(p[1] ?? 0).toFixed(0)} / 100`,
  }

  const wppCfg: ChartCfg = {
    aria: 'Total population to 2100, UN medium variant',
    x: { min: 1990, max: 2100, ticks: [[1990, '1990'], [2024, '2024'], [2050, '2050'], [2075, '2075'], [2100, '2100']] },
    y: { min: 0, max: 100, ticks: [[20, '20m'], [40, '40m'], [60, '60m'], [80, '80m']] },
    today: 2024, future: 2024,
    series: WPP_PICKS.flatMap((c) => {
      const rows = data.wpp[c]
      if (!rows?.length) return []
      const act = rows.filter((p) => !p[2]).map(([y, v]) => [y, v] as Pair)
      const proj = rows.filter((p) => p[2]).map(([y, v]) => [y, v] as Pair)
      // The projection starts where the estimate stops, so the two meet rather
      // than leaving a gap the eye would fill in.
      if (act.length && proj.length) proj.unshift(last(act))
      return [
        { key: c, label: c, color: cc(c), pts: act, hoverLabel: `${c} · estimate` } as Series,
        { key: `${c}_p`, color: cc(c), pts: proj, mode: 'projection', hoverLabel: `${c} · UN medium` } as Series,
      ]
    }),
    fmtX: (v) => String(v),
    fmtV: (p) => `${(p[1] ?? 0).toFixed(1)} million`,
  }

  const mipexCsv = MIPEX_PICKS.flatMap((c) => (data.mipex[c] ?? []).map(([y, v]) => ({ country: c, year: y, mipex_score: v })))
  const wppCsv = WPP_PICKS.flatMap((c) => (data.wpp[c] ?? []).map(([y, v, pr]) => ({
    country: c, year: y, population_millions: v, is_projection: pr,
  })))

  return (
    <>
      <div className="panel s4">
        <h2>How policy treats immigrants</h2>
        <div className="sub">MIPEX integration-policy score, 0–100. Policy on paper — not lived experience.</div>
        <Chart id="ex-mipex" cfg={mipexCfg} transition="morph" />
        <ChartFoot csv={{ name: 'compass-mipex.csv', rows: mipexCsv }}>
          <span className="chip chip-note">◐ Research · MIPEX 2020–2024</span>
          <span className="chip chip-risk">no scores for Australia · US · UK · Norway in this workbook</span>
        </ChartFoot>
        <ChartTable caption="MIPEX scores — the numbers behind this chart"
          head={['Country', 'Year', 'Score / 100']}
          rows={mipexCsv.map((r) => [r.country, r.year, r.mipex_score])} />
      </div>

      <Gap title="Who’s already there is a snapshot" where={<a href="#/data">See any country page →</a>}>
        <p>
          UN DESA’s matrix answers “how many people from Iran live here?” — for 2024, precisely,
          with origins. One reference year, not a series: it lives on every country page rather than
          pretending to be a curve here.
        </p>
      </Gap>

      <div className="panel s6">
        <h2>How many neighbours you’d have</h2>
        <div className="sub">
          Total population to 2100 — the UN’s medium variant, the second live
          institutional forecast on the site. The tinted region is the future; we add nothing of our
          own to it.
        </div>
        <Chart id="ex-wpp" cfg={wppCfg} transition="morph" />
        <ChartFoot csv={{ name: 'compass-population-2100.csv', rows: wppCsv }}>
          <span className="chip chip-ok">● Official · UN WPP 2024, medium variant</span>
        </ChartFoot>
        <ChartTable caption="Population to 2100 — the numbers behind this chart"
          head={['Country', 'Year', 'Millions', 'Projection?']}
          rows={wppCsv.filter((r) => r.year % 20 === 0).map((r) => [r.country, r.year, r.population_millions, r.is_projection ? 'yes' : 'no'])} />
      </div>
    </>
  )
}

/* ----------------------------------------------------------------- life --- */

export function lifeHero(d: LifeData): HeroStat[] {
  const fi = d.whr.FI ?? []
  const us = d.whr.US ?? []
  const usRsf = d.rsf.US
  const yearsAtOne = fi.filter((p) => p[2] === 1).length
  return [
    { value: yearsAtOne, format: (v) => `${Math.round(v)} yrs`,
      label: 'Finland has held rank #1', source: 'World Happiness Report' },
    { value: us.length ? us[0]![2] - last(us)[2] : null, format: (v) => `${Math.round(Math.abs(v))} places`,
      label: 'the US has slid down the ranking since 2011',
      source: us.length ? `#${us[0]![2]} → #${last(us)[2]}` : '' },
    { value: usRsf?.length ? last(usRsf)[1] : null, format: (v) => `${v.toFixed(0)} / 100`,
      label: 'US press-freedom score, 2026 — falling', source: 'RSF' },
  ]
}

const RSF_PICKS = ['FI', 'NL', 'DK', 'DE', 'US']

export function LifeTheme() {
  const { data, error } = useAsync(loadLife, 'life')
  const [mode, setMode] = useState<'score' | 'rank'>('score')
  const [picks, setPicks] = useState(['FI', 'DK', 'NL', 'DE', 'US'])

  const whrCfg = useMemo<ChartCfg | null>(() => {
    if (!data) return null
    return {
      aria: `World Happiness ${mode === 'score' ? 'score out of 10' : 'rank'}, 2011 to 2025, ${picks.join(', ')}`,
      x: { min: 2011, max: 2025, ticks: [[2011, '2011'], [2015, '2015'], [2020, '2020'], [2025, '2025']] },
      // Rank space is inverted: #1 belongs at the top, which is what makes the
      // morph legible rather than merely pretty.
      y: mode === 'score'
        ? { min: 5.5, max: 8.2, ticks: [[6, '6.0'], [7, '7.0'], [8, '8.0']] }
        : { min: 30, max: 0, ticks: [[1, '#1'], [10, '#10'], [20, '#20'], [30, '#30']] },
      series: picks.filter((c) => data.whr[c]?.length).map((c) => ({
        key: c, label: c, color: cc(c), markers: true, hoverLabel: c,
        pts: data.whr[c]!.map(([y, s, r]) => [y, mode === 'score' ? s : r, false, { s, r }]),
      })),
      fmtX: (v) => String(v),
      fmtV: (p) => {
        const e = p[3] as { s: number; r: number } | undefined
        const of = data.whrRankedOf[String(p[0])]
        return mode === 'score'
          ? `${(p[1] ?? 0).toFixed(2)} / 10 · rank #${e?.r}${of ? ` of ${of}` : ''}`
          : `#${p[1]}${of ? ` of ${of}` : ''} · score ${e?.s.toFixed(2)}`
      },
    }
  }, [data, mode, picks])

  if (error) {
    return <div className="panel s6"><p className="nodata">
      Happiness and press-freedom history could not be loaded ({error}). Nothing is drawn rather than something approximate.
    </p></div>
  }
  // Reserve the whole panel, not just the chart: the country picker's chips
  // wrap to a second row once the data names them, and no chart-shaped
  // placeholder can reserve a row that does not exist yet.
  if (!data) return <ThemeSkeleton panels={[['s6', 517], ['s4', 461], ['s2', 461]]} />

  const rsfCfg: ChartCfg | null = {
    aria: 'RSF press freedom score, 2022 onward',
    w: 620, h: 250, padR: 44,
    x: { min: 2022, max: 2026, ticks: [[2022, '2022'], [2024, '2024'], [2026, '2026']] },
    y: { min: 55, max: 100, ticks: [[60, '60'], [80, '80'], [100, '100']] },
    ann: [[2022, 'new method']],
    series: RSF_PICKS.filter((c) => data.rsf[c]?.length)
      .map((c) => ({ key: c, label: c, color: cc(c), markers: true, pts: data.rsf[c]!, hoverLabel: c })),
    fmtX: (v) => String(v),
    fmtV: (p) => `${(p[1] ?? 0).toFixed(1)} / 100`,
  }

  const whrCsv = picks.flatMap((c) => (data?.whr[c] ?? []).map(([y, s, r]) => ({
    country: c, year: y, score: s, rank: r, ranked_of: data?.whrRankedOf[String(y)] ?? null,
  })))
  const rsfCsv = RSF_PICKS.flatMap((c) => (data?.rsf[c] ?? []).map(([y, v]) => ({ country: c, year: y, score: v })))

  return (
    <>
      <div className="panel s6">
        <h2>Fifteen years of people rating their own lives</h2>
        <div className="sub">
          World Happiness score, 0–10 — or flip to rank and watch places trade
          positions. Same data, two honest readings; the morph between them is the argument.
        </div>
        <div className="crail">
          <Seg label="How to read happiness" value={mode}
            options={[['score', 'score /10'], ['rank', 'rank']]} onChange={setMode} />
          <Picker label="Countries"
            items={Object.keys(data?.whr ?? {}).sort().map((c) => ({ k: c, cc: c, label: c }))}
            active={picks} onChange={setPicks} />
        </div>
        {/* Same points, new y space: this is a value change, so it morphs. */}
        {whrCfg ? <Chart id="ex-whr" cfg={whrCfg} transition="morph" /> : <ChartPlaceholder />}
        <ChartFoot csv={{ name: 'compass-world-happiness.csv', rows: whrCsv }}>
          <span className="chip chip-note">◐ Research · World Happiness Report 2011–2025</span>
          <span className="chip chip-quiet">rank view is still not a recommendation — it is their survey, your read</span>
        </ChartFoot>
        <ChartTable caption="World Happiness — the numbers behind this chart"
          head={['Country', 'Year', 'Score / 10', 'Rank', 'Countries ranked']}
          rows={whrCsv.filter((r) => r.year % 4 === 0).map((r) => [r.country, r.year, r.score.toFixed(2), `#${r.rank}`, r.ranked_of])} />
      </div>

      <div className="panel s4">
        <h2>Press freedom, since it became comparable</h2>
        <div className="sub">
          RSF score, 0–100, higher is freer. RSF rebuilt its method in 2022 — earlier
          years exist but don’t compare, so we draw only what does.
        </div>
        {rsfCfg ? <Chart id="ex-rsf" cfg={rsfCfg} transition="morph" /> : <ChartPlaceholder w={620} h={250} />}
        <ChartFoot csv={{ name: 'compass-press-freedom.csv', rows: rsfCsv }}>
          <span className="chip chip-note">◐ Research · Reporters Without Borders</span>
          <span className="chip chip-quiet">2013–2021 exist but aren’t comparable — deliberately undrawn</span>
        </ChartFoot>
        <ChartTable caption="Press freedom — the numbers behind this chart"
          head={['Country', 'Year', 'Score / 100']}
          rows={rsfCsv.map((r) => [r.country, r.year, r.score])} />
      </div>

      <Gap title="What’s deliberately absent">
        <p>
          No “quality of life” composite. Averaging happiness, peace and healthcare into one number
          would be a recommendation wearing a costume. The weights tool below exists for exactly
          that — and only you can turn it on.
        </p>
      </Gap>
    </>
  )
}
