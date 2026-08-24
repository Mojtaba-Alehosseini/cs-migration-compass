# Data fitness for purpose

_Packages 15 and 16. For every claim the site makes on screen: what the evidence actually
supports, at what precision, and — where it falls short — the corrected form. Package 15 measured;
package 16 applied the corrections and swept the datasets package 15 never reached (§10)._

This is not a validation report. `make validate` and `make audit` already answer "is this value
legal?". This answers a different question: **is the data fit for the claim the page makes on it?**
A number can pass every invariant in the repo and still be summarised with the wrong estimator,
published to a precision its sample cannot carry, or labelled as something it is not.

Method, evidence and p-values: `REPORT-P15.md`. Machine-readable findings:
`data/quality_history/statistical_audit.json`, `profile.json`, `title_classifier_eval.json`,
`dedupe_eval.json`, `postings_pay_rederived.json`.

**Two rules governed every change made under these packages.** No published value was altered —
every correction is to a method, a summary, a disclosure or a boundary. And no check is reported
clean unless it has been observed to fail on a constructed violation; each harness ships a
`--self-test` that does exactly that.

**One value WAS altered, and it belongs in the preamble rather than a footnote.** Package 16
corrected Vancouver's coordinates (§10): the geocoder had returned both the city and Vancouver
Island and the pipeline picked the island, putting the map dot 174 km out to sea. Both points are
published by the source; what changed is which of them this repo selected. That is a corrected
*selection*, not an altered source value — but the distinction is fine enough to state plainly
instead of leaving the blanket claim above to cover it.

---

## Summary

| Claim | Verdict | Supported precision |
|---|---|---|
| Median advertised pay by country (`/work`) | **Supported for five countries** | 5 countries, not 7; recent postings only; nearest $1,000 — see §1's package-17 update |
| Years to own a home (city cards, `/compare`) | **Supported, but not to one decimal** | `~23 yrs`, never `22.6`; the rounding band is on the source card |
| City salary bands (new-grad / mid / senior) | Supported | Nearest $1,000 |
| Wage distribution panel (`/explore/money`) | Supported | As published — already median-based |
| Canadian house-price trend (Teranet) | **Multi-year direction only** | No single value, monthly *or* annual |
| Cost-of-living and rent inputs | Supported | As published |
| "N postings, M companies" counts | Posting count includes re-listings (~6%); **company count sound** | Distinct roles vs raw rows |
| Cross-source salary agreement | Supported as *correlation*, not as *agreement* | Never blended |
| City map coordinates | Supported — after correcting one 174 km error | 73/73 verified against an independent gazetteer |
| Currency conversion (`fx_rates`) | Supported | Agrees with the ECB to better than 0.1% |
| The other datasets | Swept (25); **the only confirmed defect is Teranet's own** | See §10 for coverage gaps and what each is fit for |

---

## 1. "Median advertised pay by country" — not supported as labelled

**What the page said** (the route is `/work` since package 17; `/postings` redirects there). A
dotted-line chart, captioned *"Annual-salary postings only
(5+ per country to appear), converted to USD at each posting's own year"*, showing a median for
seven countries.

**What the data supports.** Three separate problems compound:

1. **The panel is not a software-jobs panel.** Only ~28% of postings are software roles. The
   harvest takes *every* job a seeded company posts, so the panel contains nurses, retail sales
   associates and seasonal store staff. Three measurements land in the same place: a keyword rule
   **27.09%** (`engineer` or `developer` as a substring, 13,074 of 48,267), a 400-title
   hand-labelled sample **29.0%** (95% CI 24.8-33.6%), and a trained classifier **27.89%**. All
   three fall inside the hand-label interval. They are **not independent** - the classifier is
   trained on those hand labels, so it corroborates the keyword rule, not itself - and the keyword
   rule is the weakest of the three, since a substring match counts "engineering manager" and
   "sales engineer" as software. What this supports is "roughly a quarter to a third", not a share
   to two decimals. The occupational mix also differs by country, so the error differs by country.
