# Regression catalogue

Package 13, Tier 0. Every data or arithmetic defect found across packages 6–12's own
adversarial reviews (pure UI/copy findings are excluded — those are covered by the
Lighthouse/theme/keyboard gates each package already ran, not by this catalogue). For
each: what was wrong, what correct behaviour is, whether it's testable, and where its
test lives.

Two kinds of test, by where the bug lives:

- **Pipeline bugs** (`scripts/*.py`) — real Python tests in `scripts/tests/test_*.py`,
  importing and calling the actual functions. No reimplementation.
- **Client bugs** (`site/src/**/*.ts(x)`) — `profile.ts`'s own top-level import chain
  reaches `store.ts`, which reads `import.meta.env.BASE_URL` — a Vite-injected global
  that does not exist under plain Node, confirmed by trying the direct import first
  (`ERR_MODULE_NOT_FOUND` on the extensionless specifier, then `TypeError` on
  `import.meta.env` once a custom resolver hook fixed the extension problem). Rather
  than mock Vite's own runtime piecemeal — a whack-a-mole with no natural stopping
  point — these are tested the same way every prior package's own gates already
  verify UI behaviour: real headless Chrome via `.status/evidence/cdp.mjs`, against a
  real built-and-served site, reading the actual rendered numbers. Slower than a unit
  test, but it exercises the exact chain a reader experiences (data load, computation,
  render) rather than an isolated function — and it is zero new dependencies, zero
  production-code changes made only to satisfy a test harness. Tests live in
  `scripts/tests/test_ui_regressions.mjs`, run against a `vite preview` server the
  suite's own runner starts and stops.

`scripts/tests/run_all.py` runs both kinds and reports one pass/fail.

---

## Package 6 — chart integrity

### R1. Years-to-home reported past its own denominator's precision (Milan, Valencia)

