# Needs a decision

Raised while porting the design mockups into the React app. Nothing here blocked
a build: each item was resolved the least-invasive way and shipped, and each one
is reversible. They are listed because the choice was not mine to make.

---

# Package 5 — Explore

## 1. Stack Overflow: one wave is wired, six are missing

`data/processed/stackoverflow_survey.json` holds **only the 2024 wave** — every
one of the fifteen countries has exactly one key, `"2024"`. The percentile and
sample-size fields are all present, so the distribution chart is real today; what
is missing is the time axis.

**Shipped:** the panel draws the 2024 distributions and says on the page that it
"grows a time axis the day the 2017–2023 archives land in the pipeline".

**Decide:** whether to add a pipeline step for the archived survey dumps
(2017–2023 are published as CSV per year). That is a data-pipeline package, not
a UI one, and it is the single change that would turn this panel from a snapshot
into the site's best time series about pay.

## 2. Indeed: eight metros drawn, thirty in the file

The work order says to "use whatever `indeed_hiring_lab_job_postings` actually
contains and say the count on the page". The file contains **30** US metros; the
locked design draws **8**, and gate 10 requires metro series to use the `--m-1…8`
palette — eight colours.

**Shipped:** the design's eight, with the footer stating
"8 of the 30 metros in the file — the eight the design draws", so the reader
knows what is not drawn.

**Decide:** whether the other 22 deserve a way in — a picker would fit the
site's grammar, but it would be a second control on a chart the design gives one,
which the brief forbids.

## 3. The mockup's prose says four metros; its data says eight

Recorded as the work order asks. `EX.indeed` in the mockup holds eight metros and
its palette note says "four US metros cannot borrow other countries' colours".
The data won; the prose appears to be a leftover from an earlier draft.

**Decide:** nothing, unless the prose was the intent and the data the leftover.

## 4. The OECD overlay applies *real* growth to a *nominal* line

The design compounds the OECD's projected **real** GDP growth onto the World
Bank's **nominal** US$ level, draws it as a separate paler line, and hides it
entirely in the yearly-change lens with a chip explaining why. That is the
mockup's own arithmetic and the pre-existing behaviour of `ExploreCharts`.

**Shipped:** exactly that, and the chip in the yearly-change lens states the
mismatch in the design's words.

**Decide:** whether the level and indexed lenses should carry the same caveat.
They currently do not — the paler line and the "projection →" label are the only
signal there that it is a different quantity.

## 5. `bls_oews`, `imf_weo`, `worldbank_gep`, Numbeo city rents

Four datasets that cannot be drawn as series, each verified rather than assumed:
BLS returns one year per metro; `imf_weo` is `status: blocked` with an empty
`data` object (403 from every `imf.org` host); `worldbank_gep` is
`status: unavailable`; `numbeo_history.data.by_city` is `{}`.

**Shipped:** each has a gap card naming the dataset, the reason and where it is
tracked. No panel is blank anywhere on Explore.

**Decide:** whether any of the four is worth a fetch strategy of its own — the
IMF parser is written and would run the day the block lifts.

---

# Package 4 — Compare

## 6. Three surfaces the mockup does not draw, and does not ask to remove

Compare already carried a metric picker (`+ add a metric`), a budget editor and a
climate overlay. The mockup's screen 2 ends after the two footnotes, and the work
order says only that metric selection is out of scope for that package.

**Shipped:** all three kept, moved to sit *after* the mockup's own elements, so
the drawn sequence — toolbar → address strip → chips → table/chart → footnotes —
is exactly as designed and the undrawn extras follow it.

**Decide:** keep them where they are, fold them into the design properly, or drop
them.

## 7. The copy-link toast claims a preview image that does not exist

The mockup's toast reads *"Link copied — preview image attached ✓"*.
`scripts/generate_share_pages.py` only builds share shells for `/city/` and
`/country/`. A comparison link is `…/#/compare?places=…`; the hash never reaches
the server, so it gets the site's default Open Graph image — not a preview of
that comparison.

**Shipped:** `Link copied — the whole comparison travels in the address`.

**Decide:** accept the new wording, or add per-comparison OG images.

## 8. Sticky header on phones is a CSS impossibility, not an omission

A horizontally scrolling container is also a vertical scrollport, so a
`position: sticky` row inside one pins to *the container* and never to the
viewport. Measured across every overflow combination Chrome accepts: only
`overflow-x: clip` preserves viewport-sticky, and `clip` makes wide tables
unreachable.

**Shipped:** the header row pins under the site header at every width where the
table fits; where it must scroll sideways, the metric-label column pins left
instead.

**Decide:** accept, or spend a JS-synced duplicate header row on the phone case.

## 9. `band` and `lens` stay out of the address until they are touched

**Shipped:** existing URL contract kept. A default link reads
`…/#/compare?places=berlin,toronto` and grows as controls are used.

**Decide:** whether a shared link should spell out its defaults.

## 10. Metric rows are the registry's, not the mockup's

Binding note 13 keeps metric selection out of package 4, so the rows are still
`HEADLINE_KEYS` from `site/src/data/registry.ts`.

**Decide:** if the mockup's illustrative set was meant as the new default, that
is a change to `headline: true` in the registry.

## 11. Missing-input wording comes from `compute.ts`, not the mockup

`missingInputs()` returns `living costs` and `apartment price` where the mockup
wrote `living-costs` and `apartment-price`. The list is used as it comes, with
one exception: the purchase price is dropped from the "kept after rent and
living" reasons, because that formula never uses it.

**Decide:** nothing, unless the hyphenated forms were deliberate.
