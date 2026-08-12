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

## 15. Germany, package 9 attempt — DESTATIS_TOKEN unavailable this session; the API path is confirmed deprecated, not just stale

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