2. **The sample is far too small in almost every country — and much of that is an FX artefact.**
   Singapore's original figure rested on **five** postings whose 95% bootstrap interval ran
   **$60,177 - $317,412**. But the deeper cause is not thin harvesting: for every country except
   the US, **the current year cannot be priced at all**. The World Bank exchange-rate series ends
   at 2025 and this repo never substitutes a neighbouring year's rate, so 88-92% of the annual-pay
   postings for Great Britain, Canada, Germany and France — almost all of them 2026 — have no USD
   value and cannot enter any median. Those countries are not data-poor; their recent data is
   unpriceable until the rate is published.
3. **The published precision is manufactured.** Employer-entered pay is heaped to round thousands
   (77.5% of native annual minima end in 0 or 5; 65% end in 000; terminal-digit uniformity rejected
   at p < 0.001). FX conversion then turns a round native figure into `$152,969.52`. The decimals
   were never in the source.
4. **The figure carried no date, and that turned out to matter more than anything else.** Package
   16 found that the US median rested on 1,121 rows of which **714 were posted in 2017 and 148 in
   2016**, 872 of them USAJOBS federal listings — and **not one row from 2026**, while 31,829 of
   the 48,267-row corpus is 2026. The cause was a conversion that should never have been attempted:
   `to_usd()` looked up an FX rate even for USD→USD, so every 2026 US posting quoted in dollars
   failed for want of a 1.0 nobody had published yet. USD→USD is the identity; the short-circuit is
   now applied for USD only, and every other currency still requires its own year.

**Re-derived on the clean subset** — de-duplicated, restricted to software titles, and limited to
postings from 2024 onward — the US median is **$205,000**, against **$140,000** for the raw
all-occupation population: **+46.4%**.

*Both earlier figures are superseded and neither is reproducible now, which is the finding rather
than a regression.* Package 15 measured +18.9% ($82,994 → $98,688) and package 16 reproduced it
exactly — on a corpus that was silently missing its own current year. With 2026 restored the pooled
median becomes $175,000, sitting between a 2026 population near $204,000 and a 2016-2017 one near
$87,000: a bimodal mixture wearing a point estimate. Pooling nine years of nominal advertised pay
is not a defensible summary, so the published figure is windowed.

**Corrected form.** One country, one recent window, rounded to the nearest $1,000, with its
interval and its composition shown:

> Median advertised pay, software roles only — United States: **$205,000** (95% CI
> $202,000-$210,000, n = 1,807 distinct software roles posted 2024 or later).
> 2024: 27 · 2025: 219 · 2026: 1,561 — 86.4% from the most recent year, and 91.3% from a single
> provider.

**The window has a cost and the page states it.** Every USAJOBS row is dated 2016-2018, so
restricting to recent postings removes US federal listings entirely and leaves private ATS boards.
That is a real selection, disclosed on screen rather than absorbed.

Every other country is below the sample floor, mostly for the FX reason above. **The remaining
product decisions** — how wide the vintage window should be, and whether to publish anything for a
country whose current year cannot be priced — are recorded in `NEEDS-DECISION.md`.

