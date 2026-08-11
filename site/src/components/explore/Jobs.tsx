/* Finding work — how much of a country works in IT, and who is posting now.
 *
 * Two signature controls, one each. The ICT chart flips between twenty years of
 * line and the one straight answer those years add up to. The postings chart
 * flips between an overlay and a grid — the same series, asked a different
 * question: "which is highest" versus "what did each one do".
 *
 * Metros use --m-1…8, never a country hue: a US metro borrowing Germany's
 * colour would break the one thing that makes every chart on this site readable
 * without a legend.
 */

import { useMemo, useState } from 'react'
import { Chart } from '../chart/Chart'
import type { ChartCfg, Series } from '../chart/engine'
import { Seg, Picker, ChartFoot, ChartTable, Gap, ChartPlaceholder, ThemeSkeleton, type HeroStat } from './Controls'
import { useAsync } from './useAsync'
import { loadJobs, METROS, METRO_LABEL, type JobsData } from '../../data/explore'

const cc = (c: string) => `var(--c-${c})`
const metroColor = (i: number) => `var(--m-${(i % 8) + 1})`
const last = <T,>(a: T[]) => a[a.length - 1]!
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function jobsHero(d: JobsData): HeroStat[] {
  const de = d.ict.DE ? last(d.ict.DE) : null
  const eu = d.ict.EU27 ? last(d.ict.EU27) : null
  const sf = d.indeed.sf_bay_area ? last(d.indeed.sf_bay_area) : null
  return [
    { value: de?.[1] ?? null, format: (v) => `${v.toFixed(1)}%`,
      label: `of all German jobs are IT, ${de?.[0] ?? ''}`, source: 'Eurostat' },
    { value: eu?.[1] ?? null, format: (v) => `${v.toFixed(1)}%`,
      label: 'the EU-27 average share', source: 'benchmark' },
    { value: sf?.[1] ?? null, format: (v) => String(Math.round(v)),
      label: 'SF Bay postings today · Feb 2020 = 100', source: 'Indeed' },
  ]
}

export function JobsTheme() {
  const { data, error } = useAsync(loadJobs, 'jobs')
  if (error) {
    return <div className="panel s6"><p className="nodata">
      Employment history could not be loaded ({error}). Nothing is drawn rather than something approximate.
    </p></div>
  }
  // Reserve the whole panel, not just the chart: the country picker's chips
  // wrap to a second row once the data names them, and no chart-shaped
  // placeholder can reserve a row that does not exist yet.
  if (!data) return <ThemeSkeleton panels={[['s6', 497], ['s4', 516], ['s2', 516]]} />
  return (
    <>
      <IctPanel data={data} />
      <PostingsPanel data={data} />
      <Gap title="Two honest holes" where={<>Both on the <a href="#/data">Data &amp; methods page →</a></>}>
        <p><b>US dev headcounts are a snapshot.</b> The BLS API returns the current year only —
          verified, not assumed — so city pages show the number and draw no curve.</p>
        <p><b>The Gulf has no ICT headcount series.</b> Eurostat stops at EU/EFTA; the UAE and Qatar publish no
          ICT count we can cite. We don’t substitute.</p>
      </Gap>
    </>
  )
}

