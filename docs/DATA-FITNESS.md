# Data fitness for purpose

_Packages 15, 16, 19 and 20. For every claim the site makes on screen: what the evidence actually
supports, at what precision, and — where it falls short — the corrected form. Package 15 measured;
package 16 applied the corrections and swept the datasets package 15 never reached (§10); package 19
fixed the PDF extraction defect §10 had already found in `wipo_gii` and swept every other document-
or web-page-derived source for the same class of failure (§11); package 20 found `wipo_gii` did not
need PDF parsing at all and moved it to WIPO's own CSV (§11)._

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
| Canadian house-price trend (Teranet) | **Raw: multi-year direction only.** Smoothed + OECD-validated trend now published alongside it | Raw: no single value, monthly or annual. Smoothed: a monthly trend with its own 95% band — see §5's package-21 update |
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

**Update, package 21 — the window narrowed from three years to two (NEEDS-DECISION #48), Puerto
Rico moved off the US population (#47); the US figure held.** `PUBLISH_FROM_YEAR` moved 2024→2025.
Re-derived directly, not assumed:

> Median advertised pay, software roles only — United States: **$205,000** (95% CI
> $202,000-$210,000, n = 1,783 distinct software roles posted 2025 or later).
> 2025: 212 · 2026: 1,571 — 88.1% from the most recent year, and 91% from a single provider.

The US and GB medians held exactly steady across both changes; Canada moved $118,000→$119,000
(+0.8%). No country crossed the 30-posting publish floor in either direction from the narrower
window. *(Adversarial review found this doc's own worked example above — the n=1,807/"2024 or
later" figures — had gone stale after package 21's own commit changed the window without touching
the paragraph that names it. Left as history, corrected here rather than silently edited in place.)*

Route correction: `/postings` now redirects to `/openings` (the browsable list), not `/work` —
package 21, NEEDS-DECISION #50. `/work` is still where this panel itself renders.

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

**Update, package 21 — the trend is recoverable for four of six cities, and NEEDS-DECISION #43 is
closed on that basis.** The finding above is about the RAW series and stands unchanged: no raw
monthly or annual Teranet value is interpretable on its own. What it does not settle is whether a
properly-noise-modelled trend can be recovered from it. Two things pointed toward yes: the
month-over-month autocorrelation column above (-0.40 to -0.47) sits close to the theoretical **-0.5**
signature of a smooth trend plus independent additive noise once differenced — exactly the noise
model this section already diagnoses, not a different one assumed for convenience.

`scripts/derive_teranet_smoothed.py` fits that model directly: a state-space local linear trend
(Kalman smoother, `statsmodels.tsa.UnobservedComponents`), with the observation and innovation
variances estimated from the data by MLE, never assumed. Recovering a signal this way is only as
good as its validation, so each city's smoothed trend is checked against an INDEPENDENT source —
OECD's own Canadian house-price index — before it is trusted:

- **Levels-correlation was tried first, and rejected by direct adversarial testing.** Correlating
  the smoothed monthly level (aggregated to quarters) against OECD's level scored 0.90-0.99 for all
  six cities — but substituting PURE NOISE for a city's own raw series and smoothing it the same
  way still scored 0.9+ against the same OECD series for 5 of 6 cities, one landing positive (would
  have "passed"). Two series that each drift slowly correlate at the level whether or not the drift
  shares a cause — the textbook spurious-regression problem — so this was never a safe test.
- **The real check: quarter-over-quarter CHANGES, not levels, plus a Monte Carlo null.** Differencing
  removes the shared trend structure; a city passes only if its differenced correlation against
  OECD's own differenced series clears a null test (pure noise, matched to that city's own fitted
  scale, run through the identical smoothing-and-validation pipeline against the SAME real OECD
  series) at p<0.05.
- **The null itself went through two rounds of adversarial correction before being trusted.** A
  first version fit the model to i.i.d. noise per draw — MLE-fitting a local-linear-trend model to
  pure noise drives its own level and trend innovation variances toward zero, collapsing the "null"
  to a near-deterministic line with almost no real variability, too weak to mean anything. The fix —
  a parametric bootstrap from each city's OWN fitted noise variances — carried a second,
  independently-found defect: simulating from an unanchored starting state let the model's double
  integration (a local linear trend's slope is itself a random walk) explode over the full monthly
  history, producing synthetic series reaching the hundreds of thousands against a real index that
  runs 80-430, which made the null artificially easy to beat. Anchoring every simulated draw to the
  real fit's own starting level and slope fixed both defects — verified directly, not just argued:
  it changed Montreal's own verdict from a pass to a fail, which is why the numbers below differ
  from an earlier draft of this section.

| City | Differenced corr. vs OECD | Monte Carlo p-value | Trend (smoothed) | Signal share of raw MoM variance | Result |
|---|---:|---:|---:|---:|---|
| Toronto | 0.481 | 0.002 | +4.9%/yr | 0.069% | Recovered |
| Vancouver | 0.391 | 0.002 | +4.4%/yr | 0.179% | Recovered |
| Halifax | 0.226 | 0.014 | +3.4%/yr | 0.070% | Recovered |
| Ottawa | 0.227 | 0.022 | +4.1%/yr | 0.033% | Recovered |
| Calgary | 0.151 | 0.110 | — | 0.101% | Raw only — did not clear p<0.05 |
| Montreal | 0.118 | 0.126 | — | 0.047% | Raw only — did not clear p<0.05 |

(500 draws resolved every city cleanly this run — none landed close enough to the 5% line to need
the 5,000-draw refinement pass the pipeline carries for exactly that case.)

**Four of six cities pass; Calgary and Montreal do not, and stay on raw-only disclosure — the
fallback path NEEDS-DECISION #43 always intended, not a hypothetical that happened to go unused.**
The recovered trend range for the four that pass (3.4-4.9%/yr) sits close to, though not identical
to, this section's own CAGR-superseding log-linear estimate (3.1-4.9%/yr, computed across all six
cities from ANNUAL MEANS of the raw series) — a different reduction of different input than the
monthly Kalman smoother, so rough agreement is corroborating, not circular.

**What still holds, and what changed.** The signal share column is the honest headline: even the
strongest of the four validated cities (Vancouver) recovers only 0.18% of month-to-month raw
VARIANCE as genuine trend — the smoothed line's own 95% band is wide, because the noise really is
that large. This is not a reversal of the finding above; it is the same noise, with a model fit to
it and validated independently rather than left undiagnosed. The site publishes the smoothed trend
with its own uncertainty band for the four cities that clear validation
(`site/src/components/explore/Housing.tsx`'s `TeranetPanel`, `/explore/housing`), labelled as
smoothed; Calgary and Montreal render instead in `CityRibbons` further down the same page, raw only,
with a note explaining why — never silently dropped from the site. Raw values for every city remain
available via CSV regardless of validation outcome; `data/processed/teranet_national_bank_hpi.json`
is read by the derivation script, never written to. `NEEDS-DECISION.md` #43 is closed: option (a),
keep a multi-year direction with a chart-level note, is superseded — for the four cities that clear
validation — by a stronger, still-honest option this package's own validation work made available: a
monthly trend with its own uncertainty, not just a qualitative direction. For Calgary and Montreal,
option (a) is exactly what still applies.

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
| `wipo_gii` | 15/15 (was 13/15) | **Fixed, package 19.** US and NL were in the Global Innovation Index but missing here because the extractor flattened the PDF's page to text, which interleaves side-by-side columns onto one line ("23 Australia 48.1 22 6 90 Cabo Verde 22.3 13 4") and reads only the first country on it. Re-extracted from the PDF's own word geometry instead of flattened text (`pdf_table.py`); every one of the publication's 139 rows is now parsed and self-checked against the publisher's own row count, range and rank sequence. See `REPORT-P19.md`. |
| `climate_normals` | 21/73 cities | Partial by construction; the fetch is rate-limited and was never completed. |
| `bls_oews`, `indeed_hiring_lab_job_postings` | 30/73 cities | **Correct.** Both are US-only sources. |
| `levels_fyi` | 63/73 cities | Ten cities hold too few self-reports to publish a band; each records its own `unavailable_reason`. |

### Vintage

Two datasets are *forecasts*, not stale data: `un_wpp` runs to 2100 and
`oecd_economic_outlook` to 2027. The repo already separates forecast from
observation (`validate_data.py`'s own forecast check) and this sweep confirms
nothing else projects past its generation year. Everything else sits within two
years of when it was generated.

---

## 11. Document- and web-page-derived sources — extraction method and failure mode

Package 19. Most other sources in this pipeline read a stable, structured format — a JSON or CSV API
keyed by field name, robust to the publisher reordering columns. Four sources instead read a PDF's
visual layout, an HTML page's rendered structure, or (one case) a human's own reading of a page —
which makes them fragile in a way nothing else here is: the extractor can keep running, keep
returning HTTP 200, and still silently misread what changed. This section states each one's method,
its specific failure mode, and what protects against it today.

**`wipo_gii` graduated out of the LAYOUT-fragile part of this category in package 20, but not out of
"could keep returning HTTP 200 and silently misread what changed" entirely.** It was a PDF
column-table layout parse through package 19; package 20 found that `wipo.int/gii-ranking/en/`
itself loads its ranking table from a plain CSV endpoint and switched to it (`src_wipo_gii.py`) — no
layout parsing, no name matching, keyed on `iso3`. That part of this section's opening sentence no
longer applies to it. What still could: the URL is year-stamped
(`bc_results_gii_2025.csv`) with no guarantee WIPO retires it when a newer edition ships — an
adversarial review found an earlier draft of this package asserted a stale URL would "almost
certainly" 404, reasoning by analogy from the PDF path's own dead 2024 URL, without establishing
that a static CSV asset behaves the same way. It probably does not: publishers commonly leave prior
years' data files in place rather than deleting them, which would make this URL silently keep
serving 2025 data forever with no error of any kind. Mitigated, not eliminated: `src_wipo_gii.py`
now probes whether a next-year URL already exists and flags loudly if so — see its own subsection
below and `REPORT-P20.md` Gate 11.

**This list was built by scanning `scripts/src_*.py` for `pdfplumber`/`bs4` imports, and that
screen has a blind spot, found by this package's own adversarial review (see `REPORT-P19.md` Gate
8/11): `scripts/src_worldbank_gep.py` imports neither library, so it never matched the scan, but it
scrapes a download link off the World Bank GEP landing page with a bare regex over fetched HTML
(`re.findall(r'href="([^"]+\.(?:xlsx|xls|csv))"', html, ...)`). It is layout-dependent in the same
family as the five below, narrower in consequence: a layout change breaks the *fetch* (no file
found, loud) rather than silently returning a wrong data value, which is why it is named here rather
than folded into the table — the property this section exists to establish (a loud failure, not a
silent one) already holds for it without a new check.

### `ef_epi` — PDF column-table layout (fixed package 19; still the extraction path)

Covered in full in `REPORT-P19.md` §0 and `REPORT-P20.md`. `page.extract_text()` flattened
side-by-side PDF columns onto one interleaved line, gluing EF EPI's Germany rank onto the country
name with no space to split on ("04Germany"). Rewritten to parse word geometry (`pdf_table.py`) and
to extract the FULL published table (123 rows) so it validates itself against the publisher's own
row count, range and rank sequence — see `audit_data.py`'s `check_full_table_self_consistency()`.
Package 20 (Tier 2) checked `ef.com/wwen/epi/` for the same CSV-endpoint escape hatch that moved
`wipo_gii` off this pattern and found none — the page's own SSR payload carries no ranking data, no
network request fetches it (a "Load more" click reveals more rows with zero new requests, so
whatever holds the full dataset client-side is not a discoverable public endpoint), and no loaded JS
chunk contains it either. `pdf_table.py` and this extraction path stay; see `src_ef_epi.py`'s own
docstring for exactly what was checked, so a future package does not have to redo it.

### `wipo_gii` — a CSV now, no longer layout-fragile, but still edition-pinned (package 20)

No longer belongs in this section's LAYOUT-extraction category. `wipo.int/gii-ranking/en/`'s own
Nuxt front end loads its table from `wipo.int/gii-ranking/data/bc_results_gii_2025.csv` — a plain,
unattended-fetchable file keyed on `iso3`, no layout parsing, no free-text name matching. Two real
parsing gotchas, both found and both handled: the CSV formats decimals with a comma (`"65,96195221"`,
handled explicitly rather than via a bare `float()` cast, checked adversarially against ~30
constructed inputs), and two economy names — Türkiye and Côte d'Ivoire — arrive double-UTF-8-encoded
in WIPO's own published bytes (`_fix_double_utf8()`, found only because an adversarial review
checked all 139 rows rather than the 15 this site tracks, all of which happen to be ASCII-only
names).

**What is not fixed, only made visible.** The URL is year-stamped with no evidence WIPO retires a
prior year's file — a static CSV going stale by simply sitting unchanged is the more likely
publisher behaviour than the dead-URL pattern the PDF path showed, not the same thing. Two
safeguards, neither a full fix: the `giiyr` column's full breakdown is always recorded in
`meta.edition_counts` (not just a pass/fail against the majority, so a growing minority of
non-conforming rows is visible before it ever flips the majority verdict — one economy, Venezuela,
already carries `giiyr="NA"` in a genuinely current file, which is why this is majority-based rather
than strict); and a lightweight probe checks whether `bc_results_gii_2026.csv` already exists and
flags loudly (`meta.newer_edition_available`) if so. Neither can catch WIPO quietly revising this
*same* year's file's content without changing `giiyr`, and the probe depends on next year's file
following the same naming pattern. `EDITION_YEAR` still needs a human to update when a new edition
ships, exactly as the PDF's own `page_index`/`published_total` constants did in package 19.

### `numbeo_history` — live HTML table scrape (made self-checking this package)

**Method.** BeautifulSoup selects Numbeo's country cost-of-living ranking table (`id` matching
`t2`/`rankings`, or `class="stripe"` as a fallback) from `rankings_by_country.jsp?title=<year>`,
reads column headers from `<thead>`, and matches each `<tbody>` row's first three cells against our
15 ISO2 codes.

