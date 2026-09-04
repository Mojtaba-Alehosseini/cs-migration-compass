/* Money — GDP per person with a lens that morphs, and real pay distributions.
 *
 * The lens is the signature control: the same lines re-read as dollars, as an
 * index, or as the change itself. Two of those are the same shape at different
 * scales, so they morph; the third is a different chart, so it crossfades.
 *
 * The yearly-change lens drops the OECD overlay on purpose. The OECD projects
 * REAL growth; this line is nominal US$. Drawn side by side as levels that is a
 * disclosed approximation, but drawn as year-on-year percentages they would be
 * read as the same quantity — so the overlay goes, and the footer says why.
 */

import { useMemo, useState } from 'react'
import { Chart } from '../chart/Chart'
import type { ChartCfg, Series } from '../chart/engine'
import { Seg, Picker, ChartFoot, ChartTable, Gap, ThemeSkeleton, ChartSkeleton, type HeroStat } from './Controls'
import { WagePanel } from './WagePanel'
import { useAsync } from './useAsync'
import { loadMoney, loadWages, naiveLine, yoy, type MoneyData, type Pair } from '../../data/explore'
import { money as fmtMoney, moneyShort } from '../../data/format'

type Lens = 'level' | 'index' | 'yoy'

const cc = (c: string) => `var(--c-${c})`
const last = <T,>(a: T[]) => a[a.length - 1]!

export function moneyHero(d: MoneyData): HeroStat[] {
  const nl = d.gdp.NL ? last(d.gdp.NL) : null
  const de = d.gdp.DE
  const us = d.so.US?.mid
  return [
    { value: nl?.[1] ?? null, format: (v) => fmtMoney(v),
      label: `income per person in the Netherlands, ${nl?.[0] ?? ''}`, source: 'World Bank' },
    { value: de ? last(de)[1] / de[0]![1] : null, format: (v) => `×${v.toFixed(1)}`,
      label: 'German income growth since 1990', source: 'nominal US$' },
    { value: us?.[1] ?? null, format: (v) => fmtMoney(v),
      label: 'US mid-level median, developers', source: 'Stack Overflow 2024' },
  ]
}

