# External data audit — CS Migration Compass

Independent review of all 52 processed datasets, 21 August 2026. Method: structural inspection,
distributional analysis, external benchmarking against OECD average wages, and outlier detection.
No repo code was modified; every figure below is reproducible from committed data.

**Verdict: the pipeline is sound. The published cross-country wage comparison is not.** Four findings
are material, one is severe, and the severe one is not a bug in any single line of code — it is a
measurement-validity problem that no unit test would catch.

---

## Finding 1 — SEVERE. The cross-country wage comparison is not measuring software developers

Software occupations earn a well-documented premium over the national average wage — typically
**1.2–1.8×** in OECD economies, higher in the US. Benchmarking the site's own published USD medians
against OECD `avg_wages` (2025, same year, same source family the site already ingests):

| Country | Site USD median | OECD avg wage | Ratio | Occupation depth | Bonuses included? |
| --- | ---: | ---: | ---: | :---: | :---: |
| **US** | 135,980 | 86,977 | **1.56** | 4-digit | partial |
| AU | 87,608 | 72,018 | 1.22 | 6-digit | yes |
| DK | 94,053 | 78,090 | 1.20 | 4-digit | yes |
| NO | 87,150 | 73,462 | 1.19 | 4-digit | yes |
| GB | 73,191 | 66,299 | 1.10 | 4-digit | yes |
| **SE** | 65,372 | 61,443 | **1.06** | 4-digit | **no** |
| **FI** | 66,242 | 63,053 | **1.05** | 4-digit | **no** |
| **DE** | 79,338 | 76,285 | **1.04** | **2-digit** | no (−0030) |
| **IE** | 67,743 | 70,113 | **0.97** | **1-digit** | no |
| **NL** | 76,584 | 80,136 | **0.96** | **no ISCO map** | **no (−16%)** |
| **ES** | 42,514 | 57,779 | **0.74** | **2-digit** | yes |

**The site currently states that a Spanish software developer earns 26% less than the average Spanish
worker, and that Dutch and Irish developers earn less than their national averages.** Those claims
are not credible.

### The two-factor explanation, and why it is not a coding error

The residuals are not random. They sort cleanly on two axes the pipeline already records:

- **Occupation breadth.** Every country at depth 1–2 sits at or below 1.04. Ireland's source is ISCO
  major group 2 — *all professionals*, doctors and lawyers included. Germany's is a 2-digit KldB
  group. Spain's is a CNO-11 subgroup. These are not software; they are broad professional averages,
  which by construction sit near the national mean.
- **Pay composition.** Sweden and Finland are 4-digit and still land at 1.05–1.06 — both explicitly
  *exclude* bonuses and 13th-month pay. The Netherlands excludes *bijzondere beloningen* entirely,
  documented at ~16% of pay.

Countries that are **both** 4-digit **and** bonus-inclusive — US, AU, DK, NO, GB — all land in
1.10–1.56, which is the plausible band. **Every country outside that band fails on at least one of
the two axes.** The pipeline's own metadata predicts its own errors.

### Why the existing safeguards did not catch it

`crosswalk.compare()` and `comparison_basis()` enforce meet-in-the-middle **pairwise**. The wage panel
plots all countries in one chart, where no pair is ever evaluated — so a 1-digit Irish figure renders
beside a 4-digit Swedish one with no degradation applied. The rule is correct; it simply never fires
in the many-country view.

---

## Finding 2 — HIGH. Sixteen years of vintage are being compared as if contemporaneous

Reference years across the fifteen countries span **2009 to 2025**:

`AE 2009 · ES 2018 · IE 2022 · QA 2023 · DK/FI/AU/NL/CA 2024 · SE/GB/US/NO/DE 2025`

Excluding the UAE, the live spread is still **2018–2025**. Nominal pay in these economies rose
roughly 20–30% over that window. Spain's 2018 figure is therefore understated against Sweden's 2025
figure by an amount comparable to the gap the chart is trying to show — **the vintage gap is the same
order of magnitude as the signal.**

No deflator is applied, and no year is displayed on the comparison chart.

---

## Finding 3 — HIGH. The postings dataset is stale, shrinking, and unconvertible