**Failure mode.** Two distinct ways a layout change breaks this silently: the selector stops
matching the real table at all (previously returned an empty dict with no warning — indistinguishable
from "no data this year"); or the selector matches something, but a redesign shrinks or restructures
the table (a "top 5" widget, a partial paywalled table, a split-by-region layout) — every row still
"successfully" parses, just from the wrong table.

**What protects against it now.** `country_year()` reports the table's TOTAL row count, not just
rows matching our 15 countries. Numbeo's country ranking has covered 130+ countries for years
(115-155 across the 12 years this pipeline actually fetched, checked while writing this); a table
that still matches the selector but returns fewer than 50 rows is recorded in `table_shape_warnings`
even in a year where every one of our countries still happens to resolve. This is the Tier 2
principle applied in the coarser form the source allows: Numbeo does not publish a fixed country
count to check an exact row count against the way WIPO and EF do, so the check is a plausibility
floor on the table's own shape rather than an exact match. See
`scripts/tests/test_package19_numbeo_shape_check.py` for the constructed-violation proof (a
shrunken table is flagged; a normal one is not).

**What a failure would look like today.** A `!! country <year>: table selector matched but only N
row(s) found` log line, `table_shape_warnings` non-empty in `data/processed/numbeo_history.json`'s
`meta`, and — per source — fewer countries resolved that year. Visible, not silent.