export function MoneyTheme() {
  const { data, error } = useAsync(loadMoney, 'money')
  const { data: wages, error: wagesError } = useAsync(loadWages, 'wages')
  const [lens, setLens] = useState<Lens>('level')
  const [picks, setPicks] = useState(['DE', 'CA', 'NL'])

  const cfg = useMemo<ChartCfg | null>(() => {
    if (!data) return null
    const series: Series[] = []
    for (const c of picks) {
      const act = data.gdp[c]
      if (!act?.length) continue
      const tail = last(act)
      // The OECD gives growth rates, not levels: compound them onto the last
      // observed value so the projection continues the same line.
      const growth = (data.eo[c] ?? []).filter(([y]) => y > tail[0])
      let v = tail[1]
      const proj: Pair[] = [[tail[0], tail[1]]]
      for (const [y, g] of growth) { v *= 1 + g / 100; proj.push([y, v]) }
      const base = act[0]![1]

      if (lens === 'level') {
        series.push({ key: c, label: c, color: cc(c), pts: act, hoverLabel: c })
        if (proj.length > 1) series.push({ key: `${c}_p`, color: cc(c), pts: proj, mode: 'projection', hoverLabel: `${c} · OECD` })
        // Our own line only where the chart is not already crowded.
        if (picks.length <= 3) series.push({ key: `${c}_n`, color: cc(c), pts: naiveLine(act, 2031), mode: 'naive' })
      } else if (lens === 'index') {
        series.push({ key: c, label: c, color: cc(c), pts: act.map(([y, x]) => [y, (x / base) * 100] as Pair), hoverLabel: c })
        if (proj.length > 1) {
          series.push({ key: `${c}_p`, color: cc(c), pts: proj.map(([y, x]) => [y, (x / base) * 100] as Pair), mode: 'projection', hoverLabel: `${c} · OECD` })
        }
      } else {
        series.push({ key: c, label: c, color: cc(c), pts: yoy(act), hoverLabel: c })
      }
    }
    const y = lens === 'level'
      ? { min: 0, max: 95000, ticks: [[25000, '$25k'], [50000, '$50k'], [75000, '$75k']] as [number, string][] }
      : lens === 'index'
        ? { min: 60, max: 420, ticks: [[100, '100'], [200, '×2'], [300, '×3'], [400, '×4']] as [number, string][] }
        : { min: -12, max: 14, ticks: [[-10, '−10%'], [-5, '−5%'], [0, '0'], [5, '+5%'], [10, '+10%']] as [number, string][] }

    return {
      aria: `GDP per person, ${picks.join(', ')}, ${lens === 'level' ? 'US dollars' : lens === 'index' ? 'indexed to 1990' : 'year-on-year change'}`,
      x: { min: 1990, max: 2031, ticks: [[1990, '1990'], [2000, '2000'], [2010, '2010'], [2020, '2020'], [2031, '2031']] },
      y,
      today: 2025,
      future: lens === 'yoy' ? null : 2025,
      zero: lens === 'yoy' ? 0 : null,
      ann: lens === 'yoy' ? [[2009, '2009'], [2020, 'covid']] : [],
      series,
      fmtX: (v) => String(v),
      fmtV: lens === 'level'
        ? (p) => fmtMoney(p[1])
        : lens === 'index'
          ? (p) => `×${((p[1] ?? 0) / 100).toFixed(2)} since 1990`
          : (p) => `${(p[1] ?? 0) > 0 ? '+' : ''}${(p[1] ?? 0).toFixed(1)}%`,
    }
  }, [data, lens, picks])

  const insight = useMemo(() => {
    if (!data) return ''
    return picks
      .map((c) => {
        const a = data.gdp[c]
        return a?.length ? `${c} ×${(last(a)[1] / a[0]![1]).toFixed(1)}` : ''
      })
      .filter(Boolean)
      .join(' · ')
  }, [data, picks])

  if (error) {
    return <div className="panel s6"><p className="nodata">
      Income history could not be loaded ({error}). Nothing is drawn rather than something approximate.
    </p></div>
  }
  if (!data || !cfg) return <ThemeSkeleton panels={[['s6', 563], ['s4', 443], ['s2', 443], ['s6', 1159]]} />

  /* Both captions below describe LINES, so they are read off the lines that
     were actually built, never inferred from the lens or the number of picks.
     The first version of this fix inferred: it printed "paler line = OECD
     projected real growth ..." on every lens but `yoy`, and the UAE and Qatar
     have no OECD Economic Outlook rows at all, so selecting only those two
     produced the caption with nothing paler on screen — the exact fault the
     same change had just removed from the dashed caption one line below.
     `picks.length <= 3` had the same shape: it is the condition the naive line
     is drawn UNDER, not evidence that one was drawn. */
  const drawsProjection = cfg.series.some((s) => s.mode === 'projection')
  const drawsNaive = cfg.series.some((s) => s.mode === 'naive')
  // The `yoy` lens hides the overlay deliberately, and only has something to
  // say about that when an overlay exists for what is currently selected.
  const hasOverlayData = picks.some((c) => {
    const act = data.gdp[c]
    return act?.length ? (data.eo[c] ?? []).some(([y]) => y > last(act)[0]) : false
  })

  const csvRows = picks.flatMap((c) => (data.gdp[c] ?? []).map(([y, v]) => ({ country: c, year: y, gdp_per_person_usd: v })))

  return (
    <>
      <div className="panel s6">
        <h2>Income per person, and where the OECD thinks it goes</h2>
        <div className="sub">
          GDP per person since 1990. Switch the lens: dollars, everything indexed to
          1990, or the year-to-year change itself.
          {drawsProjection && ' The paler continuation is the OECD’s projection.'}
          {drawsNaive && ' The dashed line is ours and is not a forecast.'}
          {' '}Drag across the chart to read any year.
        </div>
        <div className="crail">
          <Seg
            label="How to read income"
            value={lens}
            options={[['level', '$ per person'], ['index', 'indexed to 1990'], ['yoy', 'yearly change']]}
            onChange={setLens}
          />
          <Picker
            label="Countries"
            items={Object.keys(data.gdp).sort().map((c) => ({ k: c, cc: c, label: c }))}
            active={picks}
            onChange={setPicks}
          />
        </div>
        <p className="insight">Since 1990, income per person: <b>{insight}</b></p>
        {/* A lens that changes the scale morphs; the one that changes the
            quantity crossfades, because there is nothing to interpolate. */}
        <Chart id="ex-gdp" cfg={cfg} transition={lens === 'yoy' ? 'fade' : 'morph'} />
        <ChartFoot csv={{ name: 'compass-gdp-per-person.csv', rows: csvRows }}>
          <span className="chip chip-ok">● Official · World Bank</span>
          <span className="chip chip-ok">● {data.eoChip}</span>
          {/* NEEDS-DECISION #4, decided package 11 and implemented here. The
              overlay compounds the OECD's projected REAL growth onto the World
              Bank's NOMINAL US$ level. The yearly-change lens hides the overlay
              and said so in a chip; the level and indexed lenses DRAW it and
              said nothing, disclosing the same mismatch on one lens and not the
              two where it is actually on screen.

              Every caption here is now conditional on the SERIES THAT EXIST,
              not on the lens or the pick count. Two faults of the same kind
              were fixed that way: "dashed = naive extrapolation" printed on the
              indexed lens, where no dashed line is drawn; and the paler-line
              caption printed for the UAE and Qatar, which have no OECD
              Economic Outlook rows, so nothing paler is on screen for them on
              any lens. The second was introduced by the first version of this
              very fix and found by package 30's adversarial review. */}
          {lens === 'yoy' && hasOverlayData && (
            <span className="chip chip-quiet">
              OECD overlay hidden here — it projects real growth; this line is nominal US$, and
              mixing them would lie
            </span>
          )}
          {drawsProjection && (
            <span className="chip chip-quiet">
              paler line = OECD projected real growth compounded onto a nominal US$ level — not the
              same quantity as the solid line
            </span>
          )}
          {drawsNaive && (
            <span className="chip chip-quiet">dashed = naive extrapolation, not a forecast</span>
          )}
        </ChartFoot>
        <ChartTable
          caption={`Income per person, ${picks.join(', ')} — the numbers behind this chart`}
          head={['Country', 'Year', 'GDP per person (US$)']}
          rows={csvRows.filter((r) => r.year % 5 === 0).map((r) => [r.country, r.year, fmtMoney(r.gdp_per_person_usd)])}
        />
      </div>

      <SoBoxes data={data} />

      <Gap title="Where’s the IMF line?" where={<>Tracked on the <a href="#/data">Data &amp; methods page →</a></>}>
        <p>
          Blocked, and we say so: every <code>imf.org</code> host answers 403 to our build
          environment. The parser is written and waiting. Until it runs there is <b>no IMF line at
          all</b> — an approximation labelled IMF would be worse than the gap.
        </p>
      </Gap>

      {wagesError ? (
        <div className="panel s6"><p className="nodata">
          Wage distributions could not be loaded ({wagesError}). Nothing is drawn rather than something approximate.
        </p></div>
      ) : !wages ? (
        <div className="panel s6"><ChartSkeleton height={1159} /></div>
      ) : (
        <WagePanel wages={wages} />
      )}
    </>
  )
}

