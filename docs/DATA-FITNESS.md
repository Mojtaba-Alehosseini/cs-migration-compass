# Data fitness for purpose

_Package 15. For every claim the site makes on screen: what the evidence actually supports, at what
precision, and — where it falls short — the corrected form._

This is not a validation report. `make validate` and `make audit` already answer "is this value
legal?". This answers a different question: **is the data fit for the claim the page makes on it?**
A number can pass every invariant in the repo and still be summarised with the wrong estimator,
published to a precision its sample cannot carry, or labelled as something it is not.

Method, evidence and p-values: `REPORT-P15.md`. Machine-readable findings:
`data/quality_history/statistical_audit.json`, `profile.json`, `title_classifier_eval.json`,
`dedupe_eval.json`, `postings_pay_rederived.json`.

**Two rules governed every change made under this package.** No published value was altered —
every correction is to a method, a summary, a disclosure or a boundary. And no check is reported
clean unless it has been observed to fail on a constructed violation; each harness ships a
`--self-test` that does exactly that.

---

## Summary

| Claim | Verdict | Supported precision |
|---|---|---|
| Median advertised pay by country (`/postings`) | **Not supported as labelled** | 1 country, not 7; nearest $1,000 |
| Years to own a home (city cards, `/compare`) | **Supported, but not to one decimal** | A range, not a point |
| City salary bands (new-grad / mid / senior) | Supported | Nearest $1,000 |
| Wage distribution panel (`/explore/money`) | Supported | As published — already median-based |
| Canadian house-price trend (Teranet) | **Multi-year direction only** | No single value, monthly *or* annual |
| Cost-of-living and rent inputs | Supported | As published |
| "N postings, M companies" counts | Posting count includes re-listings (~6%); **company count sound** | Distinct roles vs raw rows |
| Cross-source salary agreement | Supported as *correlation*, not as *agreement* | Never blended |

---

## 1. "Median advertised pay by country" — not supported as labelled

**What the page says.** A dotted-line chart on `/postings`, captioned *"Annual-salary postings only
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
2. **The sample is far too small in six of seven countries.** Singapore's published figure rests on
   **five** postings whose 95% bootstrap interval runs **$60,177 - $317,412** - a half-width of
   84%, from five values spanning 5.3x. After de-duplicating and restricting to software titles,
   exactly **one** of the seven (the US, n = 1,117) clears a 30-posting floor; the other six fall
   to between 0 and 13 postings.
3. **The published precision is manufactured.** Employer-entered pay is heaped to round thousands
   (77.5% of native annual minima end in 0 or 5; 65% end in 000; terminal-digit uniformity rejected
   at p < 0.001). FX conversion then turns a round native figure into `$152,969.52`. The decimals
   were never in the source.

**Re-derived on the clean subset** — de-duplicated, then restricted to titles the classifier ships
as software — the US median moves **$82,994 → $98,688, +18.9%**. That delta is the size of the
error being published. Canada moves +13.2%; Great Britain does not move.

**Corrected form.** The chart supports **one country (the US), rounded to the nearest $1,000, with
its interval shown** — not seven countries to the cent:

> Median advertised pay, software roles only - United States: **$99,000** (95% CI
> $95,000-$101,000, n = 1,117 postings after de-duplication).

Everything else is below the sample size any median needs. **This requires a product decision** —
whether to show one country, or to show all seven with intervals and an explicit "indicative only"
label — and is recorded in `NEEDS-DECISION.md`.

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
annual series does, against a true trend of only **3.1-4.1% per year**. The annual residual
autocorrelation stays at 0.39-0.42, nowhere near a real index. Averaging cuts the noise by root-12
and it is still larger than the signal it is meant to reveal.

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
removes **2,884 rows (5.98%)**.

Those 120 pairs are **stratified** - 24 from each of five cosine bands, so the threshold is tuned
where the decision is hard - which means 0.958/0.719 describe that deliberately hard sample, not the
population. Reweighted by each band's population share, precision is unchanged at **0.958** (every
true and false positive falls in the top band) but recall drops to **0.678**, because the misses sit
in bands the sample over-represents. **0.678 is the figure to quote for real behaviour;** 0.719 is
the figure the threshold was selected on.

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
