# State of the site

One page on what this site currently holds, what has actually been checked, what is
knowingly imperfect, and what is still undecided. Written at package 30 (September 2026).

The deep documents already exist and are not repeated here: [METHODOLOGY.md](METHODOLOGY.md) for
how each figure is derived, [DATA-FITNESS.md](DATA-FITNESS.md) for whether each dataset supports
the claim it is labelled with, [LIMITATIONS.md](LIMITATIONS.md) for the long list of caveats,
[SOURCES.md](SOURCES.md) for where everything came from. This page is the map.

Every number below is reproducible; [how to re-check all of it](#how-to-re-check-every-number-on-this-page)
is at the bottom.

---

## What it covers

| | |
|---|---|
| Cities | 73 |
| Countries | 15 |
| Metrics | 30, across 7 themes (money 5, housing 7, climate 5, life 4, visa 4, people 3, jobs 2) |
| Pages the site can render | 108 route/entity combinations the test suite walks, over 103 distinct URL paths (`/work` and `/compare` appear more than once with different query strings) |
| Figures on those pages | 646, plus 61 "no data" marks |
| Pipeline sources | 57 recorded in `data/provenance.json`; 54 render (53 ok, 1 partial); 2 blocked, 1 unavailable |
| Payload on arrival | `site/public/data/core.json` — 397.8 KB raw, ~89 KB gzipped. It is the only blocking fetch |
| Payload if you open `/openings` | `postings.json`, **23.1 MiB**. `dist/data` is 28 MB in total, almost all of it history. Nothing else on the site is remotely this heavy, and it is the reason open item #69 exists |

The site is static. There is no server, no account, and nothing is stored about a visitor.

---

## What is verified, and how

**On every push to `main`, every pull request, and on manual dispatch, CI runs:** the Python
pipeline suite (`scripts/tests/test_*.py`, auto-discovered),
`validate_data.py`, `audit_data.py`, a TypeScript type-check, the site's own unit tests, a
production build, and then two browser suites against that build's preview server.

**The two browser suites are the ones that catch what review misses.** They drive a real headless
Chrome over the built site:

- **`test_ui_regressions.mjs`** — pinned regressions from earlier packages, at 1280 wide.
- **`test_figure_inventory.mjs`** — renders all 108 route/entity combinations and asserts over what
  the DOM actually contains, at 1440 wide. Six standing assertions:

  | | |
  |---|---|
  | C1 | no figure is sitting on an unset initialiser |
  | C2 | no "no data" is shown over data that exists |
  | C3 | no internal key, pipeline filename or id leaks into view |
  | C4 | every figure opens a source card, and no card is titled with a bare source id |
  | C5 | nothing is clipped below legibility without a way to read it |
  | C6 | every mark clears 3:1 contrast against what is really painted behind it |

  Package 24 shipped two defects of exactly this kind to production; both were invisible in code
  review and obvious on screen. That is why these assertions read the DOM and the painted pixels
  rather than the source.

  **Two caveats on this suite, both found while writing this page.** First, the six do not all cover
  everything: the suite's own header records that C4 idles on five of the eight Explore themes (they
  carry no figure cards) and C5 idles on all eight (nothing is clipped there), so on Explore the
  real cover is C3 and C6. Second, and worse: on one unchanged build the suite captures either
  646 figures / 61 no-data / 764 marks, or 646 / 54 / 668 — and the difference is the whole of
  `/openings`, which fetches a 23.1 MiB file against a fixed 150 ms wait. **Roughly three runs in
  four, an entire route and 12.6% of the marks are missing from what C1–C6 assert over, and the run
  still prints PASS** — because every assertion is shaped "N found, expect 0", and a route that was
  never seen cannot fail one. Open item #69.

**Per package, by hand:** Lighthouse (desktop preset, at least 90 performance / 95 accessibility
across 14 routes) and an independent adversarial review of the package's own work. Neither runs in
CI.

**What this does not establish.** All of the above checks that the site renders honestly what the
data says. Whether the data itself is fit for the claim on the label is a separate question,
answered dataset by dataset in [DATA-FITNESS.md](DATA-FITNESS.md) — which found, among other
things, that "median advertised pay by country" is not supported as labelled.

---

## What is known-limited

These are not bugs. They are places where the honest answer is worse than the one a reader might
assume, and they are stated on the page wherever they affect a figure.

**1. Age is standing in for experience, for two countries.**
`experience_gradient.json` carries pay-by-experience curves for Sweden and Norway only, built from
national wage data banded by age (18–24, 25–34, 35–44 …). Age is not experience: someone who
changed career at 40 sits in the 35–44 band as a junior. The curves are labelled `confidence:
derived` and are deliberately *not* applied to the other 13 countries — package 10 shipped one
universal curve borrowed from Spain's tenure data and package 11 retired it, because borrowing one
country's shape for another is the exact defect the pipeline elsewhere refuses to commit.

