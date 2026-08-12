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

---

# Package 7 — The salary spine

## 12. Canada's NOC 2021 splits one ISCO-08 job into two codes; nothing sums them

`data/occupations.json` maps NOC 21231 ("Software engineers and designers")
**and** NOC 21232 ("Software developers and programmers") to the *same* shared
key, `isco08:2512` — the same job Sweden, the UK and the US each report under
one code. NOC draws a professional-engineering-licensure line between the two
that ISCO-08 does not itself draw, so there is no single "Canadian equivalent"
figure to hand back; there are two, and they differ (Toronto: 21231 median
CAD 56.49/hr, 21232 CAD 48.08/hr — not close enough to treat as noise).

**Shipped:** both codes are recorded in full, each individually correct, with
`is_primary_target: true` on both and a note on each pointing at the other.
Nothing sums them, nothing picks one and drops the other.

**Decide:** when package 9 builds the cross-country developer-pay comparison,
should Canada's figure be 21231+21232 combined (the fuller "everyone who
codes for a living" population, closer to what Sweden/UK/US each already
report as one number), 21231 and 21232 shown side by side (preserves the
signal that Canada's own classification treats these as different jobs), or
just 21232 alone (the closer semantic match to "developer" as opposed to
"engineer")? Whichever is picked changes where Canada lands relative to the
other three on that chart.

## 13. BLS OEWS's percentile extension is written and verified, but not committed as data — RESOLVED in package 8, tier 0

`scripts/src_bls_oews.py` now requests 8 datatypes (employment, hourly mean,
annual mean, annual P10/P25/median/P75/P90) instead of the old 3, and fixes a
real pre-existing bug: datatype 04 was fetched and stored as
`hourly_mean_usd` but is actually the ANNUAL mean (148,100 for the 2025
national series — obviously not an hourly rate). Both the extension and the
fix were run successfully and spot-checked against raw API bytes twice during
this session, with every figure matching the work order's own cited reference
numbers exactly (employment 1,687,890; P10 82,460; median 135,980; P90
214,670; San Jose P90 289,150, confirming BLS's May 2025 release now publishes
real uncapped high percentiles instead of the old ">=$239,200" top-code).

**Not shipped as of package 7** (historical — see "Resolved" below):
`data/processed/bls_oews.json` as committed by package 7 was UNCHANGED from
its pre-package-7 state. BLS's unregistered API caps at 25 requests/day;
that session's own repeated development and verification runs exhausted it,
twice — the second time immediately after a request that had briefly
succeeded, suggesting the cap or its reset window is stricter than a simple
daily boundary. Committing a broken/empty fetch in place of the working file
that existed before that package touched it would have been a real
regression, so the processed file and its provenance entry were both
reverted to their exact pre-package-7 state instead. `salary_se`/`salary_uk`/
`salary_ca` were unaffected — they hit no such limit and shipped fully
committed with fresh, verified data in package 7.

**Resolved 2026-08-11 (package 8, tier 0):** the work order's prescribed fix —
switch to BLS's bulk special-request zips, which sit outside the timeseries
API's rate limit — turned out not to be reachable: `bls.gov` and
`download.bls.gov` are blocked wholesale from this environment (verified via
three independent request methods, all returning HTTP 403 "Access Denied" on
every path tried, including the plain human-facing landing page, not just the
data files). This is a site-wide edge block, matching an existing finding in
`data/data-pipeline-sources.json`, not a header or rate-limit problem, so
switching endpoints could not have helped. What actually closed the gap was
running the exact code above, unchanged, during a window when the timeseries
API's daily quota was available — it succeeded cleanly (256/256 series,
32 areas x 8 datatypes, 0 failures) and every figure matches the numbers
quoted above exactly, including the corrected `hourly_mean_usd` (71.20
USD/hr) now sourced from its own datatype rather than aliased from the
annual figure. `data/processed/bls_oews.json` is committed with the full
extension as of package 8. No further action needed on this item.

**Decide:** nothing — this was the open decision as of package 7 (run the
pipeline again when quota allows, or register a free BLS API key). Package 8
resolved it by the first route; both options are recorded here only as
history of what was considered, not as outstanding work.

---

# Package 8 — Salary breadth

## 14. Germany has no salary source in this package — GENESIS could not be reached

The work order named Destatis GENESIS (tables 62361-0030/-0034, KldB 2010,
mean and median) as Germany's source, and explicitly pre-authorised skipping
it if "no credential is available": *"If no credential is available, record
it in NEEDS-DECISION.md and skip the country cleanly — do not scrape a
workaround."*