function IctPanel({ data }: { data: JobsData | null }) {
  const [mode, setMode] = useState<'share' | 'slope'>('share')
  const [picks, setPicks] = useState(['DE', 'NL', 'SE', 'ES'])

  const cfg = useMemo<ChartCfg | null>(() => {
    if (!data) return null
    const mk = (key: string, color: string, m?: Series['mode']): Series | null => {
      const pts = data.ict[key]
      if (!pts?.length) return null
      if (mode === 'slope') {
        // Twenty years reduced to the two points that carry the answer.
        const f = pts[0]!
        const l = last(pts)
        return { key, label: `${key}  ${f[1].toFixed(1)}→${l[1].toFixed(1)}%`, color, pts: [f, l], markers: true, mode: m, hoverLabel: key }
      }
      return { key, label: key, color, pts, mode: m, hoverLabel: key }
    }
    const series: Series[] = []
    for (const c of picks) { const s = mk(c, cc(c)); if (s) series.push(s) }
    const bench = mk('EU27', 'var(--ink-3)', 'benchmark')
    if (bench) { bench.label = 'EU-27'; bench.hoverLabel = 'EU-27 average'; series.push(bench) }

    return {
      aria: `ICT specialists as a share of employment, ${picks.join(', ')}, with the EU-27 benchmark`,
      x: mode === 'slope'
        ? { min: 2002, max: 2027, ticks: [[2004, '2004'], [2025, '2025']] }
        : { min: 2004, max: 2025, ticks: [[2005, '2005'], [2010, '2010'], [2015, '2015'], [2020, '2020'], [2025, '2025']] },
      y: { min: 1, max: 9, ticks: [[2, '2%'], [4, '4%'], [6, '6%'], [8, '8%']] },
      series,
      fmtX: (v) => String(v),
      fmtV: (p) => `${(p[1] ?? 0).toFixed(1)}% of all jobs`,
    }
  }, [data, mode, picks])

  const csv = picks.flatMap((c) => (data?.ict[c] ?? []).map(([y, v]) => ({ country: c, year: y, ict_share_pct: v })))

  return (
    <div className="panel s6">
      <h2>How much of a country works in IT</h2>
      <div className="sub">
        ICT specialists as a share of everyone employed. The slope view strips
        twenty years to one straight answer: where did tech grow fastest? Grey dashes are the
        EU-27 average — a benchmark, not a member.
      </div>
      <div className="crail">
        <Seg label="How to read the share" value={mode}
          options={[['share', 'over time'], ['slope', '2004 → 2025']]} onChange={setMode} />
        <Picker label="Countries"
          items={Object.keys(data?.ict ?? {}).filter((k) => k !== 'EU27').sort().map((c) => ({ k: c, cc: c, label: c }))}
          active={picks} onChange={setPicks} />
      </div>
      {/* Dropping twenty points to two is a different chart, not a new value. */}
      {cfg ? <Chart id="ex-ict" cfg={cfg} transition="fade" /> : <ChartPlaceholder />}
      <ChartFoot csv={{ name: 'compass-ict-share.csv', rows: csv }}>
        <span className="chip chip-ok">● Official · Eurostat isoc_sks_itspt</span>
        <span className="chip chip-quiet">EU/EFTA only — that limit is real and shown</span>
      </ChartFoot>
      <ChartTable caption="ICT share of employment — the numbers behind this chart"
        head={['Country', 'Year', 'Share of all jobs']}
        rows={csv.filter((r) => r.year % 5 === 0).map((r) => [r.country, r.year, `${r.ict_share_pct}%`])} />
    </div>
  )
}

