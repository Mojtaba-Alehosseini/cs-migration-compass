# Chart integrity audit

Written before any fix. Every metric in `site/src/data/registry.ts` and every
chart in Explore, Home and Compare, classified against the four fault classes in
the build brief.

Method: `registry.ts` was bundled and executed against the live `core.json`, so
the `value` and `format` functions checked here are the ones that ship — not a
re-reading of them. The scatter builder's own `axis()` was copied verbatim into
the harness. Raw output: `.status/evidence/p6-audit.txt`
(`.status/evidence/p6-audit.mjs`).

**No source data value is wrong.** Rent, living costs, purchase price and salary
are all on their published grids ($10/month, $10/m², $1,000/year). Every fault
below is in what the site derives from them or in how it draws them.

---

## Summary

| Class | Findings | Live today | Fixed in this package |
| --- | --- | --- | --- |
| A — unguarded derived ratio | 3 metrics, one root cause | yes | yes |
| B — formatter invalid as a tick label | 6 metrics | yes | yes |
| C — direction | 2 metrics | yes | labelled, not reordered |
| D — domain from raw extremes | 4 charts | yes | yes, via the stability flag |

---

## Class A — unguarded derived ratio

One quantity is behind all three: **savings per year**, which is a *difference of
two large numbers* and can land below the precision of its own inputs.

```
savings_usd_year = net_salary − 12 × (rent + living costs)
```

Rent and living costs are each published to $10/month. Both moving one step is
**$240/year**. Any savings figure smaller than that is a rounding artefact, not a
measurement.

| Metric | Formula | Denominator | Smallest observed | Stable there? |
| --- | --- | --- | --- | --- |
| `savings` | `net − 12×(rent+col)` | — (a difference) | **$210** (Milan) | **no** — smaller than the $240 step on its own inputs |
| `years_to_home` | `(90 × price/m²) ÷ savings` | savings | **$210** | **no** — Milan 2,314 yrs, Valencia 1,275 yrs |
| `m2_per_year` | `max(savings,0) ÷ price/m²` | price per m² (min $1,300, step $10) | denominator is fine | **no** — inherits the unstable numerator: Milan 0.04 m²/yr moves +114% on one step |

`m2_per_year`'s own denominator is well-conditioned (a $10 step on a $1,300 floor
moves the result 0.8%). It is unstable only because its numerator is.

### The instability test, and what it finds

Perturb rent and living costs by one published rounding step each (±$10/month =
±$240/year on the pair) and recompute. Flag the value if years-to-home moves more
than **25%** either way, or flips to "never on this salary".

Run against the live data, at the mid band, over the 72 cities that have a value:

```
city              savings/yr      years    cheaper     dearer  worst move  verdict
Milan                    210     2314.3     1080.0      never       flips  UNSTABLE
Valencia                 240     1275.0      637.5      never       flips  UNSTABLE
Rome                   2,430      125.9      114.6      139.7       11.0%  stable
Doha                   3,840       56.2       52.9       60.0        6.7%  stable
Cork                   4,450       64.7       61.4       68.4        5.7%  stable
Turin                  4,900       42.2       40.3       44.4        5.2%  stable
Dublin                 6,050       83.3       80.1       86.7        4.1%  stable
Barcelona              6,600       70.9       68.4       73.6        3.8%  stable
London                 6,930      110.4      106.7      114.3        3.6%  stable
Edinburgh              9,100       47.5       46.3       48.8        2.7%  stable
Madrid                10,800       36.7       35.9       37.5        2.3%  stable
Stockholm             12,040       50.1       49.1       51.1        2.0%  stable
… 60 more, all stable

UNSTABLE: 2 — Milan, Valencia
STABLE:   70, worst move among them 11.0%
```

**Exactly two cities, and the separation is not marginal**: the worst stable city
moves 11.0%, the two unstable ones flip out of existence entirely. Nothing sits
near the 25% line, so the threshold is not doing delicate work — the inputs'
own rounding step is.

The existing `savings <= 0 → null` guard sits at a discontinuity: at +$1 saved
the site reports 486,000 years, at −$1 it reports "never on this salary". Those
are the same statement about the world.

**Fix:** `compute.ts` gains `yearsToHomeStability()`, computed by the test above
and carried through `computed[band]` so every surface reads one flag rather than
recomputing. The number is **kept and marked**, never suppressed.