**Update, package 17 — the FX artefact was the binding constraint, and four more countries clear
the floor once it is lifted.** Problem 2 above identified the cause correctly: those countries were
not data-poor, their recent data was unpriceable. `to_usd()` now takes a maximum gap
(`MAX_FX_GAP_YEARS = 2`, chosen from this repo's own measured error table) which only the postings
conversion passes; every historical series keeps exact year-matching. Software rows priced across
the corpus go **1,864 → 2,168**, and **one publishable country becomes five**:

| | US | GB | CA | FR | DE |
|---|---:|---:|---:|---:|---:|
| n (distinct software roles, 2024+) | 1,807 | 122 | 75 | 31 | 30 |
| published median | $205,000 | $160,000 | $118,000 | $96,000 | $121,000 |
| **share converted at a neighbouring year's rate** | **0.2%** | **89.3%** | **76.0%** | **93.5%** | **86.7%** |

**That last row is the caveat, and it is now on screen.** Four of the five figures exist *because*
the rule was relaxed and rest overwhelmingly on substituted rates — never more than one year away,
but substituted. Each country's own `composition` block states its share, each median carries the
same estimate marker its inputs carry, and the panel prints one composition paragraph per country
rather than describing the US and leaving the other four to be assumed. The page is now honest
about resting on an allowance; it is not the same claim as five independently well-sourced medians.

The route is `/work`; `/postings` redirects there.

---

## 2. "Years to own a home" — supported, but not to one decimal

**What the page says.** e.g. *"22.6 yrs"* on a city card.

**What the data supports.** The quantity is real and the formula is stated, but three things
undercut the last digit:

- The inputs are rounded — rent and living costs to $10/month, price to $100/m².
- The output is the most skewed field in the dataset: **skew 6.38, excess kurtosis 41.1**. Its
  arithmetic mean sits **392% above its median**, which is why no average of it should ever be
  taken (and the site does not take one).
- It is a ratio whose denominator is a *difference* of two large numbers. Small input errors
  amplify sharply as savings approach zero — which the site already handles with its `unstable`
  marker and its "100+ yrs" clamp.

**Corrected form.** Quote a range, not a point. `22.6 yrs` should read **`~23 yrs`**, and for
cities near the instability boundary, a band. The existing `unstable` mark and the off-scale
treatment are correct and should stay.

**No change was made to any computed value.** This is a presentation-precision finding.

---

## 3. City salary bands — supported

New-grad / mid / senior bands are curated per city with a source, a date and a note. They are
single sourced figures, not sample means, so the log-normality finding does not apply to them. They
are already effectively rounded (granularity $1,000).

One caveat worth keeping visible: **`salary_usd_year` and `salary_levels_fyi` are not
interchangeable.** They correlate at Pearson r = 0.898, which reads as excellent agreement — but
Bland–Altman shows levels.fyi runs **1.22× high on average, with 95% limits of agreement from 0.79×
to 1.89×**. An individual city can differ by more than two-fold. Four cities are robust-z outliers:
Doha 2.20×, Dublin 2.04×, Valencia 2.02×, London 1.95×. They measure different constructs — market
base-pay bands versus self-reported big-tech total compensation — and the site is right never to
blend them.

---

## 4. Wage distribution panel — supported as published

`/explore/money` already reports medians, already refuses countries that cannot be compared at a
shared occupation depth, and already discloses reference years. Package 14's set-wide crosswalk fix
holds. Nothing in this audit contradicts it.

The one thing worth stating plainly: the **OECD benchmark ratio** compares a market-FX-converted
median against a PPP-adjusted OECD average (`NEEDS-DECISION #39`). That remains open and is
unchanged by this package.

---

## 5. Canadian house-price trend (Teranet) — multi-year direction only

**New defect, found in this audit.** **All six** Teranet cities in this repo carry **injected
per-observation noise** - residual autocorrelation of **+0.113 to +0.268** against **+0.985** for
both real published indices:

| Series | Residual ACF (lag 1) | Month-over-month ACF |
|---|---:|---:|
| Teranet Toronto | +0.237 | -0.40 |
| Teranet Vancouver | +0.268 | -0.47 |
| Teranet Montreal | +0.177 | -0.44 |
| Teranet Ottawa | +0.113 | -0.47 |
| Teranet Calgary | +0.235 | -0.42 |
| Teranet Halifax | +0.169 | -0.46 |
| **UK HPI London** (control) | **+0.985** | -0.05 |
| **FHFA New York** (control) | **+0.985** | +0.51 |

A genuine price index is *persistent* — this month's level is last month's plus a small change, so
residuals about a smooth trend are highly autocorrelated. Independent per-point noise destroys that
persistence and, because each month's error enters the month-over-month change twice with opposite
sign, drives the MoM autocorrelation sharply negative. The two real published indices in this same
repo behave exactly as expected; Teranet does not.

**This is not a parsing bug.** The stated base holds exactly (2005-06 = 100.0 for every city), the
long-run trend survives (Spearman with time = 0.909 for Toronto), and the pipeline transcribes the
endpoint faithfully. The endpoint is undocumented and the index is proprietary, which is the most
likely explanation.

**The annual figure is NOT rescued by averaging, and an earlier draft of this document said it
was.** That claim assumed 12 independent errors average down by root-12. They do - but the
per-point noise is so large that what survives still dominates the signal:

| City | Per-point noise | Noise left after annual averaging | Implied YoY sd from noise alone | Observed YoY sd |
|---|---:|---:|---:|---:|
| Toronto | 17.1% | 4.9% | 7.0% | 7.3% |
| Vancouver | 20.6% | 5.9% | 8.4% | 9.4% |
| Montreal | 21.3% | 6.2% | 8.7% | 10.8% |
| Ottawa | 17.7% | 5.1% | 7.2% | 6.7% |
| Calgary | 17.1% | 4.9% | 7.0% | 9.8% |
| Halifax | 21.3% | 6.1% | 8.7% | 10.7% |

Read the last two columns together. The year-over-year variation that **noise alone** would produce
is 7.0-8.7%, and the variation actually observed is 7.3-10.8%. Noise accounts for most of what the
annual series does, against an underlying trend of only **3.1-4.9% per year**. The annual residual
autocorrelation stays at 0.39-0.53 where it can be computed at all (three of the six cities;
the other three are too short), nowhere near a real index. Averaging cuts the noise by root-12
and it is still larger than the signal it is meant to reveal.

*(That trend range was first published as 3.1-4.1%, from a CAGR — the ratio of the first and last
annual values. Package 16 found that self-contradictory: a CAGR rests on exactly two observations
and so inherits the per-observation noise this very finding reports. A log-linear slope over all ~28
annual points averages the noise down instead of concentrating it in two values, and it moves
Vancouver from 3.1% to 4.4%. Both are now reported; the slope is the one to quote. The conclusion is
unchanged on either estimator — noise still exceeds trend.)*

**Corrected form.** **No single Teranet value - monthly or annual - is interpretable on its own.**
Only the multi-year direction survives, and only qualitatively. The honest options are to disclose
this on the chart, drop the series, or raise it with the publisher; that is a product decision and
is recorded in `NEEDS-DECISION.md` #43.

---

## 6. Cost-of-living, rent and apartment-price inputs — supported

Spot-checked against live Numbeo for a small sample of cities - four fields each (rent, price per
m2, and the two cost-of-living indices) - and every field checked transcribed faithfully: US cities
within 0.98-1.07x, Munich uniformly 1.13-1.15x, which is the EUR->USD rate applied consistently
across all four. **This is a spot check, not a census.** It covers a handful of cities out of 73 and
was done by hand against a live third-party page that changes continuously, so it is not
reproducible from this repo and no artifact records it. It is evidence that transcription is not
systematically broken; it is not evidence that every field of every city is correct.

**On the implied-rental-yield anomaly:** implied US gross yields do run far above non-US ones
(median 10.6% vs 4.9%, Mann–Whitney p = 3.6 × 10⁻¹¹). This audit reproduced it and then
**re-attributed its cause**. It is *not* a centre-versus-outside stock-composition artefact — the
gap is equally present at the centre, where both series are apartments (7.7% vs 4.0%, p = 2.6 ×
10⁻⁸). Nor is it a "new-world housing" artefact — Australia and Canada have US-like housing stock
and non-US yields. Both series come from the same Numbeo city page, same survey, same period, and
both transcribe correctly.

**Conclusion: an artefact of the yield identity itself, not a data defect.** The identity requires
rent and price to refer to *the same dwelling*; Numbeo's 1-bedroom rent and its whole-stock
price-per-m² do not. The 60 m² assumption was doing the rest of the work. **No input is wrong and
nothing needs correcting** — but the site should never publish a yield derived this way.

---

## 7. The posting count includes re-listings; the company count is sound

**What the page says.** *"48,267 postings, 1,723 companies, 6 sources."*

**What the data supports.** Collapsing each distinct (title, company, location) triple to one row -
at a threshold tuned to **precision 0.958 / recall 0.719** against 120 hand-labelled pairs -
removes **2,884 rows (5.98%)**. *(Those four figures are the committed corpus's, where all 120
labels still resolve. They move with the corpus; the live ones are in `dedupe_eval.json` beside
the `n` they were computed on — see the note below.)*

Those 120 pairs are **stratified** - 24 from each of five cosine bands, so the threshold is tuned
where the decision is hard - which means 0.958/0.719 describe that deliberately hard sample, not the
population. Reweighted by each band's population share, precision is unchanged at **0.958** (every
true and false positive falls in the top band) but recall drops to **0.678**, because the misses sit
in bands the sample over-represents. **0.678 is the figure to quote for real behaviour;** 0.719 is
the figure the threshold was selected on.