**What was tried.** GENESIS documents a published, non-personal guest
credential (username/password both `GAST`) specifically for anonymous access
— using it is not "creating an account" in the sense the standing rules
prohibit; it is a shared demo credential Destatis itself publishes. Two
endpoints were attempted against the documented REST base
(`www-genesis.destatis.de/genesisWS/rest/2020`) with those credentials, per a
maintained community API wrapper's documentation: `data/table` (fetch a
specific table) and `catalogue/tables` (search, to sanity-check the
credential independently of any one table ID). Both returned HTTP 200 with
the site's React frontend HTML shell, not JSON, regardless of `Accept`
headers — consistent with the API having moved to a newer version since that
wrapper's documentation was written (a GENESIS "Webservice/API" manual dated
May 2025 references version 5.0, while the wrapper and the URL itself are
pinned to "2020").

**Shipped:** no `salary_de` source this package. Germany is absent from the
salary spine's data layer; the crosswalk and the comparison rule (Tier 4)
both need to treat Germany as having zero coverage, not 2-digit or "no
series" coverage — those are different data states from "not attempted".

**Follow-up attempt (2026-08-12, prompted by an adversarial review asking whether the
domain-move theory was ever actually tested):** `www-genesis.destatis.de` now redirects
(307) to `genesis.destatis.de` — the whole subdomain has moved, not just the API
version. Re-tried the same `helloworld/logincheck` endpoint with the GAST/GAST
credential on the NEW domain
(`genesis.destatis.de/genesisWS/rest/2020/helloworld/logincheck`): still returns the
"GENESIS-Online" React shell, not JSON — confirming the failure is not simply a stale
domain either. The REST API's actual current path was not found. This narrows the
question (it is not "which domain" but genuinely "which path/version") without
answering it.

**Decide (superseded by package 9 below — kept for history).**

---

## 15. Germany, package 9 — DESTATIS_TOKEN unavailable; API confirmed ALIVE, blocked by an account-permission wall (superseded within this item — see the 2026-08-12 tier 2b update below; the original heading here claimed the API path was "confirmed deprecated", which the tier 2b update below found was itself too broad a conclusion)

