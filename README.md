# CS Migration Compass

**Compare 15 countries and 73 cities on what a developer salary actually buys.**
Salary, tax, rent, savings, years to a home, residency timelines, who already
moved there. Every number carries a source, a date and a confidence tier.

Static site. No backend, no tracking, no accounts. MIT-licensed code, openly
licensed data, and a pipeline that rebuilds the whole dataset with one command.

---

## Why it exists, and what it refuses to do

Most "best countries to move to" content is a ranking written by someone who
already decided the answer. This is the opposite of that.

**We visualise; we never recommend.**

- No "best country", no verdict, no score, no default ranking.
- Any ordering you see exists because *you* built it — you chose the axes, the
  weights, the filters.
- Cities are listed alphabetically until you say otherwise.
- **Every filter is off by default**, including visa feasibility. Someone with a
  remote job has no visa question at all, and the site should not assume they do.
- **Nulls are honest.** A city with missing data is never dropped and never
  guessed at. It says which figure is missing. Aarhus and Doha are the standing
  test cases.
- Institutional forecasts are drawn solid and attributed; our own extrapolation
  is drawn dashed and labelled *"not a forecast"*. They are never averaged.

If a number here surprises you, it is meant to be checkable. Tap it.

---

## The data

| File | What it holds |
| --- | --- |
| `data/countries.json` | 15 countries — visa routes and 2026 thresholds, study pathway, Iranian-passport friction, PR and citizenship timelines, dual citizenship, tax model, job market, quality-of-life indices, language reality, an honest narrative paragraph |
| `data/cities.json` | 73 cities — developer salaries in three bands, levels.fyi total-comp band, rents, living costs, apartment prices, climate, travel from Tehran, tech-scene notes |
| `data/metrics.json` | The data dictionary: definitions, directions, confidence tiers, pinned FX, staleness rules |
| `data/processed/` | 24 processed datasets from the pipeline |
| `data/raw/` | What was actually downloaded, committed so any transform can be re-audited offline |
| `data/provenance.json` | Every source: URL, fetch time, licence, and the exact transforms applied |

**24 datasets, 22 with data.** World Bank, Eurostat (ICT specialists and total
employment), OECD (house prices, wages, hours, tax wedge), BIS (from 1927), FHFA
(30 US metros from 1975), Teranet (6 Canadian cities), UK HPI (London from 1968),
Indeed Hiring Lab, BLS OEWS, Stack Overflow survey, UN DESA migrant stock,
World Happiness Report, MIPEX, RSF, EF EPI, WIPO GII, Numbeo, plus institutional
forecasts from OECD Economic Outlook 119 and UN World Population Prospects.

Two sources could not be reached and say so on the site rather than being quietly
omitted — see [docs/LIMITATIONS.md](docs/LIMITATIONS.md) §6.

---

## Run it

Requires **Python 3.12+** and **Node 20+**.

```bash
make setup          # Python + Node dependencies
make pipeline       # fetch and process every source (cached downloads reused)
make validate       # the data-integrity gate that CI runs
make site-dev       # http://localhost:5173
```

Other useful targets:

```bash
make pipeline-fresh   # clear data/raw and re-download everything from scratch
make docs             # regenerate docs/SOURCES.md from data/provenance.json
make site-build       # production build into site/dist
make all              # pipeline + validate + docs + build
```

Run a single source, or list them:

```bash
python scripts/pipeline.py world_bank
python scripts/pipeline.py --list
```

A failing source never aborts the run. It is recorded with its status in
`data/provenance.json` and reported in the summary table, because a
half-updated dataset with honest provenance beats a run that dies on source #3.

### How the pipeline is built

One script per source, all sharing `scripts/_common.py`:

```
download → data/raw/<source>/ → process → data/processed/<source>.json
        → append to data/provenance.json (url, fetched_at, licence, transforms)
```

Two gotchas are handled centrally and are worth knowing if you extend it:

- UN DESA, the BLS website, EF and WIPO return **403 to default Python user
  agents**. `_common.py` always sends a browser-like `User-Agent`.
- `housepriceindex.ca` serves an intermediate certificate `certifi` does not
  carry. We route verification through the OS trust store via `truststore` —
  certificate verification is never disabled.

---

## Deploy

Push to `main`. `.github/workflows/deploy.yml` builds and publishes to GitHub
Pages; `BASE_PATH` is set automatically for project pages.

CI (`.github/workflows/ci.yml`) runs three jobs:

- **validate-data** — runs against committed data, no network, so a third-party
  outage can never turn the build red
- **build-site** — typecheck and production build
- **pipeline-smoke** — two cheap live sources, `continue-on-error` for the same
  reason

Link previews: because the app is hash-routed, a crawler fetching `/#/city/berlin`
would only ever see the root page. `scripts/generate_share_pages.py` emits a
static shell per city and country at a real path with correct meta tags, and
`scripts/generate_og_images.py` pre-renders 89 preview images. Both run
automatically as part of `npm run build`.

---

## Repository layout

```
data/       curated + raw + processed + provenance
scripts/    one script per source + orchestrator + validation + generators
site/       the web app (Vite + React + TypeScript + Tailwind + Recharts + Motion)
docs/       SOURCES · METHODOLOGY · LIMITATIONS · DESIGN
```

- **[docs/SOURCES.md](docs/SOURCES.md)** — every source, licence and citation.
  Generated from `provenance.json`; never hand-edited.
- **[docs/METHODOLOGY.md](docs/METHODOLOGY.md)** — every formula, and every
  choice that could have gone another way.
- **[docs/LIMITATIONS.md](docs/LIMITATIONS.md)** — where this is weak, in plain
  sight.
- **[docs/DESIGN.md](docs/DESIGN.md)** — tokens, themes, motion spec.

---

## Licence

**Code** — MIT, see [LICENSE](LICENSE).

**Data** — belongs to the organisations it came from, each under its own terms.
Some are open (World Bank, Eurostat, UN DESA); some permit derived aggregates
only; for those this repository commits the fetch script and the aggregates but
not the raw payload. Every source's licence and required citation is in
[docs/SOURCES.md](docs/SOURCES.md). Read it before redistributing anything from
`data/`.

---

## Contributing

The most useful contributions are corrections. If a number is wrong:

1. Check `data/provenance.json` for where it came from and what was done to it.
2. Open an issue with the source that contradicts it.

Adding a source means adding one `scripts/src_<name>.py` that follows the same
contract — download to `data/raw/`, write `data/processed/`, record provenance —
and one line in `SOURCES` in `scripts/pipeline.py`. `make validate` will tell you
if you missed anything: it fails the build on a missing licence, a missing
transform list, a placeholder where a null belongs, or an inverted salary band.

*Dataset as of 2026-08. FX pinned in `data/metrics.json`.*
