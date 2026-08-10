# Explore — diagnosis

Written before any code change, per the build brief's Phase A. Every claim here
was reproduced against the files in `data/processed/`, the shipped bundle in
`site/dist/`, and the running app — not inferred from the source.

Method: reproduce → isolate → root cause. Where a theme is empty, the question
answered is not "is it empty" but "which of the four possible causes is it":
a missing join, an empty series for the selected geography, a lazy-chunk
failure, or an absent empty state.

---

## Summary

| | |
| --- | --- |
| Processed datasets on disk | **26** |
| Shipped to the browser in `history-manifest.json` | **23** (3 are merged into `core.json` instead) |
| Datasets Explore actually reads | **2** — `world_bank`, `oecd_economic_outlook` |
| Themes with any theme-specific panel | **2 of 7** (Money, Weather) |
| Themes rendering nothing but the two universal tools | **5 of 7** (Visas, Jobs, Homes, People, Daily life) |
| Charting cost | `charts-*.js` — **380.5 KB** raw, 113.4 KB gzip, parsed on every Explore and Compare visit |

**The root cause is not a data failure.** Every dataset the design needs is
present, well-shaped, and already shipped to the browser. The wiring was never
written: `Explore.tsx` contains exactly two theme-conditional mounts, and
`loadHistory()` — the lazy per-source loader in `site/src/data/store.ts` — has
exactly one caller in the whole codebase.

```
$ grep -rn "loadHistory(" site/src
site/src/data/store.ts:26      export function loadHistory<T>(sourceId: string)
site/src/components/ExploreCharts.tsx:42   loadHistory<…>('world_bank')
site/src/components/ExploreCharts.tsx:43   loadHistory<…>('oecd_economic_outlook')
```

That is the whole of it. Two ids, one component, one theme.

The second root cause is the **absent empty state**. A theme with no panel
renders the scatter builder and the weights tool and nothing else, with no
sentence explaining why. A visitor cannot tell "we deliberately draw no trend
line for visa rules" from "the pipeline is broken", so the page reads as the
latter. Every honest hole in this dataset is invisible.

---

## What renders today, theme by theme

`site/src/routes/Explore.tsx` mounts, in full:

```tsx
{active === 'money'   && <DeferUntilVisible …><EconomyHistory /></DeferUntilVisible>}
{active === 'climate' && <DeferUntilVisible …><ClimateMatcher /></DeferUntilVisible>}
<DeferUntilVisible …><ScatterBuilder /></DeferUntilVisible>   // every theme
<DeferUntilVisible …><WeightsTool /></DeferUntilVisible>      // every theme
```

### Money

| | |
| --- | --- |
| Wired | `world_bank` (`gdp_per_capita_usd`), `oecd_economic_outlook` (`real_gdp_growth_pct`, projections only) |
| Renders | One recharts `LineChart`: DE/CA/NL actual + OECD overlay + naive extrapolation. Country set is **hardcoded** (`const picks = ['DE','CA','NL']`) — no picker. |
| Unwired but present | `stackoverflow_survey` (developer pay distributions, 15 countries), `oecd_indicators` (`avg_wages`, `tax_wedge`), `levels_fyi` (city level, used on city pages) |
| Broken | Nothing. This is the one theme that works. |
| Missing | No lens control, no picker, no CSV, no confidence chip in the footer. |

### Visas & staying

| | |
| --- | --- |
| Wired | **nothing** |
| Renders | Scatter builder + weights tool only |
| Relevant data | Not in `data/processed/` at all — visa routes, PR/citizenship years and salary floors live in `data/countries.json` and are already in `core.json`. `visa.skilled_routes[].salary_threshold_usd` is populated for 11 of 15 countries; `pr_years_typical` / `citizenship_years_typical` for 14 of 15. |
| Root cause | No panel was written. The data needs **no fetch at all** — it is already in the blocking `core.json` load. |
| Honest hole | 4 countries have no salary floor (US, CA, IT, and one more): they run on points or sponsorship. Today nothing says so. |

### Finding work