Package 9's work order named an API token, `DESTATIS_TOKEN`, as "set by the runner
script, which lives in the gitignored `prompts/` directory" — i.e. `prompts/run-
package-9.cmd`, which does contain a `set DESTATIS_TOKEN=...` line (confirmed present,
value not read — see below). That script injects the token when package 9 is launched
*through* it. This session received the work order pasted directly into chat, not via
that script, so the environment variable was never set — checked in both the Bash and
PowerShell environments used this session, neither has it.

Per the work order's own rule ("Read it from the environment only... never reach the
repository, the report, a log file, a commit message or a data file"), the token was
**not** extracted from `run-package-9.cmd` directly — doing so would have pulled a live
secret into this session's own context/transcript, which the "environment only" rule
exists specifically to prevent, even though the file happened to be locally readable.
Confirmed only that the file *sets* the variable (`grep -c DESTATIS_TOKEN
prompts/run-package-9.cmd` → 1 match), never its value.

**Fell back to the work order's own pre-authorised path**: "If the token fails, try the
documented guest account GAST/GAST, then record precisely what failed." This went
further than package 8's attempt and got a materially more specific answer:

- `www-genesis.destatis.de` still 307-redirects to `genesis.destatis.de` (confirmed
  again).
- Every request to `genesis.destatis.de/genesisWS/rest/2020/*` — tried
  `helloworld/logincheck` and `data/table` with `name=62361-0030` — now returns an
  explicit **HTTP 302** (not a silent 200-with-HTML-shell, which is what package 8 saw)
  redirecting to `https://genesis.destatis.de/datenbank/online/announcement?username=
  GAST&password=GAST&...`. That target is GENESIS-Online's new human-facing web portal,
  not an API response — the server is deliberately rerouting the entire old REST
  namespace into the web UI, not merely serving it stale content.
- That `/announcement` page is itself a client-rendered React shell — WebFetch (no JS
  execution) cannot read whatever deprecation notice or migration pointer it actually
  displays to a browser.
- Tried five plausible successor version segments in place of "2020" —
  `genesisWS/rest/{2023,2024,2025,2026,5.1}` — every one returned a genuine **HTTP 404**
  (the server has no route at all for those paths), a different failure mode from
  "2020"'s 302. This rules out "just increment the year" as the fix: "2020" is
  specifically deprecated-and-redirected, not one of a numbered family the API still
  serves under a sibling path.

**Net finding:** the old REST API namespace is conclusively decommissioned server-side,
not merely moved or rate-limited. `run-package-9.cmd` itself is just a launcher (sets
`DESTATIS_TOKEN`, then pipes the work order into an unattended `claude -p` run) — it
carries no request logic of its own to inspect, so it doesn't reveal the working
endpoint either. Getting past this needs either (a) `DESTATIS_TOKEN` present in the
actual run (a genuinely different credential/path than the GAST/GAST guest access tried
here might behave differently — untested, since the token was never available this
session), or (b) a human opening
`https://genesis.destatis.de/datenbank/online/announcement` in a real browser to read
whatever migration notice it renders client-side, or GENESIS's own current API
documentation (the version-5.1 manual linked above, June 2026 — a PDF this session
could fetch but not usefully parse; its actual body text needs a human or a proper PDF
reader).

**Shipped:** no `salary_de` source this package either. Same downstream consequence as
package 8: Germany stays at zero coverage in the crosswalk and comparison rule, not
2-digit or "no series".

**Decide (superseded by the 2026-08-12 tier 2b update immediately below — kept for
history; the "redirect" and "decommissioned" framing in the paragraphs above turned
out to be too broad a conclusion from too narrow a test).**

---

**Update, 2026-08-12, package 9 resumed, tier 2b — the API was never down; the calling
convention was wrong, and now the real wall is precisely located.**

Package 9's resumed work order re-opened this item with its own specific hypothesis:
that the REST API had moved to a new path shape, `genesis.destatis.de/api/rest/2020/`
(dropping the `genesisWS` segment), citing `destatis.api.bund.dev` and the official
GENESIS "User Guide Web Services" PDF (version 5.1, 2026-06-01) as evidence.

**That specific hypothesis does not hold up.** Tested live: `.../api/rest/2020/
helloworld/whoami` returns a genuine HTTP 404 (Destatis's own branded German/English
error page — "Ups, ein Fehler!" / "Oops, something went wrong!"), under three separate
auth attempts (no auth, GAST as query parameters, GAST as HTTP Basic auth). It does
not appear anywhere in either cited source: `destatis.api.bund.dev`'s own rendered
page declares its Base URL as `www-genesis.destatis.de/genesisWS/rest/2020/` — the
OLD host and path — because it renders `bundesAPI/destatis-api`'s `openapi.yaml`
directly from GitHub, and that repository's own commit history shows it was last
pushed 2023-06-20, more than three years stale. The official PDF (downloaded and read
in full — 128 pages, via PyMuPDF after the PDF-tools MCP's sandbox rejected the
scratchpad path and pdftoppm was unavailable for the Read tool's own PDF renderer) was
searched for the literal string "api/rest": zero matches across every page. Its own
per-endpoint documentation (`helloworld/whoami`, `helloworld/logincheck`, `data/table`,
all checked) uses `genesis.destatis.de/genesisWS/rest/2020/...` throughout — the
SAME path that both package 8's and this package's own tier 2 attempts already tried
and found redirecting.

**What the PDF's front page actually says changed** is narrower and more mundane: *"The
SOAP/XML web service interface has been switched off. The RESTful/JSON web service
interface now completely replaces SOAP/XML services. GET methods with credentials have
been replaced by the previously parallel offered POST methods of the RESTful/JSON
interface."* The path never moved. What changed is that credentialed calls must be
POST requests with `username`/`password` sent as literal HTTP request headers (not
Basic auth, not query parameters, not a JSON body field) plus a
`application/x-www-form-urlencoded` body for every other parameter. A GET request with
credentials in the query string — exactly what package 8's attempt sent, and what a
"GAST as query parameters" test produces — is the deprecated convention, and reads
`.../datenbank/online/announcement?username=GAST&password=GAST...` — a redirect that,
in hindsight, is the deprecated-GET-convention handler forwarding into the human portal
it now aliases to, not evidence of a dead API.

**Verified live, in order, this session:**
1. `GET .../helloworld/whoami` (no auth) → HTTP 200, `{"User-Agent": "curl/8.9.0"}` —
   the original, unchanged path is alive.
2. `POST .../helloworld/logincheck`, GAST/GAST as HTTP headers, body `language=en`,
   `Content-Type: application/x-www-form-urlencoded` → HTTP 200,
   `{"Status":"You have been logged in and out successfully! ...","Username":"GAST"}`.
   ("GAST" is not named in the current v5.1 guide — a convention carried from the
   older, stale community wrapper package 8 relied on — but Destatis still honours it.)
3. `POST .../data/table` (table `62361-0030`, and separately `catalogue/tables` with
   `selection=62361*`, and the guide's own worked example table `11111-0001`), same
   auth, across `area` values `all` / `public` / `Katalog/Öffentlich` / `oeffentlich` →
   **every single combination** returns the identical, specific denial:
   `{"Code":15,"Content":"You are not allowed to call this service or the header of
   your request does not contain all the necessary information so that your access
   data cannot be recognised.","Type":"ERROR"}` — wrapped in a plain HTTP 200 on the
   first few attempts, then HTTP 401 on later ones against the identical request,
   suggesting GENESIS applies a defensive throttle after several denied calls in a
   short window rather than the response itself changing meaning.

**Net finding:** triangulated across 2 services × 3 tables/selections × 4 `area`
values — GAST authenticates successfully (proves the login mechanism, transport, and
header-auth convention are all correct) but has zero permission on any data or
catalogue service. This is a real, specific, well-isolated account-permission wall,
not a request-shape bug and not evidence the tables are gone. A real `DESTATIS_TOKEN`
— a personal token tied to a registered account, a materially different credential
from the guest login — was not testable this session: still absent from this
interactive session's environment (confirmed via the environment only, exactly as
before; never read from the gitignored runner script that sets it).

**Shipped:** `scripts/src_salary_de.py` (new) — a real, working harvester implementing
the verified request sequence above (whoami → logincheck → both tables), using
`DESTATIS_TOKEN` if present in the environment, GAST/GAST if not, never logging either
credential's value. Run for real this session: whoami and logincheck both succeed;
`data/table` is caught and recorded as `status: blocked` with the exact diagnostic
above, both for the plain-200 and the HTTP-401 response shapes GENESIS returned across
the session. Deliberately does NOT guess which KldB 2010 row is "software developer" —
that lookup needs `metadata/table` or `catalogue/variables2statistic`, both behind the
identical permission wall GAST hit on every other data/catalogue service, so it cannot
be verified against the live catalogue this session either; occupation-row
identification is an explicit follow-up, not invented. Wired into `scripts/pipeline.py`.
`data/pay_composition.json`'s Germany row corrected to say the API is reachable and the
block is account-permission, not availability. Still no `salary_de.json` with real
figures — same downstream consequence as packages 8 and 9's first pass: Germany stays
at zero coverage in the crosswalk and comparison rule, drawn as absent in tier 6.

**Decide:** run this package (or just `scripts/src_salary_de.py`) via
`prompts/run-package-9.cmd` directly so `DESTATIS_TOKEN` is actually present. The
request shape is now confirmed correct and the harvester is real and ready — a working
personal token only needs to clear the same `data/table` call GAST was denied on. If a
real token is ALSO denied with the identical Code 15, that would newly indicate a
genuine account/table-entitlement issue on the Destatis side worth Destatis's own
support contact (`destatis.de/DE/Service/Kontakt/Genesis/Servicekontakt-GENESIS.html`,
found in the guide's own contact section) — a materially different, better-evidenced
next step than "try another URL."

## 16. `phase-4-salary-and-cv-plan.md` assigns package 9 a `stabilityOf()` extension this package's own work order never mentions

The plan document's constraints table says: *"Package 9 must extend `stabilityOf()`
to accept a salary override. §5's 'pay vs. cost, joined' runs a user-chosen percentile
through net → savings → years-to-home... The guard is per-city today and will silently
not apply."* (`phase-4-salary-and-cv-plan.md:491-494`)

The actual "WORK ORDER — PACKAGE 9" text received and executed this session never
mentions `stabilityOf()`, a salary override, or "pay vs. cost, joined" anywhere across
its seven tiers — and Tier 6 draws the boundary explicitly: *"No profile form, no
position, no estimate — those are package 10."* A user-chosen percentile run through
net → savings → years-to-home is exactly a "position/estimate" feature by that
description.

**Treated the work order as authoritative over the older plan document** — the plan
was written before package 9's own scope was finalised, and package numbering/scope
has already shifted once before in this project (see items above). No `stabilityOf()`
change was made this package; the small-denominator guard gap the plan describes is
real but untouched.

**Decide:** when package 10 is scoped, confirm whether the `stabilityOf()`
salary-override extension belongs there (matching where Tier 6 places "position/
estimate" features) — and if so, treat `phase-4-salary-and-cv-plan.md:491-494` as
already describing the requirement, just under the wrong package number.

---

# Package 9 — Normalisation (Tier 7, adversarial review findings F3/F4)

## 17. Denmark's own two DST concepts don't reconcile, and one subtraction step has to assume a shape the source data doesn't publish

Both findings are about `salary_dk`'s `dispersion_by_year` table (`data/processed/salary_dk.json`,
occupation 2512) and are specific to Denmark — no other source in the spine has this shape of
problem, because no other source publishes two independent DST-style concepts for the same job in
the same file.

**F3 — the country page's native figure and DST's own monthly headline are ~24% apart, for the
same job, same year, same statistical office.**

`salary_dk.json` carries two genuinely different DST series for occupation 2512, 2024:

- `dispersion_by_year["2024"]` — an **hourly** distribution (`mean_dkk_hour`, `median_dkk_hour`,
  `p25`/`p75`, plus `employer_pension_dkk_hour` and `irregular_dkk_hour`), DST's `LONS20` table.
- `standardized_monthly_dkk_by_year["2024"]` — DST's own separately-computed **MDRSNIT**
  ("standardberegnet månedsfortjeneste" — standardised average monthly earnings), `65,504.17`
  DKK/month.

`resolve_country()`'s `native.value` block (`scripts/build_wage_distribution.py:474-475`) is `obs.get(k)`
— the raw hourly figures, unadjusted — because "native" is defined pipeline-wide as "published as
originally reported," and no subtraction happens before that point. That is correct for every
other source. For Denmark specifically it produces a number that silently disagrees with DST's
*own other* headline for the identical occupation and year, once a reader does the annualisation
DST itself does not publish a formula for. Verified live this session, from the committed file, no
part of this is a memorised figure:

| Reconstruction | Formula | Result | vs. MDRSNIT (65,504.17) |
| --- | --- | --- | --- |
| Country page's own native mean, annualised at this pipeline's own DK hours figure | `489.26 × 38.4h/wk × 52 / 12` | 81,412.86 | **+24.29%** |
| Country page's own native median, same hours | `470.53 × 38.4 × 52 / 12` | 78,296.19 | +19.53% |
| Pipeline's `regular_pay` basis (PENS+UREGEL subtracted), median | see F4 for the subtraction | 66,912.77 | +2.15% |
| Pipeline's `regular_pay` basis, mean | — | 70,029.44 | +6.91% |

The `regular_pay`/`total_earnings` comparison figures (the numbers the Explore·Money panel
actually charts) land within a few percent of MDRSNIT — reassuring, and not the problem. The
problem is narrower and easy to miss: **the country page's own native block is the raw,
un-subtracted FORINKL rate**, and nothing on the country page tells a reader that DST publishes a
second, materially different "the number Danes actually recognise" figure for the same job that
doesn't reconcile with it by simple multiplication. A Danish reader who knows MDRSNIT (a commonly
cited figure) and does napkin-math on the site's own displayed hourly rate lands 24% high and has
no on-page signal that FORINKL-hourly and MDRSNIT-monthly are two different DST concepts, not one
figure expressed two ways.

**Not shipped as a fix** — this is a disclosure gap, not a wrong number: every figure the site
computes is traceable and correct for what it claims to be. Fixing it means either (a) a note on
Denmark's native block naming MDRSNIT as a second, non-reconciling DST figure and explaining why it
doesn't match, or (b) switching Denmark's native display to derive from MDRSNIT instead of the
hourly table — which would lose the percentile spread MDRSNIT doesn't carry (see F4) and change
what "native" means for this one country relative to every other source.

**F4 — PENS/UREGEL are subtracted as one flat DKK/hour scalar at every percentile, because DST
does not publish them at any finer grain than a single occupation-wide figure.**

`_figure_for_basis`'s Denmark branch (`scripts/build_wage_distribution.py:342-370`) loops over
`_FIELDS` (`mean, median, p10, p25, p75, p90`) and subtracts the *same* `employer_pension_dkk_hour`
(59.35 DKK/hour, 2024) and `irregular_dkk_hour` (9.06 DKK/hour) from every one of them. That is not
a shortcut this pipeline chose over a better option — `dispersion_by_year["2024"]` has exactly one
`employer_pension_dkk_hour` value and one `irregular_dkk_hour` value for the whole occupation; DST
does not publish either broken out by percentile, so there is no percentile-level figure to use
instead. The pipeline's flat-scalar subtraction is an unstated assumption that PENS/UREGEL are a
constant *krone amount* per hour across the distribution — plausible for UREGEL (irregular/overtime
pay can plausibly cluster near a flat rate), but employer pension contributions in Denmark are
typically a *percentage* of pay under the governing overenskomst, which would make the true PENS
gap in kroner *larger* at p90 than at p10, not identical. If that is right, this pipeline's p90
regular_pay figure is subtracting too little and its p10 figure is subtracting too much — narrowing
the true spread by an unknown, unmeasured amount at both ends.

**Not shipped as a fix** — same reason as package 8's Canada item (12) and this package's own F16
(Norway): re-deriving a percentile-level split DST itself doesn't publish would mean inventing a
distributional assumption and presenting it as sourced data, which is exactly what this pipeline's
own `hours_for()`/`subtract_component()` docstrings say not to do. The method card (`<Derived>`,
gate 13) shows the subtraction step honestly — "470.53 − 59.35 (employer_social_contributions,
sourced from salary_dk's own separately-published figure...)" — but does not currently say that the
*same* 59.35 is being applied at every percentile, which is the part a careful reader would want
flagged.

**Decide:** (1) whether Denmark's native block needs an on-page note pointing at MDRSNIT — the
same treatment as Qatar's `weighting_note` (finding F15, this package) or Ireland's
`explicit_hours` sourcing note, both of which already exist for exactly this "the number needs one
more sentence of context" situation, so this may just be extending that existing pattern rather
than a new one; (2) whether the `<Derived>` chain step for Denmark's subtraction should say "same
rate applied at every percentile — DST does not publish PENS/UREGEL by percentile" explicitly,
rather than leaving that assumption implicit in the fact that the same number appears in every
row's own chain; (3) whether a flat-DKK assumption or a flat-*percentage*-of-pay assumption is
closer to correct — answering that needs either a human reading DST's own PENS/UREGEL methodology
documentation, or contacting DST directly; this pipeline should not guess and present the guess as
sourced.

---

**RESOLVED, package 10, tier 0.2 — F3 reconciled exactly; F4 addressed by disclosure (item (2)
above), items (1) and (3) still stand.**

**F3 is not a real disagreement between two DST statistics.** It was this pipeline comparing two
different LØNMÅL concepts as if they were the same one. DST's LONS20 table carries not two but
**three** relevant series, verified live this package by querying every LØNMÅL code the table
defines (25 codes total, not the 7 this pipeline had been fetching): FORINKL and its siblings
measure earnings per hour **actually worked**; a second, parallel family — **STAND** ("STANDARDIZED
HOURLY EARNINGS") and its own siblings (BASISST, PENSST, UREGELST, NEDREST/MEDIANST/OVREST) —
measures earnings per DK's own **standardised** hour, which nets out paid-but-not-worked time
(holiday, sick leave) the way FORINKL's denominator does not. MDRSNIT is built from STAND, not
FORINKL: `STAND × 160.33 (= 37h/week standardised full-time week × 52 / 12)` reproduces MDRSNIT to
**under 0.002%**, checked across all 7 years (2018-2024) and all 5 DISCO-08 251x occupations this
table publishes — 35 (occupation, year) pairs, worst residual 0.0035%. By contrast FORINKL × 38.4h
(Eurostat's measured hours) overstates MDRSNIT by 23-25% in *every* year — the exact ~24% originally
flagged, now understood as two compounded mismatches (wrong earnings concept, wrong hours figure),
not one unexplained gap.

**Shipped:** `scripts/src_salary_dk.py` now fetches the STAND family alongside FORINKL (kept for
context, no longer used for any figure this site computes) and re-proves the STAND↔MDRSNIT identity
on every harvester run (`_verify_mdrsnit_reconciliation()`, raises if the worst residual across all
years/occupations ever exceeds 0.5% — a live regression guard, not a one-time claim).
`scripts/build_wage_distribution.py`'s `_extract_dk()` switched the primary DK figure from FORINKL
to STAND, with `explicit_hours_by_field` set to DK's own 37h/week standardisation constant (not the
generic Eurostat lookup, which would reintroduce the exact mismatch this fix removes) — the same
`explicit_hours` mechanism package 9 built for Ireland's F2 fix. Denmark's country page and every
wage-panel row now show STAND-derived figures, resolving item (1) above concretely: the native
block no longer disagrees with MDRSNIT, so there is no separate note needed pointing at a
discrepancy that no longer exists — the reconciliation itself (the STAND/MDRSNIT arithmetic and its
residual) is now a real, computed, visible step in Denmark's own `<Derived>` method card, and
`CountryProfile.tsx`'s `<Figure>` for Denmark states the match in its `what` text.

**F4, item (2), addressed:** the DK subtraction chain in `_figure_for_basis` now appends an explicit
`"assumption"` step naming the flat-scalar caveat in full (same wording as this item's own F4
description above), visible in every regular_pay/total_earnings method card, not left implicit.

**Items (1) [now resolved by F3's fix, see above] and (3) still open** — whether a flat-DKK or
flat-percentage assumption is closer to correct for PENS/UREGEL's true shape across the
distribution remains unanswered; DST's methodology page for this is a JS-rendered shell this
pipeline's fetch cannot parse (the same limitation package 9 hit on GENESIS's PDF-only docs), so
this still needs either a human reading DST's own documentation or contacting DST directly. Not
blocking: the assumption is now named, not hidden.

## 18. Norway's bonus was named as available and capturable; what this pipeline actually fetched has no such field

The work order's own §5.1.2 names "Norway's Bonus" as an example of a separately-published,
subtractable pay component, alongside Denmark's PENS — grouping the two as the same kind of case.
They are not, in what actually reached this repository: `data/processed/salary_no.json` (via
`scripts/src_salary_no.py`) carries only `mean`/`median`/`p25`/`p75`/`n_employees` per occupation —
no bonus figure, separate or otherwise. `data/pay_composition.json`'s `salary_no` entry records
`irregular_bonus: true` (bonus is genuinely IN Norway's `Månedslønn` concept by SSB's own
definition — confirmed, not the gap) but `separately_published_components: []`, because there is
nothing in the fetched file to point at.

This surfaced as adversarial-review finding F16 (this package, Tier 7): Norway's row is correctly
*excluded* from `regular_pay` comparisons by `comparison_basis()` (bonus-included sources can't
express bonus-excluded regular_pay without a subtraction this pipeline has no component for) — so
nothing downstream shows a wrong number. The gap is narrower and specifically about capture: SSB
may well publish the bonus component separately (the same way DST publishes PENS/UREGEL
alongside Denmark's FORINKL, in the same source table), and `src_salary_no.py` may simply not have
requested it.

**Not investigated further this package** — re-scoping a harvester mid-Tier-7-remediation, under
the same time pressure this protocol exists to protect against, risks exactly the kind of rushed
change this project's own discipline avoids. `data/pay_composition.json`'s `salary_no.note` records
the gap in full (added this session) so it is not silently resolved by an empty array reading as
"nothing to subtract" when the real state is "nothing was asked for."

**Decide:** whether `src_salary_no.py` should be re-run against SSB's `Månedslønn` table looking
specifically for a bonus breakdown field before package 10 needs a subtracted Norway figure for
anything — and if SSB genuinely does not publish one at the same granularity as the headline
figure, that itself is worth recording as a checked negative, the same way Canada's and Qatar's
`"unknown"` composition fields are (gate 3) rather than left as a bare empty array with no
account of whether it was checked.

---

**RESOLVED, package 10, tier 0.3 — better than a subtraction: SSB publishes the regular_pay figure
directly.**

Checked table 11418's own metadata live (a plain GET, no query — the same check style package 9
used on DST's LØNMÅL): its `ContentsCode` variable carries **seven** values, not the one
(`Manedslonn`) this pipeline had been fetching — `Manedslonn` (total), `AvtaltManedslonn` (basic
salary — bonus, overtime and irregular allowances all OUT), `Uregtil` (irregular allowances),
`Bonus`, `Overtid` (overtime), plus two unrelated age/hours fields. Better than a Denmark-style
subtraction target: `AvtaltManedslonn` is published at the **same measuring-method granularity** as
the total — median, mean, P25, P75, verified live for 2023-2025 — not merely as a mean. Norway
never had Denmark's problem (a flat scalar distorting the spread); its actual gap was under-
fetching, not under-publishing. `Bonus`/`Uregtil`/`Overtid` themselves are checked but genuinely
mean-only (median and P25 are 0 in every year checked — most employees receive none of these in a
given period) — not fetched, and not needed, since regular_pay here is a real published field, not
a subtraction.

**Shipped:** `scripts/src_salary_no.py` now queries both `ContentsCode` values across the same
measuring methods; `scripts/build_wage_distribution.py`'s `_extract_no()` selects between them the
same way `_extract_fi()` already does (Finland's `total_*`/`regular_*` split, package 9) — a native
dual-basis field, not `subtract_component()`. One bug caught and fixed before shipping: both
`mean_nok_month` and `avtalt_mean_nok_month` end in `"nok_month"`, so the generic `_base_obs()`
suffix-matcher would have silently picked whichever key happened to iterate first — the exact bug
package 9 found and fixed for Finland's own total_/regular_ split. Fixed the same way: the generic
native fields are set explicitly from the unprefixed (total) keys, not via suffix match.
`data/pay_composition.json`'s `salary_no` entry rewritten to describe both concepts and the
resolution; the stale note promising this NEEDS-DECISION item (written mid-package-9 remediation,
before the item existed at its current number) now points here correctly.

Norway now expresses `regular_pay` in every wage-panel comparison — six more rows join that basis
than before (Denmark, Finland, Ireland, Sweden were already there; the panel's own gap-card count is
evidence, not asserted here — see `REPORT-P10.md`), exactly the outcome this item's own "Decide"
predicted a real fetch would produce.

---

# Package 10 — Profile, position, estimate

## 19. Germany — `DESTATIS_TOKEN` still absent this session; the registered-account path remains untested

Package 10's work order (tier 0.1) named the same rule package 9's resumed work order established:
this package must be launched through `prompts/run-package-10.cmd`, which sets `DESTATIS_TOKEN` in
the environment. Checked in both the Bash and PowerShell environments this session uses — the
variable is unset in both, confirmed via the environment only (`printf`/`$env:DESTATIS_TOKEN`),
never read from the gitignored runner script that sets it. This session received the work order
pasted directly into chat, the same harness circumstance package 9's resume hit, not a new finding.

Per the work order's own explicit instruction ("do not infer anything about the API or the account
from its absence"), nothing about GENESIS's state is concluded from this. GAST/GAST was not
re-tried either — package 9's resume already tested it exhaustively (3 tables × 4 `area` values, all
denied `Code:15`) and the work order does not ask for a repeat here; re-running it would reconfirm
an already-documented finding, not produce a new one. `scripts/src_salary_de.py` (package 9) is
real, tested and ready — a working personal token only needs to clear the same `data/table` call
GAST was denied on.

**Shipped:** nothing new — Germany stays at zero coverage, same state package 9 left it in.

**Decide:** run this package (or just `scripts/src_salary_de.py`) via `prompts/run-package-10.cmd`
directly so `DESTATIS_TOKEN` is actually present — unchanged from item #15's own still-open
"Decide," now carried forward a second package.

## 20. How "the position" can be both experience-linked and `<Figure>`-sourced — the reading this package committed to

Tier 2's text names a worked example ("P60 of DISCO-08 2512 in Denmark") that implies the position
is personalised to the profile's `yearsProfessional`, then states flatly "the position is sourced,
so it is a `<Figure>`" — while Tier 3's estimate, built from the SAME kind of experience-gradient
math, is explicitly "a `<Derived>`, never a `<Figure>`." Read together with "experience maps to a
position only through a source that actually measures experience," these two rules only both hold
if the position's own experience-personalisation is restricted to arithmetic on two REAL published
numbers from the SAME country's own tables — never the modelled, cross-country gradient Tier 3
uses.

**Shipped, this reading:** the position is the occupation's own published percentile table
(P10/P25/median/P75/P90, `n`, table, year — a real `<Figure>`), with the highlighted percentile
resolved two ways depending on what that specific country publishes:
- **Spain only.** Of the three sources that cross occupation pay with anything experience-related,
  only INE's crosses TENURE — years actually worked, the exact variable Tier 1's form collects as
  `yearsProfessional`. SCB `LonYrkeAlder4AN` and SSB `11658` cross by AGE instead, and the form
  never collects age (deliberately, matching Tier 3's own "age is a weak proxy for experience in
  software" caveat) — so there is no input to bucket Sweden's or Norway's own age bands against at
  all, not just a weaker signal. Spain's profile-personalised position: `yearsProfessional` selects
  a band from INE's own tenure cross, that band's own published wage figure is looked up against
  Spain's OWN percentile table via linear interpolation, and the resulting percentile is the
  position — two real numbers from one office, one arithmetic rank-finding step, no model, no
  cross-country borrowing.
- **Every other country with a distribution** (Sweden and Norway included, despite each having its
  own age cross — see above): the position defaults to the published median (P50) — real, sourced,
  true by definition, not personalised. This is why the worked "P60 in Denmark" example does not
  literally occur under this reading: Denmark has no experience cross of its own, so Denmark's
  position defaults to P50 like every non-Spain country with a distribution — the example is read
  as illustrating the position's citation FORMAT, not a literal claim about what Denmark
  specifically returns. Sweden's and Norway's own age crosses are not wasted: both feed
  `experience_gradient.json`'s context curves (package 10, tier 3) as a same-shape corroborating
  check on the universal gradient, just never as a position input.

The universal, Spain-tenure-anchored gradient (item 19's sibling artifact,
`data/processed/experience_gradient.json`) drives Tier 3's estimate for every country and is never
consulted by the position at all — keeping the `<Figure>`/`<Derived>` boundary exactly where
packages 9's own design put it: a position never carries the authority of a measurement for a
number this pipeline modelled.

**Decide:** whether this reading matches intent, or whether "the position" was meant to be
personalised everywhere via the universal gradient (making it depend on `<Derived>`-class
reasoning) and "sourced" was meant more loosely (citing the underlying published TABLE the
percentile-rank was read against, not asserting the specific percentile itself was unmodelled).
Both readings are defensible from the text; this package chose the one that keeps every existing
component boundary intact without stretching either `<Figure>` or `<Derived>`'s established
contract.