---

## Class B — formatter invalid as a tick label

`axis()` produces tick *values*; the metric's display `format` renders them. A
formatter that clamps, buckets or returns words is correct for one datum and
wrong for an axis.

Tested by generating each metric's real axis and formatting its ticks:

| Metric | Ticks | Distinct labels | What it produces | Verdict |
| --- | --- | --- | --- | --- |
| `years_to_home` | 6 | **2** | `["0.0 yrs","100+ yrs","100+ yrs","100+ yrs","100+ yrs","100+ yrs"]` | **the reported bug** |
| `english_work` | 5 | **4** | `["rarely","no data","often, depends on the employer","no data","usually yes"]` | collides **and** categorical |
| `tuition` | 5 | 5 | `["free","$10,000","$20,000","$30,000","$40,000"]` | a word among currency |
| `pr_years` | 5 | 5 | `["~0 yrs", …]` | **`~0 yrs` is not a thing**: no country grants PR on arrival |
| `happiness_rank` | 6 | 6 | `["#0","#10","#20", …]` | **`#0` does not exist** |
| `peace_rank` | 4 | 4 | `["#0 of 163", …]` | same |

The last three are not collisions, but they are the same defect: a display
formatter used where an axis formatter is needed, producing labels for values
that cannot occur.

`english_work` is worse than a formatting problem. It maps `high/medium/low` to
`3/2/1` and back to words — a **categorical variable on a continuous axis**.
A tick at 1.5 means nothing, and the distance between "rarely" and "often" is not
a number. It should not be axis-eligible at all.

**Fix:** `MetricDef` gains `tickFormat`, defaulting to a plain numeric formatter;
`format` keeps its clamping for single figures. `english_work` is removed from the
axis pickers with the reason stated on screen, and recorded in
`docs/LIMITATIONS.md`. A dev-time assertion in the chart kit throws when an axis
produces duplicate labels.

---

## Class C — direction

| Metric | Better is | Axis reads | Says so? |
| --- | --- | --- | --- |
| `happiness_rank` | lower (#1 best) | ascending left→right, so best is at the left | **no** |
| `peace_rank` | lower (#1 best) | same | **no** |

Live today: the shipped preset *"Money against life"* puts `happiness_rank` on x.
A reader who does not know the metric reads "further right is more" and gets the
answer backwards.

**Not reordered.** Inverting an axis silently is its own trap, and the Explore
happiness chart already offers rank-space with `#1` at the top as an explicit,
labelled choice. The fix here is to say which way is better in the axis label —
a wording change, not a reordering. Recorded so the decision is visible.

---

## Class D — domain from raw extremes

| Chart | Where | Uses | Worst case |
| --- | --- | --- | --- |
| Explore scatter | `ExploreCharts.tsx:29-30` | `Math.min/max` over all values | **the reported bug**: `apt_m2 × years_to_home` puts 55 cities into the bottom 1.3% |
| Compare chart view | `Compare.tsx:557` | `Math.max` over positive values | years-to-home with Milan present crushes every other bar |
| Weights tool | `WeightsTool.tsx:65` | `Math.min/max` per metric to normalise | worse than a drawing fault: an unstable extreme **changes every other city's score** |
| Home field | `questions.ts:67,84,87` | fixed ticks, capped at 130 → `≈never` | **already safe** — a cap established in package 1 |
| ClimateOverlay / ClimateMatcher / CountryProfile | min/max over climate and origin counts | no derived ratio involved | checked, clear |

The Home field is the pattern to extend rather than replace: it already refuses
to let an enormous years-to-home value set its scale, and says `≈never` instead.

**Fix:** the domain is computed from **stable values only**; flagged points are
drawn in a labelled overflow band at the edge of the plot, keeping their real
number in the hover readout and in the CSV. The Weights tool excludes flagged
values from its min/max the same way and discloses it, since there a bad extreme
silently rescales other cities' scores.

---

## What gets fixed in this package

- **Class A** — all three metrics, through one flag in `compute.ts`.
- **Class B** — all six, via `tickFormat` plus the injectivity assertion;
  `english_work` withdrawn from axis pickers.
- **Class C** — labelled, not reordered; decision recorded.
- **Class D** — all four live sites; Home already safe.

Nothing here changes a stored value. Every change is a derivation or a rendering.