**Not covered, named rather than fixed.** The header-to-value mapping is still positional
(`headers[i]` paired with `cells[i]`) — a column that changes MEANING without changing its header
text would not be caught by any check here or anywhere else in this pipeline. There is no
independent second source for this table to check the mapping against.

### `wikipedia_english_speakers` — live HTML table scrape (not self-checkable; named plainly)

**Method.** BeautifulSoup scans every `table.wikitable` on one Wikipedia article whose header
mentions "english", takes the first cell as the country name, and takes the first percentage or
first large integer found anywhere else in the row.

**Failure mode.** The "first number in the row" heuristic is the same shape of bug this whole
package was written to fix in the PDFs: if the article gains a new leading column (e.g. a
population column ahead of the percentage column), or a second, unrelated table also matches the
"mentions english" filter, a value from the wrong column or the wrong table would be read as this
country's figure — with no exception and no output that looks obviously wrong, just a plausible
number that is not the right one.

**Why this is not made self-checking.** Tier 2's principle needs a publisher-stated total to check
the extracted row count against. This page is a single snapshot with no analogous headline figure —
there is no "N countries" to validate a count against, and the underlying numbers are already
mixed-vintage national censuses the article itself never reconciles into one table with a stated
total. The existing `snapshot_only` flag and vintage caveat are the honest handling already in
place; this package adds no new check here because nothing about the source is shaped like the PDF
tables' self-validating structure. Said plainly rather than forcing a check that would not mean
anything: this is the work order's own explicit case for naming a weakness instead of manufacturing
a fix for it.