**Wrong:** `savings_usd_year = net − 12×(rent+living costs)` is a difference of two
numbers each published to a $10/month step (±$240/year combined). Milan's own savings
landed at $210/year — smaller than its own inputs' rounding — and `years_to_home =
90×price/savings` turned that into 2,314 "years", a number with no more real precision
than the noise in its own denominator.

**Correct:** `yearsToHomeStability()` (`compute.ts`) perturbs rent and living costs by
one published step each and flags a result as unstable if it moves >25% or flips to
"never affordable". Milan and Valencia flag; all other 70 (of 72) cities with a value
do not, worst stable movement 11.0% (Rome) — nothing sits near the 25% line, so the
threshold isn't doing delicate work, the inputs' own rounding is. A flagged value is
kept and marked, never suppressed or silently dropped from a chart's own domain.

**Test:** `test_ui_regressions.mjs` — loads Milan's own city profile, confirms the
years-to-home figure carries the instability mark (`≈` / `.unstable-mark`) and that the
same figure is excluded from the Explore scatter's own y-domain (a stable city's exact
pixel position would shift if an unstable extreme were allowed back into the domain
computation).

### R2. Tick labels that collide

**Wrong:** `years_to_home`'s axis used a formatter that clamps ("100+ yrs"), so a
0–2,500 domain produced ticks `0.0 yrs, 100+ yrs, 100+ yrs, 100+ yrs, 100+ yrs, 100+
yrs` — six ticks, two distinct labels. Separately (caught at the same package's own
gate 10, not the original bug report): `moneyShort` bucketed to whole `$k` regardless of
the axis's own step size, so a $500-step axis rendered both 1,500 and 2,000 as "$2k";
`numericTick` had the identical fault at one decimal (0.88/0.90/0.92 → "0.9/0.9/0.9").

**Correct:** `assertInjectiveTicks()` (`engine.ts`) throws in development and logs once
in production whenever an axis's own tick set produces fewer distinct labels than
ticks. Every `tickFormat` now receives the axis step, since precision is a property of
spacing, not of the number alone.

**Test:** `test_ui_regressions.mjs` constructs the exact failing axis from the bug
report (`years()` over 0–2,500) via the real, shipped metric registry (reached from
the production bundle, not reimplemented) and confirms it really is non-injective —
six ticks, two distinct labels, `"100+ yrs"` repeating five times. Separately, it
reads the real, currently-shipped `years_to_home` axis as rendered (its own domain is
0–150, not 0–2,500) and confirms 7 ticks with 7 distinct labels, `0 yrs` … `150 yrs`,
never the clamped set. `assertInjectiveTicks()` only throws under `import.meta.env.DEV`
— against the production build this test runs, it `console.error`s once instead — so
the guard itself is exercised by putting the pre-fix formatter back on the live
metric object, forcing a real re-render, and reading that its logged message names
the repeated label and the true tick/label counts, before restoring it.

### R3. A domain set by an outlier

**Wrong:** `Math.min/max` over every value (including Milan's and Valencia's own
2,314/1,275-year outliers) set the Explore scatter's y-domain, the Compare chart
view's bar scale, and the Weights tool's own per-metric normalisation — putting the
other 70 real cities into the bottom 1.3% of the plot, crushing every bar against
Milan's, and letting one bad extreme silently rescale every other city's weighted
score.

**Correct:** every domain/scale computed from a savings-derived metric now excludes
`UNSTABLE_METRIC_KEYS` values (`stabilityOf()`-gated) before taking `min`/`max`.
Flagged cities draw in a labelled overflow band at the plot's own edge instead,
keeping their real number in the hover readout and the CSV export.

**Test:** `test_ui_regressions.mjs` — loads the Explore scatter on the
`years_to_home × apt_m2` preset, confirms 70 of 72 cities plot inside the main field
(not the overflow band) and that the computed y-domain's own upper bound is under
200 (not the ~2,314 an unguarded `Math.max` would produce).

---

## Package 9 — normalisation

### R4. FX rate not matched to the figure's own year

**Wrong:** converting a historical native-currency figure with a single, current-year
FX rate rather than that figure's own year's rate. Sweden 2023 median (51,000 SEK/mo),
converted at 2023's own rate (10.6102), is $4,806.71; converted at 2025's rate
(9.8207) instead, $5,193.11 — an 8.0% error that grows the further back the year runs.

**Correct:** `fx_rate(currency, year)` (`normalise.py`) has no nearby-year fallback —
an unmatched year is a hard failure, not a silent substitution.

**Test:** `test_normalise.py` — calls `to_usd()` for SE 2023 and 2024 and asserts the
result matches the year-matched hand computation exactly (not the wrong,
current-year-rate answer); calls `fx_rate()` for a year with no committed rate and
asserts it raises rather than returning the nearest year's own value.

### R5. Hours annualisation using the 2080-hour convention instead of sourced hours

**Wrong:** annualising an hourly figure via the generic 40h×52wk = 2,080 hours/year
convention instead of the country's own sourced, year-matched hours. Denmark 2024,
470.53 DKK/hour: sourced hours (38.4h/week) give 939,554.30 DKK/year; the 2080
convention gives 978,702.40 — 4.17% too high.

**Correct:** `annualise()` (`normalise.py`) requires a real, sourced hours record for
the figure's own country and year; there is no 2080-hour fallback path.

**Test:** `test_normalise.py` — calls `annualise('hour', 470.53, ...)` for Denmark 2024
and asserts the sourced-hours result (939,554.30), not the 2080-convention result
(978,702.40); confirms calling `annualise()` for an hourly figure with no matching
hours record raises rather than silently defaulting to 2,080.

### R6. `comparison_basis()` granting total_earnings without checking bonus status

**Wrong:** a source with `employer_social_contributions=False` (contributions already
excluded) was classified as expressing `total_earnings` without checking whether its
own `irregular_bonus` was also `True` — Sweden and Finland (bonus **excluded**, the
opposite of what `total_earnings` requires) were wrongly counted as total_earnings-
comparable.

**Correct:** `comparison_basis()` requires `irregular_bonus is True AND
employer_social_contributions is False` for `total_earnings`, not contribution-status
alone.

**Test:** `test_normalise.py` — asserts Sweden's own real `pay_composition.json` entry
has `irregular_bonus=False` (this test's own premise) and that `comparison_basis
('salary_se', 'salary_es')` is unconditionally refused (`comparable=False`), not
gated behind an `if result["comparable"]:` that never ran on any real pass — an
earlier version of this test did gate it that way, silently asserting nothing on
every run since `comparable` is False today; the adversarial review that caught it,
and this fix, are recorded in REPORT-P13.md. Two genuine POSITIVE controls, both
against real committed `pay_composition.json` entries, not constructed: Norway and
Spain (both `irregular_bonus=True, employer_social_contributions=False`) are
correctly granted `total_earnings`; Sweden and Finland (both flags `False`) are
correctly granted `regular_pay`. (Denmark, this entry's own earlier draft
mis-described as "bonus included, contributions excluded" — its real committed
entry has BOTH `True`, matching neither basis on its own; DK reaches `total_earnings`
only after Tier 1's own subtraction step, not from its raw composition flags.)

### R7. Ireland's hours annualisation using the generic cross-country lookup instead of its own sourced figure

**Wrong:** Ireland's own CSO-published hours were fetched but `annualise()` had no
parameter to prefer a source's own matched hours over the generic Eurostat lookup —
overstating Ireland's annual figure by a measured 21.4%.

**Correct:** `annualise()` gained `explicit_hours`/`explicit_hours_by_field`
parameters; Ireland is wired to use its own CSO figure.

**Test:** `test_normalise.py` — annualises Ireland's own committed hourly figure with
and without `explicit_hours` and confirms the two differ by the documented ~21.4%,
with the `explicit_hours` path matching the currently-shipped `wage_distribution.json`
value.

---

## Package 10 — position, estimate

### R8. A comparability check never consulted

**Wrong:** `computePosition()`/`computeEstimate()` never checked
`row.crosswalk.comparable` before computing a position — the Netherlands
(`comparable: false`, no ISCO-08 correspondence at any depth) still rendered a full,
confident position and estimate.

**Correct:** both functions check comparability first, via a shared `_notComparable()`
helper; NL renders its refusal reason with no `<Figure>`/`<Derived>` trigger at all.

**Test:** `test_ui_regressions.mjs` — loads `/position` with the Netherlands selected,
confirms no method-card trigger renders and the refusal text is present; confirms a
genuinely comparable country (e.g. Sweden) does render one.

### R9. `<Derived>`'s own displayed arithmetic not reproducible by hand

**Wrong:** a chain's own multiplier was rounded to three decimals for *display* but the
*result* was computed from the full-precision premium — "5,100 × 0.657 = 3,350.19" was
shown next to a result that isn't actually 5,100×0.657 (which is 3,350.70).

**Correct:** the premium is rounded once, before it's used for either display or the
arithmetic — whatever a card shows is what actually produced the number.

**Test:** `test_ui_regressions.mjs` — opens a personalised method card, parses the
displayed `A × B = C` string out of the DOM, and asserts `A × B` (recomputed
independently in the test) equals `C` to the cent, for at least two different profiles.

### R10. `?years=` empty string silently became 0, not the default

**Wrong:** `Number('') === 0` in JavaScript, not `NaN` — a present-but-empty `years`
query param was read as "0 years experience" instead of falling through to
`DEFAULT_YEARS`.

**Correct:** `profileFromParams()` explicitly checks `raw == null || raw === ''` before
parsing, rather than relying on `Number()`'s own coercion.

**Test:** `test_ui_regressions.mjs` — loads `/position?years=` (present, empty) and
confirms the resolved profile uses `DEFAULT_YEARS`, not 0.

### R11. Canada's two NOC-code rows silently filtered out everywhere

**Wrong:** `!r.country.includes('-')` — meant to exclude some other malformed key
shape — also excluded both of Canada's own real rows (`CA-21231`, `CA-21232`) from
the coverage map, the main position/estimate table, and the pay-vs-cost city lookup.

**Correct:** filtering keys on the ISO prefix where one row is needed; removing the
filter entirely where both Canada rows are meant to render.

**Test:** `test_ui_regressions.mjs` — loads `/position` with Canada selected and
confirms both `CA-21231` and `CA-21232` rows are present, not zero.

---

## Package 11 — the position must answer the question it asks

### R12. A premium computed against one central figure, applied to another (Sweden: mean vs. median)

**Wrong:** SCB's own `LonYrkeAlder4AN` (the age cross Sweden's gradient is built from)
publishes each band's own **mean** — confirmed equal to `dispersion_by_year`'s own
`mean_sek_month` for every committed year, never a median. The premium is therefore
mean-relative by construction. Applying it to the **median** instead (the pre-fix
behaviour) implicitly assumed mean and median move together across age bands, an
assumption never stated or checked — and systematically ranked every personalised
Swedish position about 6 percentile points too low. At 8 years: shifting the median
(53,500 × 0.895 = 47,882.5) ranks at **P31**; shifting the correct mean (55,500 ×
0.895 = 49,672.5) ranks at **P37** — the gap this finding named.

**Correct:** `premium_basis` (`"mean"` for SE, `"median"` for NO) selects which of a
country's own two figures `_centralFor()` shifts, read identically by
`computePosition()` and `_shiftEstimate()` so the two can never disagree about which
basis they're using.

**Test:** `test_ui_regressions.mjs` — loads `/position?years=8` for Sweden and asserts
the rendered position is **P37** (49,673 SEK/month), not P31 (47,883) — the exact
before/after pair this finding's own fix produced, hand-verified against
`wage_distribution.json`'s own committed percentile table in `REPORT-P11.md`.

### R13. A band anchored outside its own reachable range (Norway's youngest age band)

**Wrong:** Norway's youngest age-band anchor sat at 19.5 (the arithmetic midpoint of
SSB's own "0-39" band) — below `ASSUMED_CAREER_START_AGE`'s own minimum possible value
(22), so no real profile could ever land there. Every reachable age fell into the
"interpolate toward 40-54" branch instead of reading the band's own flat, real,
published value — a 17-year-experience profile (assumed age 39, genuinely still inside
"0-39") read **+6.99%** instead of SSB's own real **−8.31%** for that whole
population, a ~15-point swing.

**Correct:** the band's first point moved to 39 (its own real, published upper edge).
Every assumed age SSB itself calls "under 40" now reads that band's own flat value via
the clamp-low branch. A direct, observable consequence: 2 and 8 years of experience —
both well inside "0-39" — now read **identically**, since both clamp to the same real
band value; before the fix they read differently (interpolated toward the next band as
if age were a smooth curve SSB never published).

**Test:** `test_ui_regressions.mjs` — loads `/position` for Norway at `years=2` and
`years=8` and asserts the two rendered positions/estimates are byte-identical (the
regression signature the flat band produces); loads `years=17` and asserts the
personalised premium is negative (matching SSB's own real −8.31% figure), not the
positive +6.99% the pre-fix arithmetic produced.

---

## Package 12 — postings

### R14. Country resolved by unanchored substring match

**Wrong:** `country_from_location()` matched a country name as a bare substring of the
lowercased location text, with no word boundary — "Atlanta, **Georgia**" resolved to
the country Georgia; "Milwa**uk**ee" and "**Uk**raine" both resolved to the UK ("uk" is
a literal substring of both); "New **Mexico**" resolved to Mexico; "King of **Pr**ussia"
resolved to Russia (**"russia"** is a substring of p**russia**).

**Correct:** whole-word matching (`_word_match()`, using a not-preceded/followed-by-a-
letter check, since plain `\b` itself fails around punctuation like "u.s."), plus a
full US-state-names table checked before the ambiguous country-name table (Georgia the
US state and Georgia the country are the identical word — resolved to US as the
empirically correct default, since zero of 143 real "Georgia"-labelled postings in the
live dataset were Tbilisi).

**Test:** `test_country_resolution.py` — the exact five failing inputs from the finding
("Atlanta, Georgia", "Milwaukee, Wisconsin", "Ukraine", "Albuquerque, New Mexico",
"King of Prussia, PA"), asserting each now resolves correctly (US, US, UA, US, US) and
not to the old wrong answer (GE, GB, GB, MX, RU).

### R15. Pay period mislabelled from an assumed enum that didn't match the real API values

**Wrong:** Ashby's own `interval` field is `"1 HOUR"` / `"1 YEAR"` / `"1 MONTH"`, not
the assumed `"HOURLY"`/`"YEARLY"`/`"MONTHLY"` — every posting with compensation
silently defaulted to `"year"`, rendering `€200–250/yr` for a role Ashby's own
`tierSummary` field said was "per hour". Lever's own `interval`
(`"per-year-salary"`, `"per-hour-wage"`, ...) hit the identical shape of bug via a
`.replace('per-', '')` that produced strings matching nothing (`"year-salary"`).
Greenhouse's `pay_input_ranges` has no period field at all — the same company posted
both `$100,000-$125,000`-shaped and `$30.00-$35.00`-shaped ranges under the identical
"Salary Range" title.

**Correct:** Ashby/Lever match the real interval strings via substring containment on
the real enum values; Greenhouse infers hourly from magnitude (a range's own upper
bound under $1,000 — no real annual salary is that low, no real hourly wage is that
high), disclosed as an inference, not asserted as certain.

**Test:** `test_pay_period.py` — feeds each provider's real interval strings
(`"1 HOUR"`, `"per-hour-wage"`, a Greenhouse range shaped like `$30–$35`) through the
real mapping function and asserts `"hour"`, not the pre-fix default of `"year"`.

### R16. `$0` compensation rendered as a real figure

**Wrong:** Ashby's and Lever's own compensation guards used `is None` / `is not None`
— a real `0` value is not `None`, so a genuinely empty `$0`–`$0` range passed straight
through and rendered in bold as if an employer had stated it.

**Correct:** the guard rejects any non-positive minimum (`not c.get("minValue")`),
matching Greenhouse's and USAJOBS's own harvesters, which already guarded this way.

**Test:** `test_pay_period.py` — feeds a component shaped like Ashby's real
`{"minValue": 0, "maxValue": 0, "currencyCode": "USD", ...}` through the real
extraction function and asserts it returns no compensation, not a `$0`-`$0` figure.

### R17. Free-text compensation parser matched the wrong number, lost an HTML entity, and mis-applied a "k" suffix

**Wrong, three compounding bugs in `parse_compensation_text()`:** (a) matched the
FIRST number-dash-number pattern regardless of whether a currency marker was actually
bound to it — "hybrid, **2-3** days/week ... $160-170K CAD" parsed as min=2, max=3;
(b) `_strip_html()` missed the `&#x2F;` entity (an encoded forward slash), so
"$80–140/hr" arrived as "$80–140&#x2F;hr" and the `/hour` period regex could never
match; (c) English "$146-220k" shorthand (the `k` suffix applying to BOTH numbers) was
applied to only the second, parsing min=146 (not 146,000) — roughly 1/1000th of the
real minimum.