/* -------------------------------------------------------------------------- */

const SO_COUNTRIES = ['US', 'DE', 'GB', 'NL', 'CA']
const BANDS: [keyof MoneyData['so'][string], number, number][] = [['ng', 3, 0.35], ['mid', 9, 0.6], ['sr', 15, 0.9]]

/** Distributions, not medians: the box is the middle half of answers and the
 *  notch is the median. A thin sample draws a thinner notch — the point is real,
 *  the number behind it is a handful of people. */
function SoBoxes({ data }: { data: MoneyData }) {
  const W = 620
  const ROW = 42
  const PL = 46
  const PR = 18
  const TOP = 30
  const rows = SO_COUNTRIES.filter((c) => data.so[c])
  const H = TOP + rows.length * ROW + 26
  const X = (v: number) => PL + (v / 210000) * (W - PL - PR)

  const csv = rows.flatMap((c) => BANDS.flatMap(([band]) => {
    const b = data.so[c]![band]
    return b ? [{ country: c, band, p25_usd: b[0], median_usd: b[1], p75_usd: b[2], respondents: b[3] }] : []
  }))

  return (
    <div className="panel s4">
      <h2>What developers told Stack Overflow — 2024</h2>
      <div className="sub">
        Not just medians: the box is the middle half of answers (25th–75th
        percentile), the notch is the median. One wave is wired so far — this grows a time axis
        the day the 2017–2023 archives land in the pipeline.
      </div>
      <div className="chart">
        <svg viewBox={`0 0 ${W} ${H}`} role="img"
          aria-label="Developer pay distribution by country and experience, 2024">
          {[[50000, '$50k'], [100000, '$100k'], [150000, '$150k'], [200000, '$200k']].map(([v, l]) => (
            <g key={String(v)}>
              <line x1={X(v as number)} x2={X(v as number)} y1={TOP - 8} y2={H - 20} className="gridline" />
              <text x={X(v as number)} y={H - 7} fontSize="10" fill="var(--ink-3)" textAnchor="middle">{l}</text>
            </g>
          ))}
          <text x={PL} y="12" fontSize="10" fill="var(--ink-3)">
            box = middle half of answers · notch = median · rows: start / 3–6 yrs / senior stacked
          </text>
          {rows.map((c, i) => {
            const y0 = TOP + i * ROW + 8
            const col = cc(c)
            return (
              <g key={c}>
                <text x={PL - 8} y={y0 + 13} fontSize="11" fontWeight="600" fill={col} textAnchor="end">{c}</text>
                {BANDS.map(([band, dy, op]) => {
                  const b = data.so[c]![band]
                  if (!b) return null
                  const [p25, med, p75, n, thin] = b
                  return (
                    <g key={band}>
                      <rect x={X(p25)} y={y0 + dy - 2.6} width={Math.max(0, X(p75) - X(p25))} height={5.2}
                        rx={2.6} fill={col} opacity={op * 0.42}>
                        <title>{`${c} ${band}: p25 ${fmtMoney(p25)} · median ${fmtMoney(med)} · p75 ${fmtMoney(p75)} · n=${n}`}</title>
                      </rect>
                      <line x1={X(med)} x2={X(med)} y1={y0 + dy - 4.6} y2={y0 + dy + 4.6}
                        stroke={col} strokeWidth={thin ? 1.2 : 2.2} opacity={op} />
                      {band === 'sr' && (
                        <text x={X(med) + 5} y={y0 + dy + 3.5} fontSize="9.5" fill="var(--ink-3)">{moneyShort(med)}</text>
                      )}
                    </g>
                  )
                })}
              </g>
            )
          })}
        </svg>
      </div>
      <ChartFoot csv={{ name: 'compass-so-pay-2024.csv', rows: csv }}>
        <span className="chip chip-note">◐ Research · Stack Overflow 2024</span>
        <span className="chip chip-quiet">respondents self-select — compare shapes, not gospel</span>
      </ChartFoot>
      <ChartTable
        caption="Developer pay by country and experience — the numbers behind this chart"
        head={['Country', 'Band', 'p25', 'Median', 'p75', 'n']}
        rows={csv.map((r) => [r.country, r.band, fmtMoney(r.p25_usd), fmtMoney(r.median_usd), fmtMoney(r.p75_usd), r.respondents])}
      />
    </div>
  )
}