**2. National wage series do not all measure the same thing.**
The 15 wage-distribution records (14 sources; Canada carries two occupation codes, NOC 21231 and
21232) split on what "pay" means at source: 6 report **regular pay**, 4 report **total earnings**
including overtime and bonus, and 5 record no basis at all (Denmark, Qatar, the UAE, and both
Canadian codes). A total-earnings country will look
better paid than a regular-pay country by definition, before any real difference. The field is
recorded per source as `native_basis` and pinned by a test so a rebuild cannot silently drop it.

**3. 16 of 73 cities have no second salary band.**
The "top-employer pay" card (levels.fyi median total compensation) resolves for 57 cities. On the
other 16 there is one band, not two, and the card says so rather than estimating. Where both bands
do exist they are never blended: they are different quantities (total comp vs base), correlated at
r = 0.90 but 1.22× apart on average. Separately — see open item #60 — for 21 of the 73 the two
bands are not independent, because both trace to the same levels.fyi metro page.

**4. Six countries have no official immigration source on record, and most figures have no page.**
Canada, Germany, Italy, Spain, the UAE and Qatar carry no recorded official immigration authority,
so their residency and citizenship figures name a compiled source rather than a government one.
For the nine that do have an authority, package 30 checked which recorded page actually documents
which figure: of 36 rendered citations, **8** have a page on record for their own figure. The other
28 now link nothing and say so, because until package 30 every country served one page for all four
questions — Helsinki cited a work-permit page for "years to permanent residency". Two of the 36 were
right by luck rather than by design (Norway and Sweden record only a citizenship page, and the
citizenship figure is one of the four asking); 34 were about something other than the figure beside
them. A citation is a claim that the linked document supports the number, and naming the authority
while linking a page about something else is not a weaker version of that claim — it is a false one.

The eight that remain are matched at topic level, not sentence level, and one is weak on its own
terms: Denmark's tuition figure links a higher-education study-permit page, and the figure itself is
a recorded estimate ("typically DKK 75k–120k/yr").

**5. Layout is verified at one width per suite, in a window taller than any screen.**
The browser suites run at 1280×2000 and 1440×4200. The tall viewport is deliberate — it forces
deferred content to mount so the assertions can see it — but it means nothing is checked while
actually scrolling, and neither suite runs at a phone width. Mobile (390×844) has been measured by
hand for `/explore` (package 28) and is not pinned by any test. A layout defect that only appears
at 390px, or only after a scroll, would pass CI.

---

## What is still open

The decision log ([NEEDS-DECISION.md](../NEEDS-DECISION.md)) holds 69 items. Package 30 read the 68
that existed and reconciled every heading against its own body, then added one of its own:
**60 closed, 9 open.** Before that, 57 headings gave no indication either way, so the honest answer
to "what is still open" was that nobody knew.

All 9 remaining are judgement calls for the owner, not unfinished work:

| # | What it is |
|---|---|
| 17 | Denmark's two DST concepts don't reconcile; one subtraction step has to assume a shape the source doesn't publish |
| 42 | `/postings` "Median advertised pay by country" supports one country, not seven — how should it be shown? |
| 56 | CV storage — scoped out of package 22 and deliberately deferred since |
| 60 | For 21 of 73 cities, the two salary bands trace to the same levels.fyi page |
| 61 | Two lower-severity citation figures found by package 26's own rule, not fixed |
| 62 | The UAE plots at $49,000 on "the price of the door", but one of its three routes has no salary floor at all |
| 63 | Doha's salary citation lost a working PayScale link to stop it misattributing a band |
| 65 | CI's browser suites failed once on a 30-second Chrome start budget, and passed on re-run unchanged |
| 69 | Roughly three runs in four, the figure-inventory suite drops `/openings` entirely and still reports green |

---

## How to re-check every number on this page

Run from the repository root.

    # cities and countries
    node -e "const c=require('./site/public/data/core.json');console.log(c.cities.length,c.countries.length)"

    # payload, raw and gzipped
    node -e "const z=require('zlib'),f=require('fs');const b=f.readFileSync('site/public/data/core.json');console.log(b.length,z.gzipSync(b).length)"

    # pipeline sources and their status
    node -e "const p=require('./data/provenance.json');console.log(p.entries.length)"

    # metrics
    grep -c "^    key: '" site/src/data/registry.ts

    # 108 combinations, 646 figures, and the C1-C6 assertions
    node scripts/tests/test_figure_inventory.mjs

    # everything CI runs on the pipeline side
    python scripts/tests/run_all.py

    # what each national wage source actually measures
    node -e "require('./data/processed/wage_distribution.json').data.countries.forEach(c=>console.log(c.source_id,c.native.native_basis))"

    # cities carrying a top-employer band
    node -e "console.log(require('./site/public/data/core.json').cities.filter(c=>c.salary_levels_fyi?.median_total_comp_usd!=null).length)"

    # open items
    grep '^## ' NEEDS-DECISION.md | grep -icv 'closed\|resolved\|obsolete\|decided\|ruled\|superseded'