**Correct:** the range pattern requires a currency symbol or 3-letter code bound
directly to the matched numbers; `html.unescape()` replaces the hand-picked entity
list; a trailing `k`/`K` is copied onto the first number when only the second carries
it.

**Test:** `test_pay_period.py` — the three original failing strings, asserting the
parser now returns the real range (not the wrong-number match, not the un-decoded
entity blocking period detection, not the 1/1000-scale minimum).

---

## Package 14 — proving the data, and fixing what stayed broken

### R18. A postings harvester's own `verified_companies` was rebuilt from scratch every run

**Wrong:** each provider harvester wrote `verified_companies` fresh every run, with no
memory of what the immediately previous, COMMITTED run had already confirmed. A
scheduled run that could only reach a fraction of a large candidate list (an always-empty
CI cache — `data/raw/` is gitignored, and the workflow persisted nothing between runs —
meant the "new candidate" bucket, capped per run, was all a run could ever probe)
overwrote the committed file with that smaller fraction, permanently erasing every
company it didn't happen to re-verify. Ashby went from 862 verified companies (package
12) to 304 in one such run — an external audit's own Finding 3.

**Correct:** `postings_common.merge_verified_companies()` — a company verified this run
is written fresh; a company previously committed but probed-and-failed THIS run is
retained with an incremented failure streak, dropped only after
`DEFAULT_MAX_CONSECUTIVE_FAILURES` (3) consecutive misses, and the drop is logged; a
company not probed at all this run is untouched. `postings_common.build_probe_order()`
additionally reclaims every previously-committed company UNCONDITIONALLY each run
(uncapped), not just whatever the "new candidate" cap happened to include — the actual
mechanism that let the collapse happen in the first place.