**These figures rest on the pairs that survive the corpus they are measured against, and that
number changes with every harvest.** The labels are keyed by `(id, occurrence)` since package 18;
postings expire, and a pair whose posting has left the corpus is not scored. The figures above were
computed on **120 of 120** surviving, which is the state of the committed corpus. The live count is
`tuned_on_n_pairs` in `data/quality_history/dedupe_eval.json` — read it there rather than assuming
120, and quote precision with the n it was computed on. `dedupe_postings.py` refuses to tune at all
below **12 surviving pairs in any cosine band, or 12 of either same_job class**: measured, dropping
one whole band leaves 96 of 120 pairs — an 80% survival rate — and reports precision 1.000 with
recall 0.000, because 23 of the 32 positive pairs live in a single band.

**The company count is not affected.** De-duplication loses exactly **zero** companies: 1,960
distinct employers before and 1,960 after, and not one of the 2,384 clusters spans more than one
company - which is by construction, since blocking is *by* company. An earlier draft of this
document claimed posting *and company* counts were both overstated by about 6%. That was wrong for
companies and is withdrawn.

**"Removable" is an upper bound on duplication, not a count of scraping artifacts.** Of the 2,884
removable rows, **99.9% carry their own distinct URL** and **33.6%** sit in a cluster spanning more
than one posting date. The largest cluster is **18 USAJOBS rows with 18 distinct announcement IDs**
running from 2017 onward - one federal role genuinely re-announced over years, not one posting seen
eighteen times. The labels behind the tuning table see only (title, company, location), so they
cannot separate a req scraped twice from a role re-announced, or opened in ten locations at once.