function PostingsPanel({ data }: { data: JobsData | null }) {
  const [mode, setMode] = useState<'overlay' | 'grid'>('overlay')
  const drawn = METROS.filter((m) => data?.indeed[m]?.length)

  const cfg = useMemo<ChartCfg | null>(() => {
    if (!data || !drawn.length) return null
    const series: Series[] = drawn.map((m, i) => ({
      key: m, label: METRO_LABEL[m], color: metroColor(i), pts: data.indeed[m]!, hoverLabel: METRO_LABEL[m],
    }))
    const xmax = Math.max(...series.flatMap((s) => s.pts.map((p) => p[0])))
    return {
      aria: `Job postings index by US metro, February 2020 = 100, ${drawn.map((m) => METRO_LABEL[m]).join(', ')}`,
      w: 620, h: 260, padR: 70, zero: 100,
      x: { min: 2020, max: xmax, ticks: [[2020, '2020'], [2022, '2022'], [2024, '2024'], [2026, '2026']] },
      y: { min: 40, max: 200, ticks: [[50, '50'], [100, '100'], [150, '150'], [200, '200']] },
      ann: [[2020.25, 'covid']],
      series,
      fmtX: (v) => `${MONTHS[Math.round((v - Math.floor(v)) * 12)] ?? ''} ${Math.floor(v)}`,
      fmtV: (p) => `${(p[1] ?? 0).toFixed(0)} · Feb 2020 = 100`,
    }
  }, [data, drawn])

  const csv = drawn.flatMap((m) => (data?.indeed[m] ?? []).map(([x, v]) => ({
    metro: METRO_LABEL[m], year: Math.floor(x), month: Math.round((x - Math.floor(x)) * 12) + 1, index: v,
  })))

  return (
    <div className="panel s4">
      <h2>Is anyone hiring right now?</h2>
      <div className="sub">
        Job postings per metro, February 2020 = 100 — a true city-level series.
        Overlay to compare; split to see each metro breathe on its own.
      </div>
      <div className="crail">
        <Seg label="How to read the postings" value={mode}
          options={[['overlay', 'overlay'], ['grid', 'one by one']]} onChange={setMode} />
      </div>
      {!data || !cfg
        ? <ChartPlaceholder w={620} h={260} />
        : mode === 'overlay'
          ? <Chart id="ex-indeed" cfg={cfg} transition="fade" />
          : <PostingsGrid data={data} drawn={drawn} />}
      <ChartFoot csv={{ name: 'compass-indeed-postings.csv', rows: csv }}>
        <span className="chip chip-note">◐ Research · Indeed Hiring Lab</span>
        <span className="chip chip-quiet">all postings, not software-only — the sector cut isn’t published</span>
        <span className="chip chip-quiet">
          {drawn.length} of the {data?.metrosAvailable ?? '…'} metros in the file — the eight the design draws
        </span>
      </ChartFoot>
      <ChartTable caption="Job postings index — latest reading per metro"
        head={['Metro', 'Latest index', 'Feb 2020 = 100']}
        rows={drawn.map((m) => {
          const l = data!.indeed[m]!
          return [METRO_LABEL[m]!, l[l.length - 1]![1].toFixed(0), '100']
        })} />
    </div>
  )
}

/** Small multiples: each metro on its own baseline, so a shape is readable
 *  without competing against seven others. */
function PostingsGrid({ data, drawn }: { data: JobsData; drawn: readonly string[] }) {
  const W = 620
  const cols = 4
  const cw = W / cols
  const rh = 96
  const H = Math.ceil(drawn.length / cols) * rh + 8
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`Job postings per metro, one panel each: ${drawn.map((m) => METRO_LABEL[m]).join(', ')}`}>
        {drawn.map((m, i) => {
          const pts = data.indeed[m]!
          const cx = (i % cols) * cw
          const cy = Math.floor(i / cols) * rh
          const x0 = 2020
          const x1 = Math.max(...pts.map((p) => p[0]))
          const X = (v: number) => cx + 10 + ((v - x0) / (x1 - x0)) * (cw - 24)
          const Y = (v: number) => cy + 70 - ((v - 40) / 160) * 54
          const last0 = pts[pts.length - 1]!
          return (
            <g key={m}>
              <line x1={cx + 10} x2={cx + cw - 14} y1={Y(100)} y2={Y(100)} className="zeroline" strokeDasharray="2 3" />
              <path d={pts.map((p, j) => (j ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join('')}
                fill="none" stroke={metroColor(i)} strokeWidth="1.8" />
              <text x={cx + 10} y={cy + 16} fontSize="10.5" fontWeight="600" fill="var(--ink-1)">{METRO_LABEL[m]}</text>
              <text x={cx + cw - 14} y={cy + 16} fontSize="10" fill="var(--ink-3)" textAnchor="end">{last0[1].toFixed(0)}</text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
