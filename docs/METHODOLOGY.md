# Methodology

Every formula the site uses, and every choice that could reasonably have gone
another way. If a number on the site surprises you, the explanation is here.

The implementations live in two places and are kept deliberately parallel:
`scripts/build_site_data.py` (defaults, baked at build time) and
`site/src/data/compute.ts` (live recomputation when you edit the budget).

---

## 1. Money

### Currency

Everything is USD. Conversions use **pinned** FX rates from
`data/metrics.json` → `meta.fx_rates_usd_base`, snapshotted in early 2026:

```
EUR 0.8686 · GBP 0.7446 · AUD 1.4262 · CAD 1.4044 · SEK 9.5589
NOK 9.5316 · DKK 6.4927 · AED 3.6725 · QAR 3.64
```

Pinned rather than live, because a comparison site whose numbers drift daily is
impossible to check, cite or share. Gulf currencies are USD-pegged, so those are
exact. The comparisons here are robust to small FX drift; if a rate moves 10 %
the conclusions do not change, but the figures shown will lag reality.

**Historical series are not FX-converted.** Applying a single 2026 rate to a
1970s-to-2020s price series would be actively misleading, so the UK house-price
history stays in GBP and is labelled as such.

### Net pay

```
net = gross × (country net_pct / 100)
```

`net_pct` is `tax.net_pct_single_mid_dev` in `data/countries.json`: the
take-home share for a **single person with no children at a mid-level developer
salary**, including employee social contributions, computed per country against
OECD Taxing Wages plus national calculators. Each country's `net_note` records
the exact salary and rules used.