| | |
| --- | --- |
| Wired | **nothing** |
| Unwired but present | `eurostat_ict_specialists` (10 countries + an EU-27 benchmark, 2004–2025, complete), `indeed_hiring_lab_job_postings` (**30** US metros, monthly Feb 2020 →, 78 points each), `eurostat_total_employment`, `bls_oews`, `wipo_gii` |
| Root cause | No panel written. Not a join failure: `eurostat_ict_specialists.data.countries.DE.ict_share_of_employment_pct` runs 2004 → 2025 with no gaps, and `eu27_benchmark` is a sibling key already in the right shape. |
| Confirmed hole | **`bls_oews` is a single-year snapshot** — verified, not assumed: every metro's `employment` array has exactly one element, `[{year: 2025, value: …}]`. It cannot be drawn as a series and must not be. |
| Confirmed hole | The Gulf (AE, QA) has **no ICT count** in any wired source. Eurostat stops at EU/EFTA. No substitute exists that could honestly be labelled. |

### Homes & rent

| | |
| --- | --- |
| Wired | **nothing** |
| Unwired but present | `bis_property_prices` (13 countries, quarterly real index, 1970 → 2026), `fhfa_hpi_metro` (30 US metros), `teranet_national_bank_hpi` (6 Canadian cities), `uk_hpi` (London, Edinburgh, Manchester, monthly from 1968), `oecd_indicators.house_prices` |
| Root cause | No panel written. The BIS file is the largest series on the site (430.9 KB shipped) and nothing reads a byte of it. |
| Confirmed hole | **`numbeo_history.data.by_city` is an empty object `{}`** — verified. Country-year rows exist (2015–2025); per-city rent history does not, because Numbeo's per-city archive renders client-side and its terms bar bulk use. City rent history must therefore be *country trend × the city's current rent*, labelled exactly that. |
| Confirmed hole | No institutional housing forecast is live: `imf_weo` is blocked (below) and `worldbank_gep` is recorded `unavailable` with an empty `data` object. |

### People like you

| | |
| --- | --- |
| Wired | **nothing** |
| Unwired but present | `mipex` (9 countries, 2020–2024), `un_wpp` (15 countries, 1990–2100 with `is_projection` flags), `un_migrant_stock`, `wikipedia_english_speakers`, `ef_epi` |
| Root cause | No panel written. |
| Confirmed hole | MIPEX has **no scores for AU, US, GB, NO** — they are absent from the workbook, not zero. Naming them is the honest render. |
| Confirmed hole | `un_migrant_stock` is a **snapshot**, not a series: `origins_latest` and `iranian_born` carry one reference year (2024). It belongs on country pages, not as a curve here. |

### Daily life

| | |
| --- | --- |
| Wired | **nothing** |
| Unwired but present | `world_happiness_report` (15 countries, 2011–2025, each row carrying `rank`, `score` and a `ranked_countries_per_year` denominator), `rsf_press_freedom` (15 countries) |
| Root cause | No panel written. |
| Confirmed hole | `rsf_press_freedom` holds **2022 → 2026 only** — five rows per country. RSF rebuilt its methodology in 2022; the pre-2022 scores exist upstream but are not comparable, and the processed file already reflects that decision. Drawing them joined would be the lie. |

### Weather

| | |
| --- | --- |
| Wired | `ClimateMatcher`, reading `core.json` (`city.climate`) — not a processed file |
| Renders | The matcher, which correctly scores nothing until the user sets a limit |
| Unwired but present | `climate_normals` — 21 cities × 12 months. Its content is already mirrored into `core.json` as `city.climate.monthly`, so a monthly chart needs **no extra fetch**. |
| Root cause | No chart written; the matcher is a tool, not a view of the data. |
| Confirmed hole | **21 of 73 cities carry monthly normals.** The other 52 were not fetched: the Open-Meteo archive run hit its hourly rate limit and stopped cleanly (`meta.cities_pending_rate_limit`). They are named, never guessed. |

---

## The five findings carried in from the design pass — each confirmed

**1 · `stackoverflow_survey` holds only the 2024 wave.** Confirmed:

```
by_country_experience.US waves present: ['2024']
bands: ['all', 'mid', 'new_grad', 'senior']
US 2024 mid: {median_usd: 110000, p25_usd: 85000, p75_usd: 145000, n: 794, thin_sample: false}
```

