# Limitations

Known weak spots, kept in plain sight. This file is the source for the "Where we
might be wrong" panel on the site's Data & methods page.

Sections 1–5 come from the verification pass on the curated dataset. Sections
6–9 record what the pipeline build added.

---

## 1. US-West salaries are conservative floors

For 14 of 15 US-West cities the salary bands come from official BLS medians plus
Indeed, **not** levels.fyi total compensation. SF Bay is the exception. True
senior compensation at large employers is higher than the market band shows.

The levels.fyi enrichment pass now supplies the other side of this as a separate
band, so both signals are visible — but the market band remains the headline
figure, and it leans low in the US.

## 2. Gulf salaries are deeply two-tier

Multinational and elite employers in the UAE and Qatar pay 2–4× the general
market. Both signals are recorded and neither is averaged into the other.

Gulf packages also routinely include housing allowances that no salary figure
captures, so the cost side is overstated relative to reality. Doha's very low
savings figure reflects thin data more than lived experience.

## 3. Numbeo and Expatistan are crowd-sourced

Solid for large cities, thin for **Halifax, Aarhus, Tampere, Gold Coast and
Detroit**. Crowd-sourced rents and prices carry a `crowd` confidence tier
everywhere they appear.

## 4. Minor nulls in the curated data

Sunshine hours are missing for 5 cities and rainy days for 7. Aarhus is missing
living costs and both purchase-price fields — its Numbeo page is empty, and its
rents were recovered from Expatistan using a 45 m² studio proxy, flagged as low
sample.

The site handles all of these as "no data" with the missing field named. Aarhus
and Doha are the standing null tests.

## 5. Smoke tests used a flat tax demo

The early smoke tests in phase 3 used a flat 70 % net-of-tax assumption. The
site uses each country's real `net_pct_single_mid_dev` from
`data/countries.json`. Any figure quoted from that early report will not match
the site.

---

## 6. Sources we could not reach

Recorded honestly in `data/provenance.json` and rendered on the site's Data &
methods page rather than quietly omitted.

| Source | Status | Detail |
| --- | --- | --- |
| **IMF World Economic Outlook** | blocked | Every `imf.org` host returns HTTP 403 at the Akamai edge from the build environment — the WEO database page, the DataMapper API and `data.imf.org` alike, with full browser headers and through a real browser. `sdmxcentral.imf.org` responds but carries no WEO dataflow. The parser in `scripts/src_imf_weo.py` is complete and runs wherever IMF is reachable; a documented manual drop-in path exists. Until then the site draws **no IMF line at all** rather than an approximation. |
| **World Bank Global Economic Prospects** | unavailable | The GEP landing page exposes only per-figure chart workbooks, not a country forecast table. Nothing parseable was found at build time. |
| **Numbeo per-city history** | unavailable | City price-history pages render their series client-side; the served HTML contains only navigation chrome, and `?itemId=` changes nothing (verified for items 1, 26, 27, 105). Numbeo's terms also restrict bulk use. Country-level yearly snapshots **do** work and are used. |

The institutional-forecast layer therefore runs on **OECD Economic Outlook 119**
and **UN World Population Prospects 2024**, both live and attributed.

## 7. Coverage gaps that are real, not bugs

- **Eurostat is EU/EFTA only.** The US, Canada, Australia, UAE and Qatar have no
  ICT-specialist or total-employment series. The site shows "no data" for them
  and does not substitute another source. **Gulf jobs data in particular is
  thin, and the country pages say so.**
- **BIS and OECD exclude the Gulf.** The UAE and Qatar are not members and appear
  in no OECD dataflow; BIS returns 404 for both.
- **MIPEX**: the 2020–2024 workbook covers EU countries plus Canada — 9 of our
  15. Australia, the US, the UK and Norway are absent from that file.
- **EF EPI** does not score native-English countries. Australia, the US, Canada,
  the UK and Ireland are absent **by design**, and the site says "English is the
  native language" rather than showing a gap.
- **WIPO GII**: 13 of 15 extracted. Two countries' table rows use embedded-font
  glyphs that extract as `(cid:NN)` garbage; they are left out rather than filled
  from a neighbouring column.

## 8. BLS is a snapshot, not a history

The public OEWS API returns the **current reference year only**. Identical
series IDs for 2015–2024 return "No Data Available", and pre-2018-SOC codes
return "Series does not exist". Verified empirically, not assumed.

So US city developer wages and headcounts are a single-year snapshot. **The site
draws no BLS trend line**, because it does not have one. Older years exist only
in archived OEWS releases, which are a documented manual drop-in.

## 9. Structural limits of the model

- **Years-to-home is a cash-purchase model** — no mortgage, deposit, interest,
  property tax or transaction costs. It measures difficulty of entry, not a
  financing plan.
- **One household shape.** All tax figures assume a single person with no
  children. Expat schemes are recorded but not applied to headline numbers.
- **FX is pinned to early 2026** and will drift.
- **Nominal, not PPP.** Salaries and rents compare in nominal USD.
- **FHFA geography**: 13 of 30 US metros are published as metropolitan
  *divisions*, a subset of the metro area. Flagged per series.
- **Indeed's metro index is all-jobs**, not software-only. A metro-by-sector cut
  is not published. Labelled as such.
- **Stack Overflow respondents self-select** and skew toward English-speaking
  developers. Useful for shape and cross-country comparison, weaker as an
  absolute wage level. Every bucket carries its sample size and a thin-sample
  flag.
- **Link previews for arbitrary comparisons** fall back to the default image. A
  static host cannot render one image per permutation of six cities; per-city and
  per-country previews are pre-rendered.

## 10. Things that will age

Visa thresholds, points cutoffs and processing times change faster than anything
else here. They are rendered as dated chips with a 6-month staleness warning, not
as settled facts.

Several 2026 developments are already load-bearing in the curated data and should
be re-verified before relying on them: the Iran–Gulf conflict and its effect on
residency security for Iranian citizens in the UAE, the US proclamation
restricting Iranian-national visa issuance, Sweden's citizenship tightening
(5 → 8 years), the UK's proposed ILR extension (5 → 10 years), and Australia's
deprioritisation of ICT occupations.

Their verification status differs and matters. The Iran–Gulf strikes, Sweden's
citizenship change and Germany's stability were confirmed directly against
multiple outlets. The US visa proclamation, the UK ILR proposal and Australia's
ICT tiering were corroborated but not independently re-verified, and each
should be checked against the official source before anyone acts on it. Every
affected field in `data/countries.json` carries its own `sources` array and
`as_of` date.

---

## 11. Two metrics that cannot occupy a chart axis

The scatter builder lets any metric become either axis, which means every metric
has to be honest as a *scale*, not only as a figure. Two are not, and are handled
by exclusion rather than by formatting around them.

**English at work is categorical.** The underlying data is three named states —
high, medium, low — which the site stores as 3, 2, 1 so it can be compared at
all. On an axis that becomes a lie twice over: a tick at 1.5 has no meaning, and
the gap between "rarely" and "often, depends on the employer" is not a distance
that can be measured. It is therefore **not offered in the axis pickers**. It
remains available everywhere a single value is read — country pages, Compare, the
metric picker — where three named states are exactly what it is.

**Rank metrics read backwards on a rising axis.** Happiness rank and
peacefulness rank are better when lower, so on an axis that ascends left to
right the best places sit at the left. We have not silently inverted them: an
axis that reverses without saying so is its own trap, and Explore already offers
happiness in rank space with #1 at the top as an explicit, labelled choice. The
axis label states which direction is better instead. If a future pass wants
per-metric axis inversion, that is a design decision to take deliberately, not a
default to slip in.