Worth recording because it corrects an expectation: **near-duplicates are *not* the larger
problem.** Normalised-exact matching finds 5.60%; near-duplicate matching adds only +0.38pp. A
looser threshold would delete real data - at cosine 0.70 precision falls to 0.311.

**Two stated limits on the 5.98%.** Duplicates posted by *two different employers* (an agency and
the hiring company) are invisible by construction, because matching is blocked by company. And three
employers - `bjakcareer`, `anduril industries` and `boxlunch` - exceed the distinct-key cap and
receive exact-key matching only, not near-duplicate matching. Both make 5.98% a floor on
near-duplicate detection at the same time as it is a ceiling on true duplication.

**Corrected form.** Quote the distinct-role count, or state that the raw count includes
re-listings. Leave the company count as published.

---

## 8. Panel representativeness — now measurable

The panel is ATS-seeded and skews to US/UK VC-backed tech. Measured against the site's own Eurostat
ICT-employment series rather than asserted:

Expected share is a country's share of **European ICT specialist headcount**
(`ict_specialists_thousands`). An earlier draft normalised `ict_share_of_employment_pct` instead -
a *within-country* percentage, which does not normalise across countries of different size and
inverted several of these rows. The corrected table:

| Country | Panel share | Expected share | Representativeness (1.0 = proportional) |
|---|---:|---:|---:|
| GB | 26.4% | 11.7% | **2.26x** over-represented |
| IE | 2.1% | 1.1% | 1.89x |
| FI | 1.7% | 1.3% | 1.31x |
| NL | 3.8% | 4.6% | 0.83x |
| SE | 2.0% | 3.1% | 0.64x |
| ES | 4.3% | 6.9% | 0.62x |
| DE | 9.0% | 15.0% | 0.60x |
| NO | 0.5% | 1.1% | 0.45x |
| DK | 0.3% | 1.1% | 0.30x |
| IT | 1.6% | 5.9% | **0.28x** - the most under-sampled |

The spread is about **8x** from Italy to Great Britain, so no per-country postings figure inherits a
proportional panel. **GB's basis year is 2019** - Eurostat stopped covering the UK after Brexit -
against 2025 for every other country, so the single largest over-representation is also the one
mixing vintages. That is flagged in the artifact rather than footnoted. This score is now computed
per country and is available for the UI to show.

---

## 9. What this audit did *not* establish

Stated so that silence is not read as a clean bill of health:

- **Benford's Law was tested and rejected as inapplicable.** Every series reads "nonconforming"
  (MAD 0.011–0.085) — including ones with no defect — because scale-bounded and index-normalised
  fields violate the test's own preconditions. It is not reported as evidence of anything here, and
  should not be by anyone else.