**Test:** `test_postings_seed_accumulation.py` —
`test_the_destructive_bug_itself_a_provider_returning_nothing_no_longer_erases_the_seed_list`
simulates the exact failure this bug shipped as (every candidate in a 300-company
committed list fails to reprobe in one run) and asserts the whole list survives with
zero removals; `test_previously_verified_tokens_are_reclaimed_unconditionally_even_with_zero_new_budget`
reproduces the empty-CI-cache mechanism directly.

**Recovery, for the record:** the same package that fixed the mechanism also re-probed every
company Ashby's own seed list had recorded as verified before the collapse (package 12's own
1,419-company list) against the live API, live, with the on-disk cache deliberately deleted
first so "still responds" meant a genuine fresh answer, not a stale cached one — 554 of 558
still responded and were restored. An adversarial review (L4) found this recovery left no
trace in the committed data itself: the recovery run's own `meta.tier_0_3_recovery` block and
provenance entry were both overwritten by the next regular harvester run roughly 30 minutes
later, which is expected (`meta` describes the MOST RECENT run, not a history log) but meant
the 554/558 figure existed nowhere durable. Recorded here instead, since this catalogue — not
a per-run `meta` block — is this project's own durable home for "a bug happened, here is
what was found and fixed."

### R19. A provider's own compensation period tag disagreed with its own numbers — and a first fix for it shipped its own version of the same class of bug