Every one of the 15 countries has exactly one key, `"2024"`. Wiring 2017–2023 is
a pipeline task (fetch and parse the archived survey dumps), not a UI task. The
percentile and `n` fields are already present, so the distribution render is
possible today; only the time axis is not.

**2 · `recharts` also rides on Compare.** Confirmed — two importers:

```
site/src/components/ExploreCharts.tsx:13   from 'recharts'
site/src/components/ClimateOverlay.tsx:14  from 'recharts'
```

`ClimateOverlay` is rendered by `Compare.tsx`, so removing recharts is not an
Explore-only change. It is one shared 380.5 KB chunk (`charts-*.js`).

**3 · `imf_weo` is blocked at source.** Confirmed:

```
meta: kind='institutional_forecast' institution='IMF' status='blocked'
data: {}    ← empty object, not missing, not zero
```

`data/provenance.json` records the reason: every `imf.org` host answers 403 to
the build environment. The parser is written and waiting. No IMF line can be
drawn, and an approximation labelled IMF would be worse than the gap.

**4 · `bls_oews` returns the current year only.** Confirmed above — one element
per metro, `year: 2025`. A snapshot, not a series.

**5 · Numbeo per-city history is unobtainable.** Confirmed above —
`by_city` is `{}`.

---

## Performance

`charts-*.js` is **380.5 KB raw / 113.4 KB gzip**, imported by both
`ExploreCharts.tsx` and `ClimateOverlay.tsx`. It is code-split, so it does not
land on Home — but every Explore visit and every Compare visit downloads and
parses it. Lighthouse, desktop preset, against the built site:

```
route             perf  a11y   LCP     TBT     CLS
home              100    96    0.5 s   10 ms   0
compare           100   100    0.8 s    0 ms   0
explore-money      80   100    0.7 s   30 ms   0.437   ← below gate
explore-jobs       86   100    0.6 s    0 ms   0.275   ← below gate
explore-housing    86   100    0.6 s    0 ms   0.275   ← below gate
explore-life       86   100    0.6 s    0 ms   0.275   ← below gate
city              100   100    0.5 s    0 ms   0
data               99   100    0.6 s    0 ms   0.061
```

**A correction to the brief's symptom, from measurement.** The build brief
records `/explore/money` at "~55 on Lighthouse performance — recharts is ~390 KB
to parse". At this commit it measures **80**, and the deficit is almost entirely
**layout shift (CLS 0.437)**, not parse time (TBT is 30 ms). Two things changed
underneath that number:

- `ExploreCharts` is already `React.lazy`, so the recharts chunk downloads and
  parses *after* first paint rather than during boot. It still costs the visitor
  380.5 KB, but it no longer blocks the metric that scores.
- Package 4 raised the lazy-route placeholder to a full viewport, which removed
  the route-swap shift.

What remains is `DeferUntilVisible`: each panel reserves a `minHeight`
placeholder (430 / 520 / 200 px) and then swaps in content of a different
height, shifting everything below it. **Four Explore routes fail the ≥90 gate on
CLS alone**, and the three "empty" themes fail it while displaying almost
nothing — which is its own indictment.

This does not change the plan. The kit removes 380.5 KB and the rebuild replaces
the guessed placeholder heights with real content, but the fix that actually
moves the score is making panels reserve the height they will occupy.

The design's answer is a dependency-free SVG chart kit under 10 KB min+gz, which
also removes the chunk from Compare.

---

## What this means for the build

Nothing here is a data repair. Every series the design asks for exists, is
correctly shaped, and is already shipped. The work is:

1. **Wire the 5 dark themes** — the datasets are present and need no pipeline
   change.
2. **Replace recharts** with the kit, on Explore *and* Compare.
3. **Give every hole a card that names it** — the dataset, the reason, and where
   it is tracked. Five of the six holes above are permanent or upstream-blocked
   facts about the data, not bugs, and the page should say so in its own voice.

One pipeline gap is worth an owner's attention and is recorded in
`NEEDS-DECISION.md`: the Stack Overflow archive waves (2017–2023) are the single
change that would turn the pay panel from one wave into a real time series.
