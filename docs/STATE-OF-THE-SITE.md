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
| Pages the site can render | 134 route/entity/state combinations the test suite walks. 108 of them are route/entity pairs over 103 distinct URL paths; the other 26 are material STATES the suite reaches by driving a control, because package 33 found 28 controls that change what the assertions read and the suite navigated only by URL (package 34) |
| Figures on those pages | 1,048, plus 942 "no data" marks and 1,642 marks in total (package 47's count, the same as package 46's). The jump from 646/61/764 is the 26 state targets above, not new content: the /openings and /work cards that appear only once a display currency is chosen had never been examined by anything |
| Pipeline sources | 57 recorded in `data/provenance.json`; 54 render (53 ok, 1 partial); 2 blocked, 1 unavailable |
| Payload on arrival | `site/public/data/core.json` — 398.7 KB raw, ~89.5 KB gzipped. It is the only blocking fetch |
| Payload if you open `/openings` | An index (452 KB gzipped) carrying the fields the filters read, plus row chunks fetched only for the rows shown (98 files, ~19.6 KB gzipped each). It was one 23.1 MiB file — 2.50 MB gzipped — until package 38 shipped #71's ruling. On Slow 4G the payload's own share of the wait went from 42.0 s to about 9.2 s |

The site is static: no account, and nothing is stored about a visitor. Two things reach a server,
and only when the reader asks. The CV reader (package 22) sends the text the reader has reviewed —
never the file — to a Cloudflare Worker that asks a model for two fields. And a store for those two
fields (#56, built in package 45; #85 ruled that it keeps the occupation and the number and nothing
from the CV, against a random key held in the reader's browser, for 30 days) is offered only when the
Worker behind it is deployed. **It is not deployed yet.** Since package 47 the Deploy workflow asks the
Worker on every build — a `GET /profile` with no Origin header, which cannot create or read anything —
and while the answer is the old Worker's 404, the site is built with no consent to keep anything, no
saved-profile panel, and no call to the store. Deploying the Worker and re-running Deploy turns it on,
with no code change.

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
  the DOM actually contains, at 1440 wide. Seven standing assertions:

  | | |
  |---|---|
  | C1 | no figure is sitting on an unset initialiser |
  | C2 | no "no data" is shown over data that exists |
  | C3 | no internal key, pipeline filename or id leaks into view |
  | C4 | every figure opens a source card, and no card is titled with a bare source id |
  | C5 | nothing is clipped below legibility without a way to read it |
  | C6 | every mark clears 3:1 contrast against what is really painted behind it |
  | C7 | every city holding a top-employer figure states it in words and draws it as a tick on screen (package 46) |

  Package 24 shipped two defects of exactly this kind to production; both were invisible in code
  review and obvious on screen. That is why these assertions read the DOM and the painted pixels
  rather than the source.

  **One caveat on this suite, and one defect that has since been fixed.** The caveat: the six do not
  all cover everything: the suite's own header records that C4 idles on five of the eight Explore
  themes (they carry no figure cards) and C5 idles on all eight (nothing is clipped there), so on
  Explore the real cover is C3 and C6.

  **#69, fixed in package 31.** On one unchanged build the suite used to capture either 646 figures
  / 61 no-data / 764 marks, or 646 / 54 / 668 — the difference being the whole of `/openings`.
  Roughly three runs in four, an entire route and 12.6% of the marks were missing from what C1–C6
  assert over, and the run still printed PASS, because every assertion is shaped "N found, expect 0"
  and a route that was never seen cannot fail one.

  **The cause recorded on this page was wrong, and package 31 corrected it.** This page said
  "a fixed 150 ms wait". There was no such wait — `capture()` already polled for readiness. The
  fault was the PREDICATE it polled: `button, .nodata, h1, h2, table, .wrow`, a set the page SHELL
  satisfies before any route content exists.

      t=208ms    4 elements    0 rows     829 chars   <- page shell
      t=616ms    4 elements    0 rows     829 chars   <- capture() declared READY
      t=726ms   16 elements  100 rows  14459 chars   <- the route's own content

  Two things changed. Readiness is now network-idle plus DOM-stable with a throwing timeout
  (`waitForReady`), so no fixed sleep decides anything; and `coverage.mjs` asserts what a run SAW
  before any violation check runs, against per-route floors recorded by a deliberately different
  strategy. Absence now fails. That second half is the durable part — fixing the wait fixed one
  route, and the shape had let any route hide.

**Per package, by hand:** Lighthouse, through `scripts/tests/lighthouse_gate.mjs`, and an
independent adversarial review of the package's own work. Neither runs in CI. The Lighthouse gate
audits 15 routes on the desktop preset — performance at least 90, **total blocking time at most
150ms**, accessibility, best practices and SEO at least 95 — and `/openings` five times on throttled
mobile, where it enforces the **median LCP (at most 2,500ms) and median CLS (at most 0.1)** and
prints, without enforcing, the performance score and the spread of TBT.

That split is #86's ruling (package 47). The throttled-mobile score was measuring Lighthouse's
simulated main thread rather than the page: five runs of one unchanged build scored 73–87 while TBT
ran 414–1,291ms, and the build before it scored lower. LCP and CLS are what a reader sees; across
the 25 runs on record, every set's median LCP sat at 2,414–2,436ms and no CLS was above 0.044. The
two thresholds are Lighthouse's own "good" boundaries for those metrics, so the LCP margin is thin
(about 70ms) on purpose. Dropping the mobile score from the gate is acceptable only because desktop
TBT is enforced on every route in its own right — 0–87ms on every route across packages 43–45 —
and that catches the main-thread regression the mobile score used to. Before package 47 desktop TBT
counted only through its 30% share of the performance score, and a route at about 270ms still
passed.

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
do exist they are never blended: they are different quantities (total comp vs base). In 17 of the 57
the market band itself comes from levels.fyi, so there is no second source, and since package 47
(#90) those pages state the figure without a comparison. On the other 40 the two correlate at
r = 0.86 but run 1.27× apart on average, 95% limits of agreement 0.80× to 2.02× — package 16's 1.22×
had been computed on all 57, self-comparisons included. Separately — see open item #60 — for 21 of
the 73 the two bands are not independent, because both trace to the same levels.fyi metro page. On
those 21, each bar now links a levels.fyi page its own record lists — its own level's page wherever
one is recorded. Until package 47 each linked the top-employer figure's page instead: a page it was
not read from for 36 of the 63 bars, and nothing at all for 12, in the four cities where that record
is a stub.

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

**5. The two broad suites check layout at one width each, in a window taller than any screen.**
The regression suite and the figure inventory run at 1280×2000 and 1440×4200. The tall viewport is
deliberate — it forces deferred content to mount so the assertions can see it — but it means nothing
they assert is checked while actually scrolling, or at a phone width. Since packages 46–47 three
narrower suites do run at phone widths in CI, each for named properties only: D1 (every disclosure
opens to its full content without widening the page, at 390/1024/1440), F1 (the CV flow by real
clicks at 320/390/1024/1440), and P1–P4 (the header is one row and Home, Explore's chips and Home's
dot field fit, at 360–414 and up). A layout defect of any other kind that only appears at 390px, or
only after a scroll, would still pass CI.

**6. `/work`'s estimate column is per year, and for six of its nine figures the year is this site's arithmetic.**
Since package 47 (#88) every estimate reads per year. Spain, the UK and the US publish per year.
Sweden, Norway and Finland publish per month, and the year is twelve times the monthly estimate,
which counts what each office's monthly figure counts and no more — SCB's leaves out a 13th or 14th
month and profit-sharing, Finland's regular-hours earnings leave out the holiday bonus and
performance bonuses, Norway's include bonuses averaged over January to November; each card says
which, as read at the source. Canada and Denmark publish per hour. Canada's year uses Statistics
Canada's average usual hours for full-time employees across all industries (39.8 h in 2024) — not
developers' own hours — and is shown to three significant figures; Denmark's uses DST's 37-hour
standard week, the unit its hourly figure is defined in. The conversion is the pipeline's
(`normalise.annualise()`), the published figure is one tap away, and the concept labels ("incl.
pension", "incl. bonus", "excl. bonus") stay beside the figures: a common period is not a common
concept.

---

## What is still open

The decision log ([NEEDS-DECISION.md](../NEEDS-DECISION.md)) holds **90 items: 79 closed, 1
reopened, 10 open** (as of package 47). Package 30 read the 68 that existed then and reconciled every
heading against its own body — before that, 57 headings gave no indication either way, so the honest
answer to "what is still open" was that nobody knew. Package 47 closed #85, #86, #87, #88 and #90 on
the owner's rulings.

Counting them is itself a small lesson, and the trap moves. When this section was first written, a
case-insensitive search for "closed" miscounted because #73's heading contained the words "a closed
sheet". #73 is closed now; today the same search misses #68, whose heading reads "REOPENED, package
41 (closed on arrival, package 29)", and reports 10 where 11 need the owner. The markers are shouted
(`CLOSED`, `RESOLVED`, `REOPENED`) and the prose is not, which is the distinction the count has to
make — the same unanchored-substring mistake #33 records in the pipeline.

All 10 open, and the one reopened, are judgement calls for the owner, not unfinished work:

| # | What it is |
|---|---|
| 17 | Denmark's two DST concepts don't reconcile; one subtraction step has to assume a shape the source doesn't publish |
| 42 | `/postings` "Median advertised pay by country" supports one country, not seven — how should it be shown? |
| 56 | CV storage — the store is built at two values (package 45; #85 closed on "keep the two numbers"); its Worker is not deployed, so the site offers no consent (package 47) |
| 60 | For 21 of 73 cities, the two salary bands trace to the same levels.fyi page (on the 17 of them holding both, city pages now state the figure without a comparison — #90) |
| 61 | Two lower-severity citation figures found by package 26's own rule, not fixed |
| 62 | The UAE plots at $49,000 on "the price of the door", but one of its three routes has no salary floor at all |
| 63 | Doha's salary citation lost a working PayScale link to stop it misattributing a band |
| 68 | *Reopened.* `core.json` costs 89.5 KB on every theme — closed by package 29 on a Lighthouse mobile run, reopened by package 41 because package 38 measured 7.9 s of app-boot-plus-core.json on Slow 4G, which that instrument could not see |
| 75 | `/openings` still shifts 0.0085–0.0593 depending on width — all inside "good" — because the table has no column widths |
| 76 | `yearsToHome` returns null for both "no inputs" and "saves nothing", and every caller has to remember to ask separately |
| 89 | Explore's hero numbers — three facts per theme that do not add up to an answer |

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

    # 134 combinations, 1,048 figures, and the C1-C7 assertions
    node scripts/tests/test_figure_inventory.mjs

    # everything CI runs on the pipeline side
    python scripts/tests/run_all.py

    # what each national wage source actually measures
    node -e "require('./data/processed/wage_distribution.json').data.countries.forEach(c=>console.log(c.source_id,c.native.native_basis))"

    # cities carrying a top-employer band
    node -e "console.log(require('./site/public/data/core.json').cities.filter(c=>c.salary_levels_fyi?.median_total_comp_usd!=null).length)"

    # open items
    grep '^## ' NEEDS-DECISION.md | grep -icv 'closed\|resolved\|obsolete\|decided\|ruled\|superseded'