This is one household shape. A married applicant with children, or someone
inside an expat scheme (the Dutch 30 % ruling, Denmark's researcher scheme),
will see a different figure. Expat schemes are recorded in
`tax.expat_scheme` but are **not** applied to the headline number, because they
are temporary and conditional.

### Savings

```
savings_per_year = net − 12 × (rent + living costs)
```

Rent defaults to the **one-bedroom outside the centre** figure, not the centre —
it is the realistic first-flat case for someone arriving with no money. Living
costs are Numbeo's single-person, excluding-rent basket.

Both are editable. Change them and savings, years-to-home and metres-per-year
all recompute live.

### Two salary bands, never merged

Each city carries two independent salary signals:

| Field | What it is | Source family |
| --- | --- | --- |
| `salary_usd_year` | market-wide bands, three experience levels | talent.com, PayScale, BLS |
| `salary_levels_fyi` | median total compensation at large/known employers | levels.fyi |

They are shown side by side and **never averaged**. Merging the two families is
precisely what produced the impossible salary bands (new-grad above mid) that
phase 3 had to repair in Sydney, Dubai and Abu Dhabi.

They are also not directly comparable: levels.fyi reports **total
compensation** (base + stock + bonus) while the market bands are closer to base
salary. Part of the gap between them is a definition difference, not an employer
premium. The site says so wherever both appear.

---

## 2. Years to a home

```
years_to_home = (90 m² × price per m² outside centre) / savings_per_year
m2_per_year   = savings_per_year / price per m² outside centre
```

90 m² is the reference flat — roughly a modest two-bedroom, consistent across
every city so the comparison means something. Prices are Numbeo's
outside-the-centre purchase price per square metre.

**This is a cash-purchase model.** It contains no mortgage, no interest, no
deposit, no property tax and no transaction costs. It is a measure of *how hard
a place is to buy into on a developer salary*, not a financial plan. Real buyers
use mortgages and get there sooner.

**When savings are zero or negative**, the site says *"never on this salary"*.
It does not print the arithmetic result, because the honest statement is that
nothing is left over at all.

### When the number is smaller than its own error bars

Savings is a **difference of two large numbers**, and years-to-home divides by
it. That makes the ratio arbitrarily sensitive exactly where savings are small —
and "small" here has a precise meaning, because we know the precision of the
inputs.

Rent and living costs are published to the nearest **$10 a month**. Both moving
one step is **$240 a year**. A savings figure below that is not a measurement of
anything; it is the rounding on its own inputs. Milan is the live example: it
saves **$210 a year**, which is $17.50 a month, and years-to-home comes out at
2,314. Move its rent by one rounding step and that becomes 1,080 years, or
disappears entirely.

So the site tests every years-to-home figure against the precision of what
produced it:

> Recompute savings with rent and living costs each perturbed by one published
> rounding step (±$10/month, ±$240/year on the pair). If years-to-home moves by
> more than **25%** in either direction, or flips to "never on this salary", the
> figure is **rounding-limited**.

**The threshold is not a number we chose.** It is the inputs' own published
grid. We did not pick 25% to catch particular cities and we did not tune it: run
against the current data it flags **exactly two of 72 cities — Milan and
Valencia** — and the worst of the other seventy moves 11%. Nothing sits near the
line.

**A rounding-limited figure is kept, not hidden.** We do not suppress numbers;
we say what is wrong with them. The value still appears everywhere it appeared
before, carrying a `≈` marker in the same warning language as every other
caveat, and its source card explains in plain words that what the city saves in
a year is smaller than the rounding on its own rent, and that the figure should
be read as *"effectively out of reach"* rather than as a count of years.

One thing does change: **a rounding-limited figure is never allowed to set the
scale of a chart.** It is drawn in a labelled band at the edge of the plot, with
its real number in the readout and in the CSV export, so 70 well-measured cities
are not crushed into a line by a value that is mostly rounding. The same rule
keeps it out of the min/max the weights tool normalises against, where a bad
extreme would silently change every other city's score.

The old `savings <= 0` guard sat on a discontinuity: at +$1 saved the site
reported 486,000 years, and at −$1 it reported "never". Those were the same
statement about the world, and now they read the same way.

---

## 3. Nulls

A missing value is `null` everywhere — never `0`, never `""`, never an average
of the neighbours. The validator (`scripts/validate_data.py`) fails the build if
a placeholder string appears where a null belongs.

Derived values always emit `missing_inputs`, naming exactly which figures were
absent, so the interface can say *"we have no living-cost or purchase-price
figure for Aarhus"* rather than silently dropping the row. Aarhus and Doha are
the standing test cases.

### Composite tools

The opt-in weights tool redistributes the weight of any missing metric across
the metrics that are present, and reports how much weight was redistributed.
Treating a missing value as zero would quietly punish places for having thin
data, which is a different claim from the one the tool appears to make.

---

## 4. History and forecasts

### The separation rule

| Kind | How it is drawn | Rule |
| --- | --- | --- |
| Institutional forecast | solid line + attribution chip ("OECD Economic Outlook 119") | never blended |
| Our extrapolation | dashed/hatched band, labelled "naive extrapolation, not a forecast" | never presented as authoritative |

They are never averaged into a single line, and our extrapolation is never shown
without its label.

### Our naive extrapolation

Fits the mean annual change over the last 10 observations and extends it
linearly. It is deliberately unsophisticated: it exists to show *"if the recent
past simply continued"*, which is a different and more honest claim than a
forecast.

### Telling actual from projected

- **UN WPP** — the edition states it: estimates end 2023, later years are the
  medium variant.
- **IMF WEO** — the file's own `Estimates Start After` column.
- **OECD Economic Outlook** — the cube carries no projection flag, so we derive
  it: a year is a projection when it is later than the last year the World Bank
  publishes an actual GDP-per-capita figure *for that same country*. Derived
  from data rather than assumed, and recorded in the dataset's metadata.

Only the **medium** UN variant is shown. Displaying high and low variants would
imply we modelled a range; we did not.

### City history vs country history

Real city-level series exist for:

- **US** house prices — FHFA, 1975→, all 30 metros
- **Canada** house prices — Teranet, 1990→, all 6 cities
- **UK** house prices — HM Land Registry, London from 1968
- **US** job postings — Indeed Hiring Lab, 2020→
- **US** developer wages and headcount — BLS OEWS (current year only)

Where only country history exists, a city panel may show the **country trend
applied to the city's current value**, and must be labelled exactly:

> city estimate = current value × country trend

It is never presented as city data.

Two geography caveats matter:

- FHFA publishes only the **metropolitan division** for 13 of our 30 metros — a
  subset of the metro area. The published area name and an `is_metro_division`
  flag travel with every series.
- Our `sf_bay_area` record spans San Francisco *and* San Jose. Both series are
  fetched and shown separately; they are never averaged.

---

## 5. Ranks and indices

Index scores are never printed raw. `6.882` means nothing to a reader; *"#17 of
147 for happiness"* does. Every rank carries its denominator, computed from the
number of countries actually ranked in that edition.

World Happiness scores are **three-year rolling averages**, so year-on-year
moves are damped by construction — a flat line is not necessarily a stable
country.

BIS and OECD index bases differ by country. Those series are comparable in
**shape**, never in level, and the UI compares growth rather than levels.

---

## 6. Staleness

`data/metrics.json` → `meta.staleness_rules_months`:

```
visa 6 · prices_salaries 12 · indices 18 · climate 120
```

A figure older than its rule shows a warning in its source card rather than
being hidden. Visa figures get the shortest fuse because they change fastest and
because a stale visa threshold is the most expensive kind of wrong number here.

---

## 7. What the site deliberately does not do

- It publishes no ranking, score or verdict. Any ordering exists because a user
  constructed it.
- It applies no filter by default — including visa feasibility, because someone
  with a remote job has no visa question at all.
- It never hides a place for having missing data.
- It does not adjust for purchasing-power parity in the headline figures. PPP
  GDP is available in the World Bank data for the economy charts, but salaries
  and rents are compared in nominal USD, which is what actually lands in an
  account.