- **Model-based per-record validation (gradient-boosted out-of-fold residuals) was not run.** The
  city matrix has 72 rows and nine heavily collinear features; a per-record residual model on it
  would mostly be fitting the derived-field identities enumerated in §3-C.
- **Structural-break testing (CUSUM/Chow) on the long index series was not run.** The Teranet
  finding above makes break-detection on that series meaningless until the noise question is
  settled, and the remaining long series had no anomaly flagged by the profiling harness.
- **Revision analysis across packages was not run** — the repo keeps no per-package snapshot of
  source values to diff against. Worth adding.
- **The transfer assumption (§5.5) could not be tested as specified.** It needs countries with both
  posted salaries *and* official distributions at a shared occupation depth; after cleaning, only
  the US clears the sample-size floor, so there is no second country to fit a relationship against.
  This is a real blocker, not an omission, and it means **percentile transfer is not currently
  defensible into any country** on this evidence.

---

## 10. The other 22 datasets — swept, and what the sweep found

Package 15 profiled 54 datasets but deeply analysed four. These 22 feed real
features and had never been asked whether they support the claims made on them.
Package 16 applied the same battery: distributional shape, the residual-
autocorrelation test that found the Teranet defect, cross-dataset accounting
identities, vintage, and coverage against the site's own 15 countries and 73
cities. Full results in `data/quality_history/dataset_sweep.json`.

### The persistence test finds Teranet, and nothing else

**311 series tested across 25 datasets; the only ones confirmed are Teranet's own seven.** 454 more
were skipped **with a reason recorded**, because a check nobody can see the boundaries of is
indistinguishable from one that passed: 94 are rates or growth figures the test is invalid for, and
360 are shorter than the 36 points it needs. Ten datasets hold no time series at all and now say so
explicitly rather than reporting a silent zero.

**The first version of this sweep could not have found the defect it was built from, and that is
the most important thing in this section.** An adversarial review fed it the six Teranet cities
package 15 measured. It confirmed **zero of six**.

The rule required a flagged series to be an outlier *against its own peer family*. A whole-family
defect — one bad extractor corrupting every series it produces — has no outlier by construction:
the peer median is dragged down with the defect. That is exactly Teranet's shape, so "no second
Teranet" was being asserted by a rule that provably could not have found the first. It was also
grouping families by stripping one path segment, which made every Teranet city a family of one.

What made the original finding trustworthy was never peer spread. It was **separation from a
known-good control**: Teranet at 0.11-0.27 against UK HPI and FHFA at 0.985. That is the test now.
The peer family is still reported — a whole family reading low points at a shared extractor rather
than one bad series — but it can no longer veto a finding. The three real house-price indices are
swept alongside the other 22, so the control readings and the confirmed defect are **produced by
the pipeline** rather than asserted beside it: the run that says "nothing else" is the same run
that still finds Teranet.

Four series cross the threshold and are **reported but not claimed** — the annual hours-worked
series for GB, DE, IT and ES. They sit far below the control too, but they move 0.5-2.7% point to
point where injected noise of this kind moves 22-31%. Annual hours worked genuinely moves year to
year, so the test's precondition — a path smooth relative to the sampling interval — does not hold
for it. *(An earlier draft of this section said all four were rejected because their family shows
no gap. Two of the four **are** peer outliers; what rejects all four is the movement threshold.)*

*Two more defects in the sweep itself, both found before it produced anything anyone relied on.*
The series classifier read only the last path segment, so `NO/inflation_pct/value` classified on
`"value"`, was tested as a level, and was duly flagged — a spurious finding caused by the
classifier. And broadening series discovery to reach monthly data made it treat FHFA's `quarter`
field as a measurement, building the series 4,1,2,3,4,1,2,3… and producing 15 confident false flags
against the very index used as a control. Time components are now excluded from the value side.

### City coordinates were wrong, by 174 km

A wrong latitude fails no invariant. It breaks no total, shifts no distribution,
looks unremarkable in a profile. It silently puts a dot in the wrong place. The
only way to check it is against a different gazetteer, and it had to be a
genuinely different one: `city_coordinates` came from Open-Meteo's geocoder,
which is GeoNames-derived, and `climate_normals` used the same geocoder and
agrees with it to five decimal places. OpenStreetMap's Nominatim is independent.