**What a failure would look like.** A plausible but wrong percentage or count for one or more
countries, undetectable by this pipeline's existing checks unless the value happens to also fail
`audit_data.py`'s general magnitude-plausibility band. Spot-checking against the live article is the
only real defence today.

### `levels_fyi` — not live-scraped; a one-time human capture, a different fragility entirely

**Method.** levels.fyi's metro pages are JavaScript-rendered, so nothing in this pipeline fetches
them automatically. A human read the site in a real browser and saved the values verbatim into
`data/raw/levels_fyi/capture_2026-08-04.json`, which is committed to the repo as an explicit
exception to the "`data/raw/` is a disposable cache" rule (see `.gitignore`'s own comment on that
exception). `src_levels_fyi.py` only does the deterministic part — FX conversion and reshaping into
`cities.json` — against that static file.

**Failure mode.** Not a layout-change risk at all, since there is no live parse left to break. The
real risk is staleness with no automatic re-fetch: the capture is a snapshot from one date, and if
levels.fyi's published bands move, nothing in this pipeline notices until a human re-captures by
hand. This is a fundamentally different failure mode from the three sources above and should not be
described the same way.

**What protects against it now.** `audit_data.py`'s `check_refresh_intervals()` already checks every
`data/provenance.json` entry, including this one, against an expected refresh interval generically —
this is not a new gap Tier 4 needs to close, just one worth naming so "not scraped" is not mistaken
for "cannot go stale".

**What a failure would look like.** No error, no warning from any layout check — `check_refresh_
intervals()` flagging the entry as past its expected interval is the only signal that would ever
fire.

### Summary

| Source | Method | Self-checkable (Tier 2 principle)? | Status after package 20 |
|---|---|---|---|
| `wipo_gii` | **CSV, keyed on iso3** (was PDF column-table layout through package 19) | Yes — full 139-row table validated against the publisher's own count, range and rank sequence; same check, now format-agnostic | **No longer layout-fragile (package 20); a different risk remains — a year-pinned URL with no confirmed retirement behaviour — mitigated by a next-edition probe, not eliminated** |
| `ef_epi` | PDF column-table layout | Yes — full 123-row table validated the same way | Fixed & self-checking (package 19); checked for a CSV escape hatch and found none (package 20) |
| `numbeo_history` | Live HTML table scrape | Partial — row-count floor; no exact published total exists to match | Made self-checking (coarse) |
| `wikipedia_english_speakers` | Live HTML table scrape | No — no publisher-stated total exists | Named plainly, not fixable this way |
| `levels_fyi` | One-time human browser capture | N/A — not a live parse | Staleness already covered generically; not a layout risk |