**Stale merge.** `postings.json` was generated 17 August. The provider files beneath it are newer:
Greenhouse (21 Aug) holds 13,466 postings, Lever (21 Aug) holds 9,928 — but the merged file still
carries the 17 August figures of 5,172 and 3,055. **The site is serving ~15,000 fewer postings than
the repo already has on disk.** `build_postings.py` is not being re-run after the harvesters.

**Destructive refresh.** Verified companies fell 1,419 → 606 (−57%) and postings 43,034 → 19,463
(−55%) at the 17 August scheduled run. The seed list is recomputed per run rather than accumulated,
so any truncated or rate-limited run permanently discards previously verified boards. Left alone it
will keep shrinking.

**Mixed currencies, no FX.** Compensation spans USD, EUR, GBP, CAD, SGD, JPY, KHR, INR, AMD with **no
conversion layer** — `normalise.py` is not applied to postings. Any cross-country aggregate over this
field is currently meaningless. The site's own year-matched FX table exists and is unused here.

**64 records carry a parse error.** A dropped thousands-suffix produces entries such as
`OTE $250 – $300 /year` for an Enterprise Account Executive (plainly $250k–$300k) and
`SGD 250 – SGD 400 /year`. All 64 annualise below $12,000. Separately, 7 legitimate high-value
records (JPY 18M, KHR 123M, INR 15L) are correct in local currency but would become extreme outliers
the moment any conversion is applied without validation.

---

## Finding 4 — MEDIUM. The quality report overclaims, and the drift detector is blind

`docs/DATA-QUALITY.md` reports **"Overall: PASSING"** while one of its four modules shows
`COULD NOT RUN` — `TypeError: main() got an unexpected keyword argument 'append'` in
`generate_data_quality_doc.py`. A report that claims health it has not verified is the precise
failure mode the audit package was built to prevent.

The drift detector reports *"no material drift"* while sitting on a dataset that lost 55% of its
records — because its baseline was captured **after** the loss. A first baseline taken at an unknown
point in a degradation is not a baseline.

---

## What is sound

Worth stating plainly, because most of this pipeline is in good order:

- **Percentile monotonicity holds** in every distribution that publishes percentiles. No inversions.
- **Dispersion ratios are plausible** where measurable: SE 1.83, FI 2.02, US 2.60, ES 3.27, GB 3.29 —
  all inside the expected 1.6–4.0 band for national ICT pay, and the ranking (compressed Nordics,
  dispersed Anglophone markets) matches the labour-economics literature.
- **The US figure is exactly right** — $135,980 reproduces BLS OEWS SOC 15-1252 to the dollar.
- **Provenance is genuinely complete.** 52 datasets, 49 with data, 3 recorded as blocked or
  unavailable with reasons. Licences recorded per source. This is better than most published
  research data.
- **Structural integrity checks pass** — no negative pay, no zero-as-figure, no seniority mislabelling,
  ODbL isolation intact, survey and advertised pay structurally separated.

---

## Recommended corrections, in priority order

1. **Stop ranking countries that do not measure the same occupation.** Either restrict the
   cross-country chart to the depth-4, bonus-inclusive set (US, AU, DK, NO, GB — and SE/FI/CA on the
   regular-pay basis), or apply the meet-in-the-middle rule to the *whole set* rather than pairwise,
   degrading every country to the deepest depth all displayed countries share.
2. **Add the benchmark ratio as a standing invariant.** Any country whose published median falls
   below 1.0× or above 2.5× its own OECD average wage should fail the audit. This single check would
   have caught Finding 1 on the day it shipped, and it costs ten lines.
3. **Show the reference year on every figure**, and refuse to draw two countries more than three
   years apart on the same axis without saying so.
4. **Re-run `build_postings.py`** and make the harvest additive — union new verified companies with
   the existing seed list rather than replacing it.
5. **Route postings compensation through `normalise.py`** so currency and period are handled by the
   same year-matched machinery as the wage spine.
6. **Fix the thousands-suffix parser** and add an annualised-plausibility gate at ingest.
7. **Fix `generate_data_quality_doc.py`**, and make overall status **FAIL** when any module cannot run.
8. **Reset the drift baseline** from a verified-good state, not from the current degraded one.