All 73 were checked. **Vancouver was 174 km out**, sitting in the Strait of
Georgia. The geocoder had returned both `Vancouver` (a populated place,
population 662,248) and `Vancouver Island` (an island, population 748,937), and
the tie-break preferred the larger population — so the city's coordinates became
the island's. The `geocoded_as` field recorded the substitution faithfully the
whole time. Nothing read it.

Fixed at the cause: the geocoder now requires a populated-place feature code
before applying the population tie-break, so a landmass can never again stand in
for a settlement it merely contains. Re-checked after the fix: **73 of
73 cities within tolerance, median disagreement 0.46 km, worst
17.86 km** — a normal centroid-versus-settlement-point difference.

### FX rates agree with an independent source to better than 0.1%

Every converted figure on the site rests on `fx_rates`, taken from the World
Bank's annual period-average local currency per USD. Checked against the ECB's
own daily reference rates, averaged over the same calendar year — averaged
rather than sampled, because one day's rate is a different quantity from a
year's mean and comparing them would manufacture a discrepancy that is only a
definition difference.

| Currency | Year | World Bank | ECB annual mean | Difference |
|---|---:|---:|---:|---:|
| GBP | 2015 | 0.6545 | 0.6543 | +0.04% |
| SEK | 2018 | 8.6925 | 8.6957 | -0.04% |
| JPY | 2020 | 106.7746 | 106.7483 | +0.03% |
| CAD | 2022 | 1.3015 | 1.3017 | -0.01% |
| AUD | 2023 | 1.5052 | 1.5065 | -0.09% |

**5 of 5 agree, worst 0.087%.** These two are as independent as
this repo can get, and they agree to within a rounding error.

### An accounting identity holds across two Eurostat tables

ICT specialists divided by total employment should reproduce the published ICT
employment share. The two come from different Eurostat tables, and package 15
had already corrected a selection-bias figure for using the wrong one of them,
so this was worth checking rather than assuming. Across **191 country-years
the median disagreement is 0.146 pp and the worst is 0.482 pp**
(DE 2021). They share a denominator; the corrected figure stands.

### Coverage gaps, and which are real

Several datasets do not cover all 15 countries. Most of that is correct by
design and is recorded here so it is never mistaken for a defect:

| Dataset | Coverage | Reading |
|---|---|---|
| `ef_epi` | 10/15 | **Correct.** AU, CA, GB, IE and US are absent because the EF English Proficiency Index measures English as a *foreign* language. A score for them would be meaningless. |
| `eurostat_total_employment` | 9/15 | **Correct.** Eurostat covers the EU/EEA; AE, AU, CA, QA, US are out of scope and GB left after Brexit. |
| `oecd_indicators`, `oecd_economic_outlook`, `wikipedia_english_speakers` | 13/15 | **Correct.** AE and QA are not OECD members. |
| `mipex` | 9/15 | **Correct.** MIPEX publishes a fixed country set; AE, AU, GB, NO, QA and US are not in it. |
| `wipo_gii` | 13/15 | **A real gap, already disclosed, now diagnosed.** US and NL are in the Global Innovation Index but missing here. The cause is visible in the stored `source_line`: the source PDF prints *two countries per line* ("23 Australia 48.1 22 6 90 Cabo Verde 22.3 13 4") and the extractor reads only the first. Not fixed — there is no cached raw and re-fetching a PDF for two index values is out of proportion — but it is an extraction bug, not an absence in the source. |
| `climate_normals` | 21/73 cities | Partial by construction; the fetch is rate-limited and was never completed. |
| `bls_oews`, `indeed_hiring_lab_job_postings` | 30/73 cities | **Correct.** Both are US-only sources. |
| `levels_fyi` | 63/73 cities | Ten cities hold too few self-reports to publish a band; each records its own `unavailable_reason`. |

### Vintage

Two datasets are *forecasts*, not stale data: `un_wpp` runs to 2100 and
`oecd_economic_outlook` to 2027. The repo already separates forecast from
observation (`validate_data.py`'s own forecast check) and this sweep confirms
nothing else projects past its generation year. Everything else sits within two
years of when it was generated.