**Wrong:** Ashby's own `interval`, Lever's own `interval`, and USAJOBS' own `salaryType`
are real fields, but not always correct for the SPECIFIC posting they're attached to — an
employer's own ATS form entry, or a federal listing's default salaryType, not this
pipeline mis-reading real text. A skilled-trade wage of `$30-$50` tagged "year" rendered
as a $30-$50/year salary. 64 records (an external audit's own count) annualised below
$12,000 as a result.

**First correction, later found wrong and removed:** a rule scaling any "year"-tagged,
unmarked bare number from 250 up to 12,000 by ×1000 (an employer presumed to mean
thousands — the work order's own example, "OTE $250-$300" for an Enterprise Account
Executive). An independent adversarial review found this rule had already produced real,
wrong published values: HireHangar's own "Underwriter" and "Underwriting Analyst"
postings read raw_text "$500 - $700", genuinely $500-$700/MONTH like ~90 sibling postings
from the same employer at the identical shape and magnitude — turned into a fabricated
$500,000-$700,000/YEAR that then passed every downstream plausibility check, worse than
the original visibly-broken reading. The rule could not reliably tell "a bare number
meant in thousands" apart from "a bare number that is monthly with its own qualifier
text dropped" — both produce an identical raw shape, and picking between two physically
different real interpretations by magnitude alone is exactly the class of guess this
project's own rules forbid. Removed entirely rather than patched with a corroboration
heuristic (an "OTE" text marker, a same-employer cross-check) — see
`scripts/postings_common.py`'s own module comment above `_YEAR_LOOKS_HOURLY_THRESHOLD`
for the full incident.

**Correct, current state:** `postings_common.reinterpret_implausible_year()` — ONE rule
remains: a "year"-tagged range under 100, in USD only (the threshold was itself found
currency-blind, applied to raw EUR/INR numbers calibrated only against USD data — a
second adversarial-review finding, fixed by restricting to `currency == "USD"`), is
reinterpreted as hourly, values unchanged. Every bare-number-possibly-meant-in-thousands
case the removed rule used to touch is now left alone, on purpose, the same way the
100-250 gap always was — flagged for review by R21's own plausibility gate instead of
guessed at.

**Test:** `test_postings_compensation_fixes.py` — every case is a real record pulled
live while diagnosing the bug (antares' own hourly-shaped wage, the USAJOBS seasonal
Clerk role), not a synthetic example; the HireHangar and amperos OTE cases are now
regression-tested to confirm they are BOTH left untouched, on principle, rather than one
being "correctly" rescaled and the other not — this function no longer tries to
distinguish the two by magnitude alone, because it cannot do so reliably.

### R20. A data-quality report claimed health for a module it never actually ran

**Wrong, two compounding bugs:** `generate_data_quality_doc.py` called
`snapshot_stats.main(append=False)` — a keyword argument `main()`'s own live signature
did not accept (`def main() -> int:`, no `append` parameter at all, despite being
DESCRIBED as already added in an earlier package's own report — the edit never actually
landed in the file). The resulting crash was caught and rendered as "COULD NOT RUN," but
the document's own OVERALL status computation summed only `errors`/`drops` — a crashed
module's own empty error list contributed zero, so the page still read "Overall:
PASSING" two lines above a section that said the opposite.

**Correct:** `snapshot_stats.main()` now genuinely accepts `append` (and
`baseline_reset_note`); `generate_data_quality_doc.py`'s own `overall_status()` counts a
module that raised or never ran as `unverified` and folds it into the FAILING
determination directly, separate from (but alongside) real error counts.

**Test:** `test_generate_data_quality_doc.py` — calls the real `snapshot_stats.main
(append=False)` (the exact call that raised live) and asserts it no longer raises;
calls `overall_status()` directly with a hand-built crashed-module result shape (the
work order's own explicit instruction: "add a test that constructs a crashing module and
asserts the overall status is not PASSING").

### R21. A meet-in-the-middle comparability rule that only ever ran pairwise, never across the set it was rendering

**Wrong:** `crosswalk.compare()` correctly resolves comparability between any TWO
mappings, and `scripts/build_wage_distribution.py` called it once per country against a
single fixed reference (Sweden) — but the wage panel then rendered every
`comparable: true` row regardless of how shallow, with no step that asked whether the
WHOLE displayed set actually shared that depth. A 1-digit Irish figure (Ireland's own
source is ISCO major group 2, "all professionals," not software) rendered on the same
axis as a 4-digit Swedish one, with no visual distinction — an external audit's own
Finding 1 (SEVERE): the site's own published Spanish median implied Spanish developers
earn 0.74x the Spanish national average wage.

**Correct:** `crosswalk.resolve_set()` — given every displayed country's own pairwise
verdict, resolves the deepest depth reached by a real quorum (>=2 distinct COUNTRIES) of
them, and excludes by name, with a reason, any country whose own depth does not EXACTLY
equal the resolved depth — too shallow to meet it, or (an independent adversarial review's
own finding, M2) too DEEP: an earlier revision admitted a country deeper than the resolved
depth as "comparable, degraded" while its underlying VALUE stayed at its own full native
depth (the code was truncated to the resolved depth; the data underneath it was not) — the
same class of problem Finding 1 itself was about, mirrored inside its own fix. Exact-match
inclusion means a country whose own classification is MORE precise than what the rest of
the displayed set can support leaves the chart too, honestly, rather than showing a
partially-mismatched value at a truncated label. Quorum counting was also found (M3)
operating on ROW LABELS, not countries — Canada's own two NOC-code rows (`CA-21231`,
`CA-21232`) both landing at 4-digit let Canada alone satisfy "2 countries share this
depth," which the function's own docstring already promised could never happen; fixed by
collapsing to `label.split('-')[0]` for quorum-counting and "who forced it" disclosure
purposes only — per-row verdicts are unaffected, each of Canada's rows is still
individually assessed and rendered. `build_wage_distribution.py` attaches the result as
each row's own new `chart_comparable` field (`crosswalk`, the original pairwise verdict,
is untouched — country pages still read it, see NEEDS-DECISION #40 for where that
remains correct and where it doesn't); `WagePanel.tsx` filters on `chart_comparable`, not
`crosswalk`, and renders the resolved depth plus every excluded country's own reason on
screen, not just in a tooltip — with no more "degraded but comparable" middle state to
disclose, since exact-match inclusion means a comparable row's own depth always equals
the resolved depth by construction.

**Test:** `test_ui_regressions.mjs` R21 — loads the real, live wage panel and asserts
Ireland/Spain/Germany (each excluded from the CHART for their own reason — Germany on
crosswalk-depth grounds, distinct from and not to be confused with the separate OECD
wage-benchmark check, which does not flag Germany at all, see NEEDS-DECISION #35) render
NO bar and DO render their own specific reason, while a comparable country (Sweden)
still renders a bar carrying its own reference year. `scripts/tests/test_crosswalk_
resolve_set.py` (added after M4's own finding — this function had no unit test at all
despite being the severe finding's own fix) covers both exclusion directions and the
Canada quorum-counting fix directly, at the Python level.

---

## Package 17 — the merged page, and the routes the suite never loaded

> **Route note for every R8–R21 entry above.** They say the test "loads `/position`".
> It still does, and `/position` now redirects to `/work` — so those checks exercise
> the redirect as well as the panel. That was not the plan; it is why the defects
> below shipped. A suite that reaches a page only through a redirect never sees what
> the page added.

### R22. `/work` and `/openings` had no regression coverage at all, and four defects shipped through the gap

**Wrong:** `/position` and `/postings` were merged into `/work`, with the browsable list
moved to a new `/openings`, and the UI suite went on navigating to `/position`. Nothing
ever loaded either new route. Four defects shipped:

1. All fifteen coverage-matrix country links were `<a href="#c-DK">`. Under
   `createHashRouter` a bare fragment replaces the ROUTE — every one landed on the
   404 page and took the reader's profile query string with it. A commit had already
   spent a WCAG 2.5.8 target-size fix on these links while they did not work at all.
   The same root cause made the site-wide skip link — the first keyboard-reachable
   control on every page — navigate to the 404.
2. The merge dropped `supported` from `PayVsCost`'s render condition. `computeEstimate()`
   never reads `profile.occupation`, so that gate was the only thing stopping it:
   `/work?occupation=isco08:2511` printed "Your estimate · $135,980/yr" for Systems
   analysts, taken from the US **software developer** row, directly beneath a panel
   saying no wage data resolves for that occupation.
3. Canada's two NOC sections shared one DOM `id`, and an internal `-first` render
   sentinel reached the screen as the heading "Canada · CA-first" — erasing CA-21231,
   the code that earns Canada two sections at all.
4. The display-currency picker converted every posting at one latest-year rate while
   the native→USD leg was year-matched with a stated two-year ceiling, and the estimate
   flag was read from the first leg alone. A 2016 listing shown in Australian dollars
   came out 15.4% high across a nine-year gap, unmarked.

**Correct:** the matrix controls and the skip link are buttons that scroll and focus;
`supported` gates the estimate again; sections are keyed by the wage row's own code and
`firstOfCountry` is a boolean; and both FX legs obey one rule, with the payload shipping
the whole rate series per display currency so the client can match a posting's own year.

**Test:** `test_ui_regressions.mjs` R22 — twenty-two checks that load `/work` and
`/openings` directly. Asserts unique section ids, both Canadian NOC codes present, no
`-first` in any heading, zero bare-fragment anchors in the matrix, that clicking CA
targets `c-CA-21231` and the route survives, that an unsupported occupation renders no
estimate and no pay-against-cost panel, that a 2016 posting converts at the **2016**
cross-rate and is unmarked, and that a 2026 posting is marked with both legs named.
Verified failing against the pre-fix cross-rate before being relied on.

---

## Findings considered and not made into a Tier-0 test, with the reason

- **BLS `hourly_mean_usd` mislabelled as annual** (package 7) — fixed by re-fetching
  under the correct datatype, not a code-logic branch with a wrong/right path to
  regress-test; the underlying rule ("a pay field's name states its own currency and
  period") is enforced generally by Tier 1's own structural invariant instead of one
  source-specific regression.
- **Crosswalk depth/confidence/no-series self-description findings** (packages 7, 8) —
  already covered by `validate_data.py`'s own existing assertions
  (`check_crosswalk_comparison_depth`, `check_crosswalk_notes`,
  `check_no_series_records`, `check_percentile_absence_explicit`), which Tier 4 folds
  into this package's own single audit command rather than duplicating.
- **Denmark's STAND/MDRSNIT reconciliation** (packages 9–10) — not a fixed bug with a
  wrong/right pair to regress. `_verify_mdrsnit_reconciliation()` re-proves itself
  every time `src_salary_dk.py` actually re-fetches live, but package 10's own finding
  F20 (`NEEDS-DECISION.md` #23) is that a warm cache (`_query()`'s own default) means
  most runs re-verify this pipeline's own parsing and arithmetic against a file already
  on disk, not whether DST revised its published figures since — restated accurately
  here rather than repeating the overclaim that finding corrected. Covered twice over
  by this package instead: Tier 1's `check_embedded_cross_checks_reconcile()`
  independently recomputes the residual from the committed artefact (no live fetch,
  catches a stale/hand-edited number); Tier 2's `reconcile_denmark()` genuinely
  re-fetches STAND/MDRSNIT live (its own separate cache, not `_query()`'s), so between
  the two, both the internal-consistency and the against-a-live-source halves are
  real, not just asserted.
- **Spain's tenure-cross population mismatch** (package 10, F2) — the fix was removing
  personalisation entirely, later replaced by package 11's own same-population-only
  design (R12/R13 above test that replacement directly). Nothing remains at the
  original bug's own site to regress against.
- **Coverage-map self-contradiction** (packages 10 F6, 11 F3/F8b) — UI/self-description
  rather than an arithmetic defect; covered by Lighthouse/visual gates each package
  already ran, not this catalogue.
