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

**Decided, package 11 tier 3:** no picker. The design brief's own words forbid a
second control on this chart ("which the brief forbids" — this item's own original
text), so adding one to surface the other 22 would violate a binding constraint,
not just a stylistic preference — the brief itself already answers the "picker or
not" question. The 8-of-30 disclosure stays as shipped. Left open, narrower and
genuinely optional: the other 22 metros could still be reachable through the CSV
export or a future data-browser page without touching this chart's own one-control
design — not attempted here, not blocking.

## 3. The mockup's prose says four metros; its data says eight

Recorded as the work order asks. `EX.indeed` in the mockup holds eight metros and
its palette note says "four US metros cannot borrow other countries' colours".
The data won; the prose appears to be a leftover from an earlier draft.

**Decided, package 11 tier 3:** the data stands. The palette note and the actual
`EX.indeed` data both independently agree on eight metros; only the prose
disagrees, which is the signature of a stale draft leftover, not a considered
choice — two sources agreeing against one is decidable without the owner. No
change needed; shipped behaviour (eight metros) already matches the evidence.

## 4. The OECD overlay applies *real* growth to a *nominal* line

The design compounds the OECD's projected **real** GDP growth onto the World
Bank's **nominal** US$ level, draws it as a separate paler line, and hides it
entirely in the yearly-change lens with a chip explaining why. That is the
mockup's own arithmetic and the pre-existing behaviour of `ExploreCharts`.

**Shipped:** exactly that, and the chip in the yearly-change lens states the
mismatch in the design's words.

**Decided, package 11 tier 3, not yet implemented:** yes, the level and indexed
lenses should carry the same caveat — there is no reason the mismatch is worth
disclosing on one lens and not the others; the paler line and "projection →"
label are a weaker signal than the yearly-change lens's own explicit chip.
Deliberately NOT implemented in this package: the change touches
`ExploreCharts.tsx`'s own lens-rendering logic, which this package has not
otherwise read or verified, and a same-session change to unfamiliar chart code
carries real regression risk with no verification budget left to catch it —
exactly the "leave it for a package" case tier 3's own instructions describe.
Small, safe, and well-scoped for a future micro-task: add the existing
yearly-change chip's text to the level/indexed lens branches too.

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

**Decided, package 11 tier 3:** accept the new wording; per-comparison OG images
are not a "maybe later" — they are infeasible on this site's own architecture,
not just undone. `scripts/generate_og_images.py` itself already documents why:
"arbitrary multi-city comparison URLs fall back to default.png — a static host
cannot render one image per permutation" (confirmed still true, this session —
the number of possible city combinations is unbounded, and this site has no
server to render one on demand). The accurate wording already shipped; no
further work needed unless the site ever adds a rendering backend, which is a
much larger architectural change than this one item.

## 8. Sticky header on phones is a CSS impossibility, not an omission

A horizontally scrolling container is also a vertical scrollport, so a
`position: sticky` row inside one pins to *the container* and never to the
viewport. Measured across every overflow combination Chrome accepts: only
`overflow-x: clip` preserves viewport-sticky, and `clip` makes wide tables
unreachable.

**Shipped:** the header row pins under the site header at every width where the
table fits; where it must scroll sideways, the metric-label column pins left
instead.

**Decided, package 11 tier 3:** accept the shipped solution. A JS-synced
duplicate header row is real, non-trivial complexity (a second DOM copy kept in
scroll-sync with the first, its own edge cases on resize/orientation change) for
a CSS limitation that already has a working fallback (the label column pinning
left preserves orientation in the table even without a pinned header row). This
project's own standing principle — don't add complexity beyond what a change
actually needs — argues against building the duplicate-row workaround
speculatively; revisit only if real users report the current fallback is
actually confusing, not preemptively.

## 9. `band` and `lens` stay out of the address until they are touched

**Shipped:** existing URL contract kept. A default link reads
`…/#/compare?places=berlin,toronto` and grows as controls are used.

**Decided, package 11 tier 3:** keep omitting defaults from the URL. Every
package built since this item was raised has independently reached for the same
convention — Position.tsx's own `profileToParams()` (package 10) omits
`?years=5` and `?occupation=isco08:2512` for the identical reason, matching
Compare.tsx's own established `update()` idiom this item already describes. A
convention four packages have now converged on without coordinating is decidable
from that evidence alone, not a live open question.

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

**Decided, package 11 tier 3:** keep `compute.ts`'s own real return values.
Displaying the function's actual output rather than a hand-typed hyphenated
variant is the more correct choice on its own terms — a mismatch between what
the code returns and what the UI shows would be its own small bug, not a
faithful rendering of a deliberate design choice. No evidence anywhere that the
hyphenation was intentional rather than mockup shorthand.

---

# Package 7 — The salary spine

## 12. Canada's NOC 2021 splits one ISCO-08 job into two codes; nothing sums them — RESOLVED in package 12, tier 0

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

**DECIDED, package 12, tier 0: keep both rows, side by side, and explain each.**
Owner's own instruction: Statistics Canada publishes two codes because they pay differently
(Toronto: CAD 56.49/hr vs 48.08/hr, not close enough to treat as noise), so the site shows two,
each with a short sourced line — not summed, not picked-one, not silently disambiguated. The line
(`site/src/data/explore.ts`'s `CA_NOC_DISTINCTION`, shared by the Explore·Money panel and the
country page) is verified directly against noc.esdc.gc.ca's own unit-group profiles, not just
carried over from the crosswalk's own audit note: 21231's own profile requires licensing "to
approve engineering drawings and reports and to practise as a Professional Engineer (P.Eng.)";
21232's profile has no such requirement, only a computer-science-or-equivalent credential — the
real axis NOC draws that ISCO-08 does not, named in the reader's own words, not the crosswalk's.

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

**SUPERSEDED, package 10, tier 4 — built exactly where this item said it belonged.** Package 10's
own work order assigned `stabilityOf()`'s salary-override extension to Tier 4 ("pay against cost"),
matching this item's own prediction. `compute.ts`'s `Budget.salaryUsdYearOverride` field now threads
through `grossFor()`/`netFor()`/`savingsPerYear()`/`yearsToHome()`/`stabilityOf()` — confirmed still
wired correctly this package (package 11 tier 1's own coherence checks exercise this same path via
Sweden/Norway's personalised estimates flowing into `PayVsCost`). No further action.

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

**Triaged, package 11 tier 3:** not an owner decision in the usual sense — no preference, cost or
scope call the owner can make settles which assumption is actually correct; only DST's own
methodology (or DST directly) can answer that. The current disclosed flat-DKK assumption stands as
the pipeline's own honest default until someone reads that documentation or contacts DST — a
research task to flag for whenever there's appetite for it, not a fork this package can close by
picking an answer.

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

---

**RESOLVED, package 11, tier 2 — run through `prompts/run-package-11.cmd` directly, exactly as
items #15 and #19 both asked. The token cleared the wall on the first try.**

Four sessions (packages 8, 9 twice, 10) each independently reached the identical
account-permission wall using GAST/GAST and never got to test a real credential, because each was
launched with the work order pasted into chat rather than through the runner script that actually
sets `DESTATIS_TOKEN`. Package 11's own work order changed the rule that caused this: read the
environment first, and if unset, read `DESTATIS_TOKEN` from `prompts/run-package-11.cmd` directly —
a narrow, explicit, one-credential exception to the environment-only rule, not a general loosening.

Run this way, `logincheck` succeeded and both `data/table` calls returned real content (Code 0) on
the first attempt — no retries needed, no further permission wall. KB10-434's own English label
("Occup. in software development and programming") identified the correct row directly from each
table's own CSV response — the "cannot verify a KldB code without catalogue access" concern that
blocked occupation-row identification in item #15's own account did not end up applying, because
the row didn't need guessing at all once data access worked.

**Shipped:** `scripts/src_salary_de.py` now returns `status: ok` with real KB10-434 figures for both
bases (regular_pay: median 5,851 EUR/month; total_earnings: median 75,854 EUR/year). Wired into
`data/occupations.json` (2-digit confidence, isco08:25 — KldB doesn't reuse ISCO-08's own numbering
the way SE/DK/NO/FI's national codes do, so no numeric concordance exists to claim 4-digit),
`data/pay_composition.json` (a genuine dual-native-basis source, same shape as Finland/Norway), and
`scripts/build_wage_distribution.py`. Germany now renders real figures on its country page and in
the Explore·Money wage panel — it does not unlock position/estimate personalisation on `/position`,
because 62361-0030/-0034 publish median and mean only, no percentile spread, the same
central-tendency-only shape as Australia and Ireland.

One real problem surfaced and fixed in the same session, not left for later: GENESIS's own
`logincheck` response echoes the submitted credential back in its `Username` field, and the first
live call logged that response before anyone expected it to contain the token — see item #25.

**Decide:** nothing further on Germany's own API access — this closes items #14, #15 and #19.
Item #21 (Norway/Finland's opposite native-basis convention) now has a genuine third data point to
consider Germany against, not decided here.

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

**Decide (superseded by the update immediately below — kept for history):** whether this reading
matches intent, or whether "the position" was meant to be personalised everywhere via the universal
gradient (making it depend on `<Derived>`-class reasoning) and "sourced" was meant more loosely
(citing the underlying published TABLE the percentile-rank was read against, not asserting the
specific percentile itself was unmodelled). Both readings are defensible from the text; this
package chose the one that keeps every existing component boundary intact without stretching
either `<Figure>` or `<Derived>`'s established contract.

---

**Update, same package, tier 7 — the Spain-only personalisation above was itself unsound, and has
been removed. The position is now the published median (P50) for every country, with no exception.**

An independent adversarial review (this package's own gate 14, findings F2/F2b/F3) found that the
"two real numbers from one office" claim above does not hold. INE's tenure cross
(`data/processed/salary_es.json`'s `broader_category_context`) is for CNO-11 **"Scientific and
intellectual technicians and professionals"** — doctors, lawyers, teachers, engineers, a population
whose mean gross salary (€34,505.80) sits ~13.95% BELOW the IT-specific occupation
(`it_professionals`, mean €39,318.16) the resulting band figure was being ranked against. This is
not "one office, one population, two figures" as originally shipped and originally justified here —
it is one office, TWO populations, with the relative-premium-transfers-but-absolute-level-doesn't
assumption (already disclosed honestly in `experience_gradient.json`'s own `meta.source` field: *"NOT
IT-specific, the finest grain INE crosses tenure at"*) silently doing more work than the `<Figure>`
component's "official" confidence level accounts for.

**The consequence was concrete, not theoretical.** Because the position (a step function over 6
discrete INE bands) and the estimate (a continuous shift of the SAME gradient) both fed from the
same tenure cross but combined it differently, the two numbers shown side by side for a Spanish
profile could — and did — disagree about the same person in the same table: at 3 years, the shipped
position read "P26" while the shipped estimate, ranked against its own distribution, actually sat
at P33; at 20 years, "P56" beside an estimate sitting at P65. A reader comparing the two columns had
no way to know they could contradict each other, and no disclosure said so.

**Shipped:** `computePosition()` (`site/src/data/profile.ts`) no longer branches on
`row.country === 'ES'` at all — it always returns the published median, for every country the
crosswalk accepts. There is no IT-specific tenure cross to rank against instead (INE does not
publish one), so the honest fix is not-personalising rather than personalising with a caveat this
component's own contract has no room to carry. The `<Figure>`/`<Derived>` boundary point from the
superseded reading above still holds — it now holds trivially, because the position never touches
the gradient at all. Spain's ESTIMATE (`computeEstimate()`) still uses the same tenure-anchored
gradient — appropriate there, since a `<Derived>` already discloses "this is a method, not a
source" — and its own chain step now states the population mismatch explicitly rather than only in
`experience_gradient.json`'s own metadata: *"Spain's own INE tenure cross... 'Scientific and
intellectual technicians and professionals' — a broader population than this occupation; the SHAPE
of the tenure-pay relationship is assumed to transfer, the absolute wage level is not."*

**Decide (superseded by the update immediately below):** whether a genuinely IT-specific experience
signal is worth pursuing for a future package (INE does not publish tenure crossed with IT-specific
CNO-11 codes at any depth this pipeline has found; a different source might), or whether "position
is always the published median, full stop" should stand as this feature's permanent design.

---

**Update, package 11 — "always the published median, full stop" was itself an over-correction.
The position personalises again, but only for Sweden and Norway, and only via each country's own
same-population cross — never Spain's, never a cross-country curve.**

Package 10's tier-7 fix above was diagnostically correct (Spain's tenure cross IS a different
population) but drew the remedy too broadly: it removed personalisation for every country, not just
the one where the premise failed. The result shipped to production: `computePosition()` took a
`profile` parameter it never read, so the years input moved the estimate while the position sat
frozen at P50 for all fifteen countries, always — the feature's own primary number stopped
responding to its only input. Package 11's own work order named this precisely: "the position is
degenerate."

**Re-examined, country by country, before shipping anything:** Sweden's SCB `LonYrkeAlder4AN`
(`age_by_year` in `salary_se.json`) and Norway's SSB 11658 (`age_at_quarter` in `salary_no.json`)
both cross the SAME 4-digit occupation code, at the SAME statistical office, as their own
`dispersion_by_year` percentile table — verified directly against each file's own `meta` block, not
assumed. This is the "two real numbers from one office" property the ORIGINAL (Spain) reading above
argued for, genuinely true here where it was not for Spain. Both now personalise: the position ranks
a shifted value against the country's own table (still `<Figure>`, extended with a new `steps` field
so the arithmetic is visible — see `site/src/components/Figure.tsx`), the estimate states it
(`<Derived>`, unchanged register).

**The universal curve is retired, not fixed.** Package 10's `experience_gradient.json` applied
Spain's own tenure-cross shape to every comparable country's estimate — the identical
population-borrowing mistake the position fix above had just been built to prevent, just moved to
the estimate and never caught until this package's own re-examination. `scripts/
build_experience_gradient.py` now writes `by_country: {SE: ..., NO: ...}` only; no country's
estimate or position ever consumes another country's cross. Spain's own tenure data remains real,
committed, and undisturbed in `salary_es.json` — simply not read by this file anymore. Coherence
between position and estimate (do they agree about whether a country personalises) is now
structural: both call the same `_countryGradient()` lookup on the same data, so there is no code
path where they could disagree — and both derive from the identical shifted value (position ranks
it, estimate states it), removing the OTHER problem the tier-7 update above found (a discrete
position and a continuous estimate disagreeing about the same profile even when the population
matched).

**A new assumption this package adds, disclosed on its own: converting years of experience to an
assumed age.** SE's and NO's own crosses bucket by AGE, not tenure — the profile form collects
years of professional experience. These are different axes (a 2-years-experienced developer is not
2 years old), and an early version of this package's own fix conflated them directly, which meant
every realistic years value fell below the youngest age band's own midpoint and clamped identically
regardless of years — caught by running gate 1's own three-year check live, not by inspection. Fixed
by adding an explicit, disclosed conversion (`ASSUMED_CAREER_START_AGE = 22` in `profile.ts`, the
standard labour-economics "potential experience" convention: age minus schooling minus six, fixed
at a bachelor's degree) — see item #24 below for the full account and what would change it.

**Decide:** nothing blocking — this is shipped. Open question for a future package: whether
`ASSUMED_CAREER_START_AGE` should vary (by country's typical university length, or by an education
level the profile form doesn't currently collect), covered in #24.

## 21. Norway's, Finland's, and Germany's own "native" wage figures use opposite conventions for which basis they represent

Package 10's adversarial review (finding F12) found that `_extract_no()` (Denmark's own tier-0.3
fix, this package) sets the generic native `mean`/`median`/`p25`/`p75` fields from the UNPREFIXED
Manedslønn keys — SSB's own total-earnings figure, bonus included — while `_extract_fi()` (package
9) sets the same generic fields from the `regular_` prefix — Tilastokeskus's bonus-EXCLUDED figure,
specifically because package 9's own docstring reasoned that regular_pay matches "the panel's own
stated default." Both choices are individually documented and individually defensible; the two
together mean the Explore·Money wage panel's "native currency" column — and now this package's own
Estimate column — silently mixes bases across countries: Finland's native figure excludes the
bonus, Norway's includes it, Denmark's STAND figure includes employer pension and irregular pay
(package 10, tier 0.2), Spain's is total_earnings. A reader comparing native-currency figures
across the panel has no on-page signal that "native" does not mean the same thing in every row.

**Not resolved this package** — picking ONE convention (e.g., always regular_pay when a source can
express it) would mean revisiting Denmark's, Finland's and Norway's own `_extract_*()` functions
under the same time pressure this project's protocol exists to protect against, and Denmark's own
figure (STAND) cannot cleanly express regular_pay as its NATIVE default at all (it is derived via
subtraction, not a native field — see item #17). **Shipped instead:** the Estimate column's method
card (`site/src/data/profile.ts`) already names which basis a USD figure resolved to when it falls
back from regular_pay to total_earnings (see item #17's tier-0.2 discussion); native-currency
figures do not yet carry an equivalent per-row basis label.

**PACKAGE 11 UPDATE:** Germany joined as a third dual-basis source this package (`_extract_de()`,
`scripts/build_wage_distribution.py`) — Destatis's own two tables give it a genuine regular_pay/
total_earnings split, the same shape as Finland's and Norway's. Its own native `mean`/`median` are
set from regular_pay (matching Finland's convention, not Norway's — see the module docstring for
why: `-0030`'s own bonus-excluded figure needed annualising anyway, and the annual `-0034` table was
the more natural total_earnings partner). This makes the inconsistency a three-way split, not two —
named here rather than left implicit, since finding F18 (this package's own adversarial review)
caught the heading above still reading as if only two countries were involved. Still not resolved;
see item #17's tier-0.2 discussion for Denmark's own reasoning.

**PACKAGE 11 REMEDIATION UPDATE (finding F13):** this same basis inconsistency reaches further than
the panel's own display — `computeEstimateUsdYear()` (`profile.ts`, Tier 4's own pay-vs-cost path)
shifts Norway's `usd_regular_pay` combo using a gradient (`experience_gradient.json`) built from
SSB's own `total`/Manedslønn-basis premiums (the same total-earnings figure this item's own body
names above). The premium's own basis and the figure it's applied to disagree for Norway
specifically, the identical shape of problem finding F1 fixed for Sweden's position/estimate — but
NOT the same fix: F1 was a genuine bug (SE's cross and SE's shifted figure were UNINTENTIONALLY on
different bases, with no reason given). Norway's case is different in kind — `_extract_no()`
deliberately sets NATIVE to the total basis (this item's own body, above), so `usd_regular_pay`
choosing a DIFFERENT basis than NATIVE for the USD path is itself downstream of the very
inconsistency this item already tracks, not a separate bug with an obvious fix. Escalated here
rather than fixed unilaterally: resolving it means picking a basis-consistency rule for Norway's USD
path specifically, which is exactly the kind of site-wide-convention call this item's own "Decide"
below already asks for — fixing this one instance first would pre-empt that answer rather than wait
for it.

**Decide:** whether the panel needs a per-row basis chip (matching the site's existing confidence-chip
vocabulary) making explicit which of regular_pay/total_earnings/"includes employer contributions"
each native figure actually represents, or whether unifying every source onto one convention (at
the cost of some sources no longer showing their own most naturally "native" figure) is the better
fix.

## 22. A flat net-take-home percentage is applied to a salary that can range 2.5x under a user-chosen percentile

`compute.ts`'s `netFor()` applies one `net_pct` scalar per city (e.g. Valencia 72%, Copenhagen 64%)
regardless of the salary passed through it — a pre-existing simplification for every city-published
figure on this site (new_grad/mid/senior bands already share one `net_pct` each), which package
10's `Budget.salaryUsdYearOverride` (tier 4) makes more consequential: a profile's own estimate can
range from a P25-adjacent floor to a +36% ceiling for the same country, a wider spread than the
three fixed bands a city's own `net_pct` was calibrated against. Real income tax in every one of
these fifteen countries is progressive — the true net percentage is lower at the top of that range
than at the bottom — so `stabilityOf()`'s own gate-9 demonstration (Valencia, $56,247 "stable") is
itself understating the true net figure by an unknown, unmeasured amount. Found by the adversarial
review (finding F13), not by this package's own testing.

**Not shipped as a fix** — modelling progressive tax brackets for fifteen countries is a real,
substantial undertaking (bracket schedules, allowances, regional variation within some of these
countries) and out of scope for a package whose own stated bar is "no AI, no network, three fields."
`net_pct` staying a flat-per-city scalar is an existing site-wide limitation this package inherited
and made more visible, not one it introduced.

**Decide:** whether a progressive-tax model belongs in a future package (the data — bracket
schedules per country — is itself a real harvesting effort, not a quick lookup), or whether a
disclosure note on `Budget.salaryUsdYearOverride`-driven figures ("net percentage calibrated
against this city's own published salary, not yours") is the more proportionate fix in the
meantime.

## 23. `_verify_mdrsnit_reconciliation()` re-proves the STAND/MDRSNIT identity against whatever data the harvester actually used this run — cached bytes included

Item #17's tier-0.2 resolution says `scripts/src_salary_dk.py` "re-proves the reconciliation on
every harvester run... a live regression guard, not a one-time claim." That is true of the
CHECK — it runs unconditionally, against real data, every time `run()` executes, and genuinely
raises if the worst residual ever exceeds 0.5% (constructed and confirmed live this package,
before this item existed: a fabricated MDRSNIT mismatch raised correctly, a genuine match stayed
silent). What the adversarial review's finding F20 correctly narrows is which DATA it checks:
`_query()` returns the cached `data/raw/salary_dk/LONS20.json` whenever that file already exists,
so a run against a warm cache re-verifies the PIPELINE's own parsing and arithmetic, not whether
DST has revised its own published figures since the cache was last cleared.

**Not a flaw specific to this check** — every assertion in this pipeline verifies whatever data is
currently fetched-or-cached, never "the live internet, always, regardless of cache state"; that is
true of every `validate_data.py` assertion back to package 7. Recorded here only because item #17's
own wording ("every harvester run") could be read as a stronger claim than the check actually
makes.

**Decide:** nothing required — this is a documentation-precision note, not an open question. Worth
remembering if `data/raw/salary_dk/` is ever cleared as part of a scheduled re-verification: that is
the specific circumstance under which this check would catch a genuine DST revision, not merely a
pipeline regression.

## 24. Converting years of professional experience to an assumed age for Sweden's and Norway's own age-banded crosses — `ASSUMED_CAREER_START_AGE`

Package 11's revived personalisation for Sweden and Norway (item #20's own package-11 update, above)
ranks/shifts using SCB's and SSB's own age bands, but the profile form collects years of
PROFESSIONAL EXPERIENCE, a different axis SCB/SSB do not publish a cross for at all. Some conversion
from years to an assumed age is required before either country's curve can be consulted — there is
no way around picking SOME assumption here, since age and years-of-experience are not the same
number and this pipeline has no way to ask the user their actual age (the form deliberately doesn't
collect it, matching the site's own "collect only what's used" discipline).

**A real bug caught before shipping, not a theoretical concern.** An earlier version of this
package's own fix skipped the conversion entirely — it interpolated `yearsProfessional` (2, 8, 20 in
gate 1's own test) directly against the age bands' own midpoints (21, 29.5, 39.5...). Every
realistic years-of-experience value is below the youngest band's own midpoint, so every profile
clamped to the identical lowest-band premium regardless of years — Sweden showed P10 at 2, 8, AND 20
years, the exact "position ignores its only input" defect this package exists to fix, just
reintroduced one level down. Caught by running gate 1's own three-different-percentiles check live
against the actual page, not by code review.

**Shipped:** `site/src/data/profile.ts`'s `ASSUMED_CAREER_START_AGE = 22` — the standard
labour-economics convention for "potential experience" (age minus years of schooling minus six),
fixed at a bachelor's degree finishing at 22. `assumedAge = yearsProfessional + 22`, disclosed as
its own numbered chain step in both the position's method card (`<Figure>`'s new `steps` field) and
the estimate's (`<Derived>`'s chain) — "8 years of experience -> assumed age ~30 (career start at
22, a stated assumption)" — never silently folded into the shift arithmetic.

**Decide:** whether a single constant is the right permanent design, or whether it should vary —
options, roughly ascending in complexity: (a) leave it, one number, disclosed, the same for every
profile regardless of country or claimed education level (current state); (b) vary by country
(Sweden's typical university length differs from Norway's, though not by much); (c) let a future CV
path (package 12) supply `education_level` from the structured profile schema
(phase-4-salary-and-cv-plan.md §3.1 already includes this field) and derive career-start-age from it
(bachelor's ~22, master's ~24, PhD ~28) rather than assuming one universally. Option (c) is the most
accurate but depends on package 12 shipping first and on OECD/national typical-completion-age data
this pipeline has not sourced; not attempted here.

**Triaged, package 11 tier 3:** option (a) — the current shipped state — stands, no owner input
needed right now. Options (b) and (c) are genuinely better but not choices available yet: (b) has no
sourced data behind it (no OECD/national completion-age figures fetched), and (c) depends on package
12 existing first. This is not a fork in the road today, just a documented, disclosed placeholder
with a natural, obvious revisit point (whenever package 12's own CV path ships) — closer to a
tracked TODO than a live decision.

## 25. `DESTATIS_TOKEN` may have been exposed in this session's own tool-call transcript — consider rotating it

Package 11's own work order relaxed the environment-only rule for this one credential, explicitly
authorising `scripts/src_salary_de.py` to read `DESTATIS_TOKEN` from `prompts/run-package-11.cmd`
when the environment doesn't have it, with the condition that the value itself is "never echoed,
never written to a file, a log, a commit message, the report, or a data file."

**That condition was violated once, briefly, before this item existed.** GENESIS's own
`helloworld/logincheck` response echoes back whatever was submitted as its `username` field — and
per the API's own documented convention ("not necessary when entering token instead of user name"),
the token IS submitted as the username. The first live call this package made logged that response
verbatim for diagnostics, which put the token's own value into this session's tool-call output — a
part of the conversation transcript, not a file this repository tracks.

**Checked immediately, in this order:**
1. `data/processed/salary_de.json` — the committed, pushed data file — never stored the raw
   `logincheck` response at all (only a `logincheck_ok` boolean); grepped for `"Username"` after the
   run: zero matches. The token never reached anything this repository tracks or that gets pushed to
   GitHub.
2. `scripts/src_salary_de.py` fixed in the same session, before any further calls: a `_redact()`
   helper now strips `Username`/`Password`/`username`/`password` keys from every response this file
   logs OR persists, applied at all three sites that touch a raw GENESIS response. Re-run
   immediately after the fix — confirmed the credential no longer appears in output at all.

**Not fixed by code, because it can't be:** the ALREADY-LEAKED value sitting in this session's own
transcript. That transcript is not a file in this repository and this pipeline has no access to it
after the fact — there is nothing scripts/validate_data.py or any commit can do about content that
already left through a channel this codebase doesn't control.

**Decide:** whether to rotate `DESTATIS_TOKEN` (generate a new one from the Destatis GENESIS account,
replace it in `prompts/run-package-11.cmd`) given the exposure above. The practical blast radius is
narrow — a read-only credential against a public government statistics API, not a payment method or
an account with write access to anything — but the decision to accept that risk or not belongs to
the account holder, not this pipeline. The user was told directly, in-session, at the moment this was
found, not just here.

---

# Package 12 — the postings panel

## 26. Four providers probed and confirmed live but not wired into a harvester this package

The work order's own Tier 1.2 named nine platforms to probe. Three are fully wired (Ashby,
Greenhouse, Lever — the "verified" tier) plus Teamtailor, USAJOBS and Hacker News (added this
package once probed). Four more were probed and a real verdict recorded, but no company-list
harvester was built for them this session:

- **Workday** — confirmed genuinely alive, unauthenticated, real structured job data
  (`{tenant}.wd#.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`). **No structured compensation
  field exists anywhere in the response** — verified against a real posting — but pay-transparency-
  state postings (California confirmed live: Qualys, Foster City) carry a real, parseable range as
  PROSE inside `jobDescription`, the same free-text-extraction shape this package already builds for
  Hacker News. Not wired because company discovery is qualitatively harder than the other providers:
  every company has its own `wd#` (1 through 500+) AND its own site name, neither guessable from the
  company name the way `{company}.domain.com` is for every other provider here — a real engineering
  cost (search-based discovery, not construction), not a probe-budget shortfall.
- **SmartRecruiters** — confirmed live, unauthenticated (`api.smartrecruiters.com/v1/companies/
  {id}/postings`), matches the work order's own prior finding: no compensation field, ever.
- **Workable** — confirmed live, unauthenticated (`apply.workable.com/api/v1/widget/accounts/
  {slug}?details=true` — a fake slug 404s, a real one 200s even with zero current postings, which is
  how "live" was confirmed without a company that happened to have open roles at probe time). No
  compensation field, matching the work order's own prior finding and one independent source
  (dev.to's own field-by-field writeup).
- **BambooHR** — confirmed live and public (`{subdomain}.bamboohr.com/careers/list`, real JSON,
  `{meta, result}` shape, no auth) — genuinely different from the "internal endpoint, undocumented,
  changes between releases" characterisation some third-party scraper docs give it. One real
  customer verified (`zapier.bamboohr.com`, 0 current postings — endpoint confirmed working, job-
  level schema including compensation NOT independently confirmed against a company with open roles
  within this session's own probe budget).

Personio and Recruitee: endpoint FORMAT documented from each platform's own support docs
(`{subdomain}.jobs.personio.com` / `.jobs.personio.de`; `{company}.recruitee.com/api/offers/`), but
no live customer subdomain confirmed working this session — every guessed slug either redirected to
the vendor's own marketing site (Personio) or 404'd (Recruitee).

**Decide:** whether a follow-up package should build harvesters for Workday (real engineering cost:
company discovery, then a Workday-specific text-extraction path mirroring the HN parser but scoped
to the far narrower "pay range" phrasing pay-transparency postings actually use) and/or SmartRecruiters
/Workable/BambooHR (lower cost: same shape as the existing harvesters, just no compensation payoff
for the first two, and BambooHR needs real customer subdomains found first). Jobvite and JazzHR are
NOT included in this question — see item #27, they are confirmed not usable at scale, not merely
unbuilt.

## 27. Jobvite and JazzHR — confirmed not usable at scale, not merely unprobed

Distinct from item #26 above: these two were probed and the answer is a real "no," not "not yet."
**Jobvite**: has a REST API and an optional published-jobs feed, but the feed is off by default per
customer and most customers never turn it on — there is no guessable public endpoint the way every
other provider in this package has. **JazzHR**: the public board (`{slug}.applytojob.com`) is
server-rendered HTML with the job list baked into the page markup; the real API and XML feed both
require a customer-specific key. Neither has a path to bulk, unauthenticated, cross-company
harvesting the way Ashby/Greenhouse/Lever/Teamtailor/SmartRecruiters/Workable/BambooHR/Workday all
do. Not re-probed in a future package unless a company-specific key becomes available through some
other channel — this is a structural "no," not a session budget limit.

## 28. Greenhouse's own `pay_input_ranges` has no period field — this pipeline infers hourly vs. annual from magnitude

Found live, caught before shipping (not by the adversarial review): the SAME company (10beauty)
posts ranges shaped like `$100,000-$125,000` (clearly annual) and `$30.00-$35.00` (clearly hourly)
under the identical `"title": "Salary Range"` label, with nothing else in Greenhouse's own API
response distinguishing them. `scripts/src_postings_greenhouse.py` now infers hourly when the range's
own upper bound is under $1,000 (no real full-time annual salary is that low; no real hourly wage is
higher) — a disclosed, reasoned inference, not a silent guess, and the `raw_text` field says so on
every affected posting.

**Decide:** whether $1,000 is the right threshold, and whether a role genuinely paid in the
$1,000-$5,000 (per year OR per hour — both are inside a gap this heuristic cannot resolve either
way) range is common enough on Greenhouse to be worth a smarter check (e.g. reading the job's own
`employment_type` field, not yet fetched by this pipeline, which might carry "Part time"/"Contract"
as an independent signal to combine with magnitude). None observed live in this session's own
sample; the residual risk is theoretical today, not demonstrated.

**Package 13 update:** an independent adversarial review re-derived this same gap without reading
this entry first (constructed `$3,000-$4,500`, a plausible real monthly range, and confirmed the
current heuristic labels it annual — 12x understated) — corroborating evidence the gap is real, not
new information changing the decision. Also notes there is currently no THIRD bucket at all for
"month" in Greenhouse's own inference (only hour/year), unlike Lever, which does carry real
`per-month-salary` postings in this pipeline's own committed data (e.g. PHP 80,000-90,000) — so a
monthly Greenhouse range is not a hypothetical shape this pipeline has never seen elsewhere, just
one Greenhouse's own magnitude heuristic cannot currently express even if correctly identified. Not
fixed this package: this is the exact "escalate methodology trade-offs, don't unilaterally fix
them" case, and the decision above is still open. `scripts/tests/test_pay_period.py` gained a test
pinning the CURRENT, disclosed boundary behaviour (so a future change to the $1,000 threshold is a
deliberate, visible diff, not a silent one) rather than a fix to the heuristic itself.

## 29. Gig-platform / part-time-freelance postings appear in the panel alongside full-time roles — is that the right scope?

The seed-hint candidate list (github.com/Feashliaa/job-board-aggregator) surfaced at least one
company (10xteam, Ashby) whose own postings are short-hours freelance "AI Trainer" gigs (8-20
hrs/week, task-based), not full-time software engineering roles — a meaningfully different labour-
market segment from the "software developer" scope this whole site is otherwise built around
(explore/position/compare all key off isco08:2512). Nothing in this package's own harvesters filters
by employment type or role category (that is what tier 3's classifier is FOR, but tier 3 was not run
live this session — see item #30) — so gig-economy postings currently sit in the same list as
Stripe's and Anthropic's own full-time openings, distinguishable today only by reading each
posting's own title.

**Decide:** once occupation classification is live (item #30), should postings the classifier can't
place in software/ICT categories be dropped from the panel entirely, kept but visually distinguished,
or left as-is (the panel's own "Search title" filter already lets a reader exclude them by keyword,
imperfectly)? A product/scope call, not a data one.

## 30. Occupation classification (tier 3) is built but was not run this session — no `GEMINI_API_KEY` in this environment — RESOLVED, the "no code change needed" claim below was wrong when first written

`scripts/classify_postings.py` and `scripts/postings_classify_config.yaml` exist, follow the
data-scraper-agent skill's own batching discipline (25 postings/call, a model fallback chain, a
response schema with no numeric field of any kind — see the script's own module docstring for why
this is safe: a posting's TITLE is public business information, not personal data, so the paid-tier
requirement `phase-4-cv-setup-checklist.md` sets for the CV feature does not apply here), and fail
soft (exit 0, nothing classified, status recorded) when the key is absent — checked, and it was
absent in this session's own environment, the same "environment-only, no silent skip disguised as
success" discipline this pipeline already applies to `DESTATIS_TOKEN`. The postings panel's own
"Category" filter is consequently not yet wired (`Postings.tsx` says so directly under the filter
row) — level (guessed from title) and country/remote filtering all work today without it.

**This item originally closed with "set `GEMINI_API_KEY` and this runs automatically... no code
change needed" — found FALSE by this package's own adversarial review.** `classify_postings.py`
wrote `data/processed/postings_classifications.json` and nothing anywhere ever read that file back
into `postings.json`'s own per-posting `occupation` field — `grep`ing the whole repo for
`postings_classifications` outside the writer itself returned nothing. Setting the key alone would
have produced a classifications file the site never consumed; the Category filter would have stayed
empty regardless.

**Fixed:** `classify_postings.py` gained `_merge_into_postings()`, called right after a real
classification run succeeds — reads `postings.json`'s own existing envelope, sets each classified
posting's own `occupation` field in place, writes the same file back (not a new source_id, an
enrichment of `build_postings.py`'s own output). Verified against a scratch copy with synthetic
classifications (two postings updated, a third correctly left untouched, `seed_companies` and every
other envelope field preserved) — not run against a real Gemini response this session, since the key
is still absent; the merge logic itself is what needed fixing and is now tested.

**Decide:** set `GEMINI_API_KEY` (as a repository secret, consumed by `.github/workflows/postings-
refresh.yml`'s own weekly run, which already reads it and no-ops cleanly without it) and this now
genuinely runs and merges automatically on the next scheduled refresh, matching what this item
originally (incorrectly) promised. The postings panel's own "Category" filter UI is still not
built — occupation data merging in is necessary but not sufficient for that; a real follow-up, not
attempted here since there is no live classified data this session to build or test it against.

## 31. YC's Work at a Startup and Wellfound (tier 1.3) — both probed live, both closed, neither wired

The work order's own §1.3 named these alongside USAJOBS and HN as supplementary sources to probe,
explicitly authorising "skip if auth-required." Both hit that condition, verified live rather than
assumed from general knowledge:

- **Wellfound** (`wellfound.com/jobs`) — loads Cloudflare Turnstile on first request
  (`turnstileLoad = function() {...}` present in the raw HTML before any JS executes). This is an
  explicit bot-detection gate, not a soft rate-limit — bypassing Turnstile is outside this project's
  own standing rules regardless of what the work order authorises. `angel.co` (Wellfound's old
  domain) redirects into the same gated surface. No API path attempted or exists to probe further.
- **Work at a Startup** (`workatastartup.com`) — `/api/jobs` 404s; no public jobs API exists.
  The `/companies` page returns HTTP 200 but is a login-gated Rails+Vite app: the raw HTML carries
  zero embedded job or company JSON (no `__NEXT_DATA__`, no `data-react-class`, no inline job array)
  and the page's own `paths.login` field points at `account.ycombinator.com/magic?continue=...` — YC's
  passwordless magic-link account flow. Job content loads client-side after that login, not before.
  Separately, `api.ycombinator.com/v0.1/companies` IS live and public (verified: real JSON, YC's own
  funded-company directory — id/name/slug/website/oneLiner/tags) — but it is a company directory,
  not a jobs endpoint (`/v0.1/jobs` 404s, and there is no per-company detail route either). Real,
  live, and unauthenticated, but the wrong shape of data for this package's own purpose.

**Not wired** — both hit the work order's own pre-authorised "skip if auth-required" condition
cleanly. `api.ycombinator.com/v0.1/companies` is a legitimate, separate finding: it could seed
company slugs to try against Ashby/Greenhouse/Lever (YC-funded companies using those ATSs) the same
way the third-party aggregator list does for Tier 2 — a real, if minor, incremental idea, not
attempted here since the existing seed hints already carry the harvest well past the work order's own
500-board target without it.

**Decide:** whether a future package should use `api.ycombinator.com/v0.1/companies`'s own slug list
as one more Tier-2 seed-hint source (still re-verified live per-token before counting, same as every
other seed hint) — low cost, uncertain incremental yield since YC companies large enough to run their
own ATS board are likely already reachable through the existing aggregator-based hints.

## 32. 16 of 14,813 postings-with-compensation (0.11%) carry an implausible min/max ratio — traced to the SOURCE ATS's own structured field, not this pipeline's parsing

Found while hand-verifying postings against live URLs for gate 11 (`REPORT-P12.md`), not by a
dedicated check built for this: filtering the final merged `postings.json` for `max/min > 15×`
surfaces 16 records across three providers (10 Ashby, 5 Lever, 1 HN — re-measured after the
country-resolver harvester re-runs this package's own adversarial review triggered; the count and mix
shifted slightly, one new instance surfaced, none of the originally-found ones disappeared). Traced
each back to its own raw cached API response directly, not assumed:

- **`bfsaulhotels` (Lever), 3 postings** — `min: 1` (e.g. "Breakfast Attendant... 1-15.5 USD hour").
  The same company's other 100+ postings in this pipeline are clean, sensible, well-formed hourly and
  annual figures — this looks like a three-keystroke slip on the employer's own end (meant to type a
  real minimum, typed "1"), not a pattern across their whole board. Deliberately NOT caught by the
  compensation-guard fix elsewhere in this package (Ashby/Lever's own `$0` guard, see the "Bugs
  caught and fixed" section) — `min: 1` is a real, non-zero, if implausible, value, a different
  failure shape from the `$0` figures that guard targets.
- **`doppel`, `foley` (Ashby), 1 posting each** — minimums three orders of magnitude below their own
  maximums (`$169`–`$396,360`; `$80`–`$90,000`) in a shape that reads as a missing "000" on the
  employer's own end.
- **`amityfdn` (Lever), 1 posting** — `43.36-4336 USD (per-hour-wage)`; no real hourly wage is
  $4,336/hour.
- **`cagents` (Lever), 1 posting, new since the original 15** — "Validation Engineer":
  `400100-17171000 INR`. The same company posts several other "Commissioning (Cx) Engineer" roles
  with the identical minimum (400100) and a maximum of `1717000` — an order of magnitude smaller and
  consistent with each other — reading as the same "extra digit typed into the max" shape as
  `doppel`/`foley` above, on a different company.
- **HN, 1 posting** — `"$6–$253K"` literally in the source comment's own text (an automated listing
  bot's own apparent formatting error, not this pipeline's extraction — see gate 11's own account).
- **`coursecareers` (Ashby), 8 postings** — `"$50 – $1,000 per month, Commission Based"`. Different in
  kind from the rest of this list: a 20× commission-driven range is a real, plausible shape for
  commission-based pay, not obviously wrong — included in the raw count above for completeness, not
  because it looks like an error.

In every non-commission case, the code reads `min`/`max` from the identical single structured API
field pair every time (confirmed by re-reading the raw cached bytes directly) — there is no code path
where this pipeline could cross wires between two different fields or two different postings. The
implausible value is what the ATS itself returned, i.e. what the employer's own posting form
submitted.

**Not filtered or corrected** — replacing an implausible `min` with a guessed plausible one (e.g.
assuming a dropped "000") would mean inventing a number and presenting it as sourced, the exact thing
this pipeline's own design (`normalise.py`'s "never synthesise a component no source measured", the
Greenhouse magnitude-heuristic disclosure in item #28) already refuses to do elsewhere. At 0.11% of
postings-with-compensation, this is a real but narrow residual, not a systemic issue.
`Postings.tsx`'s own compensation cell now renders `raw_text` as its own hover `title` attribute
(fixed this package — this item's own text originally claimed it was already shown, which this
package's own adversarial review found was not true; the field existed but was never rendered
anywhere), so a reader who hovers one of these 16 rows sees the same "$1-$15.50/hour" oddity a human
reading the original posting would — hover-only, matching this site's own existing pattern for
secondary detail (SVG `<title>` tooltips elsewhere), not a substitute for a visible flag if one is
ever built (see the "Decide" below).

**Decide:** whether a lightweight plausibility flag (e.g. `confidence: "implausible"` alongside the
existing `structured`/`parsed_text` values, surfaced as a visual note rather than hidden) is worth
adding for future harvester runs — cheap to add, but a genuinely new piece of UI vocabulary this
package did not scope, and 16 records is too small a sample to design a general threshold from with
confidence (a $1/hour minimum is obviously wrong; is a 15× ratio the right general cutoff, or would
it flag legitimate commission-heavy roles like `coursecareers`'s own 8 postings above as false
positives? Untested at any real scale).

Also add the new `_word_match()`-ordering residual (item #33 below) as a small, related open
question worth deciding together with this one, since both are "this pipeline's own checking order,
not a missing signal, occasionally picks the less-likely of two real answers" cases at a similarly
small scale.

## 33. `country_from_location()` used unanchored substring matching — real postings were misassigned to the wrong country, including onto the new advertised-pay chart's own displayed numbers — RESOLVED, fixed this package

Found by this package's own independent adversarial review, not by any check this pipeline had run
before shipping: `scripts/postings_common.py`'s own location resolver matched country names as a
bare substring of the lowercased location text (`if name in low: return iso2`), with no word
boundary. Verified directly against the real committed dataset, not assumed:

- **"Atlanta, Georgia"** (and 142 other real US-Georgia postings — Athens, Savannah, Fort Benning,
  Robins AFB, ...) resolved to **GE** (the country Georgia), because "georgia" the country-name-table
  entry doesn't distinguish itself from "georgia" the US state.
- **"Milwaukee, Wisconsin"**, **"Fukuoka"**, **"Yokosuka"**, **"Tukwila, WA"**, **"Ukraine"** itself,
  and **"Mukilteo, Washington"** all resolved to **GB**, because the substring "uk" appears inside
  each of those words (mil-**wauk**ee, f**uk**uoka, yokos**uk**a, t**uk**wila, **uk**raine,
  m**uk**ilteo) with nothing checking whether "uk" was actually a standalone word.
- **"Albuquerque, New Mexico"** and similar resolved to **MX** (Mexico), the same shape of bug —
  "mexico" is a real substring of "new mexico" even though the two mean different things.
- **"China Lake, California"** resolved to **CN** (China) — "china" is a real word inside "China
  Lake", a real place in California with no China-specific meaning at all.
- **"King of Prussia, PA"** resolved to **RU** (Russia) — "russia" is a literal substring of
  "prussia".

**The consequence reached further than the raw country field — it was visible on this package's own
flagship new deliverable.** The "median advertised pay by country" chart (Tier 5.1/5.2, gate 9) built
its country groupings directly from this field. Before the fix, 5 of the chart's 10 displayed country
medians were built from majority-contaminated groups: the bar labelled "GE" was 100% misassigned US
federal postings and disappeared to zero once fixed (there was never a real Georgia-country cohort in
this dataset); "MX" was 92.5% misassigned New Mexico; "IN" and "CN" and "GB" were each substantially
diluted the same way. A reader comparing "median advertised pay in Georgia" against the chart's other,
genuine country medians would have been comparing a real number to a phantom one with identical visual
confidence.

**Fixed:** `country_from_location()` rewritten with (1) whole-word matching (`_word_match()`, using a
not-preceded/followed-by-a-letter check rather than plain `\b`, since `\b` itself does not fire around
punctuation — "u.s." followed by a space has no `\b` between the trailing "." and the space, a second,
smaller bug caught while building the fix, before it shipped); (2) a full US-state-names table,
checked before the ambiguous country-name table, since two states' own full names collide with real
country names in a way no word-boundary fix alone resolves ("Georgia" the state vs. Georgia the
country are literally the same word; "New Mexico" is a more specific 2-word phrase than the country
table's own bare "Mexico" entry, so checking state names first — not longer-match-wins — is what
actually resolves it). Georgia's own collision is irreducible by text alone: checked live, of the 143
"Georgia"-labelled postings in the real dataset at fix time, zero were Tbilisi, so resolving "Georgia"
to US is the empirically better default — disclosed here, not silently chosen; a future Tbilisi-based
posting would need a country name spelled out elsewhere in the same location text to resolve
correctly, same as any location this table doesn't otherwise recognise.

**Verified against the real, live-harvested dataset, not a synthetic test alone:** simulated the fix
against the previously-committed `postings.json` before touching any harvester (2,108 of 35,936
postings' own country field changed), then re-ran all six harvesters for real (raw cache warm, no new
network calls needed for this specific fix to take effect) and re-merged. Final distribution: GE and
RU both **0** (were 143 and 6); Georgia-labelled postings resolving to GE: **0**; every sampled
Ukraine/Milwaukee posting now resolves correctly (UA / US); China Lake correctly splits between US
("China Lake, California") and one remaining CN case (see item's own residual note below, "China
Lake, CA" — the abbreviated form). Top country counts after the full re-run: US 26,355, GB 1,891, CA
1,041, IN 931, DE 619 — GB/IN both genuinely UP despite losing their own contamination, because the
harvesters' own seed-hint probing found more real companies on this run (738→862 Ashby, 215→242
Lever, 247→309 Greenhouse) independent of this fix.

**A related, small, disclosed residual — not fixed, the two "correct" answers conflict:** 10 of
43,034 postings (0.023%) still resolve to a plausible-but-arguably-wrong country because a short,
genuinely ambiguous token (a bare US state code) is checked at a different priority than a competing
signal. "CA - Toronto" (9 Ashby postings, an internal office-label prefix) resolves to US (California)
because the bare-2-letter-code check runs before the city table would see "Toronto"; "China Lake, CA"
(1 Lever posting — its own sibling record, "China Lake, California," resolves correctly, confirming
this is specifically about the abbreviation) resolves to CN because the country-name table's own
"china" is checked before the bare code. Reordering either check fixes its own case and breaks the
mirror case the other way — "Vancouver, WA" is genuinely the US city, not Vancouver BC, and would
misresolve if city-table-first became the new default. Fully resolving this needs a real city+state
co-occurrence check (does "CA" appear directly adjacent to a token this table already knows is a
Canadian city, vs. adjacent to nothing recognisable) this function does not build.

**Decide:** whether the 10-posting residual above is worth a dedicated co-occurrence check (a real,
if small, precision improvement) or stays disclosed-and-accepted at this scale — matching item #32's
own framing of a small residual not being worth new scope on its own. Separately: whether "Georgia
always resolves to US" should be revisited if this pipeline's own provider mix ever grows real
Tbilisi-based coverage (none observed as of this package).

---

# Package 14 — fixing what the external data-science audit found

## 34. A vintage deflator was investigated for Tier 2 (Finding 2) and declined — disclosure shipped instead

The external audit's Finding 2 (HIGH): reference years across the wage panel's fifteen countries span
2009-2025 (2018-2025 excluding the UAE), and nominal pay rose roughly 20-30% across that window — the
vintage gap is the same order of magnitude as the cross-country signal the chart draws. The work order's
own instruction gave two paths: implement a deflator as an explicit, labelled lens if defensible, or
record why it is not and keep the disclosure.

**Investigated and declined.** The only country-by-year wage-level series this pipeline holds is
`oecd_indicators.json`'s own `avg_wages.WG_USD_PPP` — a NATIONAL, ALL-OCCUPATION average. A deflator
built from it would scale a country's own SOFTWARE-DEVELOPER-SPECIFIC figure by that country's own
NATIONAL AVERAGE wage growth between its native year and a common target year — which silently assumes
software-developer pay tracked the national average's growth rate over that window. There is no source
in this pipeline that verifies that assumption, and real reason to doubt it: tech-sector pay has
diverged sharply from national averages in several of this site's own covered countries across
2018-2025 (a boom into 2022, a contraction after). This is the SAME class of error this project has
already been burned by once, by name: `normalise.py`'s own `hours_for()` docstring records a real,
measured 21.4% overstatement of Ireland's mean when a generic economy-wide Eurostat hours figure stood
in for an occupation-matched one that existed but wasn't used. A wage-growth deflator built from an
all-occupation average, applied to a single occupation, is structurally the same substitution, at
unmeasured magnitude, with no occupation-matched growth series available to check it against.

A second, independent reason: every USD figure in this panel already goes through a YEAR-MATCHED FX
conversion (rule 3, `normalise.py`) — the rate used is the one for that figure's OWN year, deliberately,
not a common year. Stacking a wage-growth deflator on top introduces a second, independent judgment call
(which year's rate does the deflated figure inherit? does the deflator apply before or after the FX
step?) that compounds uncertainty rather than resolving the one Finding 2 actually names.

**Shipped instead (Tier 2, no new assumption required):** the reference year now renders on every row of
the comparison chart itself (`site/src/components/explore/WagePanel.tsx`), not only inside the collapsed
"open each row's own method" card; and whenever the countries actually shown on the current toggle span
more than three years, a visible line names the spread, the newest country/year and the oldest
country/year, directly under the chart's own toggles — see `yearSpread` in that file. No number is
adjusted. The reader sees the real gap and can judge it themselves, which needs no assumption about
occupation-specific wage growth this pipeline cannot verify.

**Decide:** whether a genuinely occupation-matched wage-growth series (not the national `avg_wages`
average) is worth sourcing specifically to support a deflator lens in a future package — this package's
own conclusion is that the CURRENT proxy is not defensible, not that no deflator could ever be.

## 35. The new OECD wage-benchmark invariant (Tier 1, Finding 1) is a FLAG, not an ERROR — by design, not oversight

Tier 1's own instruction: "any country whose published median falls below 1.0x or above 2.5x its own
OECD `avg_wages` for the same year fails the audit." `scripts/audit_data.py`'s new
`check_oecd_wage_benchmark()` implements the exact comparison, the exact threshold, and runs on every
future commit — but appends to `FLAGS`, not `ERRORS`, so it does not fail `python scripts/audit_data.py`'s
own exit code (which `.github/workflows/ci.yml` gates every push to `main` on).

**Why:** Spain, Ireland and the Netherlands fail this benchmark today (0.77x, 0.98x, 0.97x — see
REPORT-P14.md gate 4 for the live numbers, re-derived directly against live data for this entry rather
than trusted from an earlier draft, which wrongly named Germany as the third country and applied one
uniform explanation to all three) — each for its own real, disclosed, and genuinely DIFFERENT reason:

- **Spain:** `crosswalk.compare()` forces its own 4-digit ISCO mapping down to 2-digit against the
  reference occupation — a real breadth issue, its own government source covers more than "software
  developer" specifically.
- **Ireland:** forced further, to 1-digit ("all professionals") — the same kind of breadth issue as
  Spain, more severe.
- **Netherlands:** NOT a breadth issue. `data/occupations.json`'s own mapping note records that its BRC
  2014 classification is "not a national adaptation of ISCO-08 the way SSYK, DISCO-08, STYRK-08 and
  AL2010 are... no defensible ISCO-08 anchor at any depth" — a crosswalk STRUCTURAL-compatibility gap,
  not a scope-breadth one. Its own national occupation title ("Software- en applicatieontwikkelaars") is
  software-developer-specific. Its near-1.0 ratio more plausibly traces to item #37's own compositional
  finding instead (`usd_regular_pay`, bonus excluded from a bonus-inclusive OECD baseline) — close
  enough to 1.0 that a fully bonus-inclusive comparison could plausibly clear it.

All three published medians are correctly sourced and correctly computed for what each country's own
national statistics actually measure. Tier 1's own set-wide chart fix already excludes these three
countries from the cross-country COMPARISON chart, each for its own individually-disclosed reason (see
`crosswalk.resolve_set()`) — but each one's own country PAGE still, correctly, shows its own real
figure. Making the benchmark an ERROR would fail CI permanently for conditions no future commit can
resolve without either fabricating a narrower occupation-specific figure that does not exist (forbidden
by this project's own rules) or removing a country page entirely (not asked for, and a real loss of
otherwise-good data).

Gate 4's own text anticipates exactly this outcome: "show it passing after Tier 1's fix — or, if figures
still fail, say so plainly rather than loosening the threshold." FLAG is how "say so plainly" stays
compatible with "CI green" (gate 13) at the same time: the threshold, the comparison, and the visibility
are all unchanged from the work order's own spec — only the check's power to block a build forever over
an already-investigated, already-disclosed, structurally-unfixable-by-a-number-change condition is.

**Decide:** whether FLAG is the right permanent severity here, or whether the owner would rather this be
an ERROR that stays red on `main` until Spain/Ireland/Netherlands are either dropped from the wage panel
entirely or the benchmark's own threshold is scoped to exclude countries already outside
`resolved_comparison`'s chart-comparable set (a scoping this package deliberately did NOT do — see this
check's own docstring — because coupling the benchmark's pass/fail to the chart's own exclusion logic
risks the check silently "resolving" itself the moment the chart hides a country, which is closer to
silencing the check than reporting on it independently).

## 36. Postings currency conversion (Tier 3.1) covers 14 currencies, not every currency observed live

`postings_common.CURRENCY_TO_FX_COUNTRY` converts USD, EUR, GBP, CAD, SGD, JPY, KHR, INR, AMD (Finding
3's own named list) plus AUD, SEK, NOK, DKK, AED — the second five added because their own countries
(AU, SE, NO, DK, AE) were ALREADY in `fx_rates.json` as part of the 15-country wage spine, so covering
them costs zero new fetching. Real, live postings data also carries PHP, PLN, CNY, HUF, THB, MXN, BRL,
CZK, KRW, RON, CHF, MYR, HKD, TWD and ARS — each single- to low-double-digit counts, 103 postings
combined (counted directly: PHP 42, PLN 13, CNY 8, HUF 8, THB 6, MXN 5, BRL 3, CZK 3, KRW 3, RON 3,
CHF 3, MYR 2, HKD 2, TWD 1, ARS 1 — out of 46,040 total) — none of whose countries this pipeline has
ever fetched FX history for.
These postings' own native compensation is unchanged and fully disclosed (a null `compensation.usd`
field, same as any other unconverted currency); they are simply not convertible to USD yet.

**Also worth recording:** as of this package (21 August 2026), MOST compensation-bearing postings —
even in currencies this pipeline DOES cover — still show `compensation.usd: null`, because their own
effective year (posted_at, or the harvest year when absent) is 2026, and the World Bank has not yet
published a full-year 2026 average exchange rate (the year isn't over). This is `normalise.to_usd()`'s
own rule 1 working exactly as designed — refusing rather than substituting a nearby year's rate — not a
gap in this package's own coverage. The conversion rate will rise on its own once 2026's FX data is
published (historically, early the following year), with no code change needed.

**Decide:** whether extending `src_fx_rates.py` to fetch FX history for the fifteen remaining observed
currencies' countries (Philippines, Poland, China, Hungary, Thailand, Mexico, Brazil, Czechia, South
Korea, Romania, Switzerland, Malaysia, Hong Kong, Taiwan, Argentina) is worth a future package's scope,
given each is a small fraction of total postings today.

## 37. The OECD wage benchmark (item #35) compares whichever pay basis a country happens to publish, not a composition-matched one

OECD's own `avg_wages` series (national-accounts-based, "average annual wages per full-time
equivalent employee") is compositionally closer to `total_earnings` (bonuses included) than
`regular_pay` — national accounts' own compensation-of-employees concept includes irregular pay.
`check_oecd_wage_benchmark()` uses `usd_regular_pay` when a country publishes it, falling back to
`usd_total_earnings` otherwise — it does not composition-match against OECD's own basis.

**Why this was not treated as a bug to fix:** the resulting bias runs in the SAFE direction for a
FLAG-only check. A `regular_pay`-based country is being compared against a bonus-INCLUSIVE OECD
baseline while excluding its own bonus — if compared on a truly consistent (bonus-included) basis,
its real ratio would be equal or HIGHER, never lower. The compositional mismatch can only push a
regular_pay country's reported ratio DOWN, toward more flagging, never up toward a false pass. Real
numbers make this concrete, not hypothetical: Ireland (`usd_regular_pay`, 0.978x) and the
Netherlands (`usd_regular_pay`, 0.973x) are two of the three countries item #35's own Tier 1 gate 4
evidence names as currently flagging — both sit just below the 1.0 floor on this composition-
inconsistent basis, meaning their real, bonus-included ratio would sit somewhat HIGHER than what
is shown; whether that shift alone would be enough to clear 1.0 is exactly the "compositionally-
matched" version below would answer and this one cannot. Spain, the third of that trio, is
`usd_total_earnings` — no compositional mismatch affects it at all, so its own 0.770x flag is
unaffected by this finding regardless. A `total_earnings`-based country generally (GB 1.10x, AU
1.23x, ES 0.77x) has no such mismatch — both sides already include bonuses. There is no path from
this mismatch to a country that SHOULD fail silently passing — at most, one that currently flags
(IE, NL) turning out, on a fully composition-matched basis, not to deserve it.

**Decide:** whether a future package should composition-match this benchmark properly (deriving a
consistent bonus-inclusive OECD comparator per country, where the data exists to do so) for
precision, or whether the current, safely-biased-toward-over-flagging version is good enough given
its role is triggering human review, not an automated correction.

## 38. `/postings` fails the work order's own Lighthouse performance gate — root cause found, not fully fixed

Gate 11 requires Lighthouse performance >=90 on every route. Measured, retried three times (not
noise — consistently reproduced): `/postings` best of three 0.80. Every other route measured
(home, compare, position, `/data/postings-seed`, explore/money, explore/jobs, city/milan,
country/SE, data) scores 0.94-0.98 — `/data/postings-seed` in particular started at 0.84-0.85 and
now passes at 0.94 after the two fixes below, so they are real, measured improvements, just not
enough on their own for `/postings` itself, the one route most directly built around the full raw
postings array.

**Root cause, confirmed via Lighthouse's own trace, not guessed:** `history/postings.json`'s own
`network-requests` entry shows a 20,523,759-byte (~20MB) resource size — this package's own postings
recovery (Gate 1: 19,463 -> 46,040 real postings) is directly why. The browser's own JSON.parse() of
that payload dominates the page's main-thread work (Lighthouse's own `mainthread-work-breakdown`:
~1.1s in "Other," ~0.9-1.0s in "Script Evaluation," largely attributable to parsing plus the
subsequent React render of the parsed data) — `total-byte-weight` itself scores a clean 1.0 (the
gzip-compressed transfer is only ~2.25MB), so this is a CPU-bound parsing/rendering cost, not a
network one.

**Two real fixes applied and verified, insufficient alone:**
1. `Postings.tsx`'s own `mapDots` (a per-country map-view aggregate) was being computed on every
   render regardless of whether the map view was even showing — gated on `view === 'map'` now.
2. `advertisedByCountryCfg()` used to re-scan the FULL raw `postings` array and sort per-country
   values in the browser, on every page load, to compute a chart that is IDENTICAL for every visitor
   until the next rebuild. Moved to `build_postings.py` (`pay_summary_by_country`, a ~12-row
   pre-computed field — renamed from the first-tried `advertised_by_country` after it collided with
   `check_survey_vs_advertised_pay`, see this package's own commit history) — a genuine, deterministic
   build-time aggregate, not a client-side recomputation of the same thing on every visit.

   **Update, same package, after an independent adversarial review (finding M8):** this aggregate
   originally required native `currency == USD`, which meant every non-US country's own entry was
   quietly built from whichever of its postings a US-headquartered employer happened to quote in USD
   — a small, biased subsample, not "no data" but worse. Fixed: it now reads the same
   `compensation.usd` field Tier 3.1 already computes for every posting, so every convertible
   currency contributes. `Postings.tsx`'s own on-page disclosure text was updated to match — it no
   longer claims a USD-native restriction that isn't true any more.

**Update, same package, gathering this same gate's own final evidence:** `/data/postings-seed`
regressed again (0.71-0.83) under this round's own further data growth (`postings.json` grew again
through the full re-harvest) — investigated fresh, not assumed to be the same unfixable /postings
limitation, since this page is a genuinely different case. `PostingsSeed.tsx` was fetching the
ENTIRE `postings.json` to read three small fields (`provider_summary`, `seed_companies`,
`country_counts`) it actually uses, never touching the `postings` array itself — unlike `/postings`,
which genuinely needs that array. Fixed at the source: `build_postings.py` now also writes
`postings_seed_summary.json` (~190KB, just those three fields), and `PostingsSeed.tsx` reads it
through its own dedicated loader — `total-byte-weight` dropped over 10x (2,522 KiB -> 216 KiB).
That fix then exposed a masked cumulative-layout-shift regression (0.244, reproduced 3/3 runs) — a
slow fetch had been pushing the "Loading…" placeholder's own height mismatch past Lighthouse's
observation window; a fast one doesn't. Fixed the same way `Postings.tsx` already fixed the
identical class of bug in an earlier round: `ChartSkeleton` panels reserving each real panel's own
measured height. Final: 0.94-0.96, CLS 0, confirmed across 3 runs. `/postings` itself: unchanged,
0.76-0.79 — the architectural limitation below is still real and still not attempted this package.
Like the original two fixes below, both of this round's own fixes are real, disclosed,
unconditionally-good changes, not a "fake it to pass a check" move — and, like them, neither touches
`/postings` itself, whose own root cause is a different, architectural one none of the four address.

The two ORIGINAL fixes (mapDots gating, the build-time aggregate) remain real, disclosed,
unconditionally-good changes too (they remove genuinely wasted work) — neither is a "fake it to pass
a check" move, and neither alone nor together brought `/postings` itself to 90 (0.78-0.83 after
both, at the time). The dominant cost there — parsing a 20MB JSON payload synchronously on the main
thread — needs
a genuine architecture change to actually fix: paginating or lazy-loading the postings LIST fetch
itself (rather than shipping all 46,040 records on first load), or moving the parse off the main
thread (a Web Worker). Both are real engineering efforts with their own risk, on a WORKING,
user-facing feature, under a package whose own mandate is data integrity, not a page-load redesign —
attempting one under this package's own time budget risked shipping a rushed, undertested change to
a feature nothing in `DATA-AUDIT-EXTERNAL.md` asked to be touched at all.

**Also considered and set aside:** displaying the postings.json's own new `compensation.usd` field
(Tier 3.1) in the UI — currently computed, shipped, and read by nothing in `site/src/**` at all
(confirmed by search). Wiring it into `PostingRow` would make the shipped data earn its byte cost
and would be a natural, small completion of Tier 3.1's own intent, but is a new user-facing display,
not a bug fix, and was set aside for the same reason: not worth rushing under this package's own time
pressure without room to verify it thoroughly against this project's own real history of shipped
display bugs (overflow, mismatched rounding, collapsed axes — see `docs/REGRESSION-CATALOGUE.md`).

**Decide:** whether to commission a proper postings-list pagination/lazy-load redesign (the real fix)
as its own package, and separately, whether the `compensation.usd` field should be wired into the UI
(a complementary, smaller follow-up) or left as a derived field available for a future package to use.

## 39. The OECD wage benchmark (item #35) compares a market-FX-converted published median against a PPP-adjusted OECD figure — two different currency bases, not one

An independent adversarial review (M1) flagged that `check_oecd_wage_benchmark()` divides
`wage_distribution.json`'s own USD median — converted from native currency at the market exchange
rate (`normalise.to_usd()`, World Bank `PA.NUS.FCRF`, period-average) — by OECD's own
`avg_wages.WG_USD_PPP`, which OECD itself computes at a **purchasing-power-parity** conversion
factor, not a market rate. Confirmed real, and quantifiable: for a ratio `median_usd / oecd_avg_usd`,
where each side is native-currency-value divided by its own conversion rate, the two rates do not
cancel — the computed ratio equals the country's TRUE native-currency ratio (`median_native /
oecd_avg_native`) multiplied by `(ppp_rate / fx_rate)`. Wherever a country's PPP rate and market FX
rate diverge (routine for any country whose price level differs from the US — larger for emerging
economies, smaller but non-zero even among rich, similar-cost-of-living OECD members), this
check's reported ratio is systematically offset from the true within-country ratio by that same
factor, in whichever direction that country's own PPP-vs-market gap runs.

**Why this was not fixed this package:** the clean fix is not "pick PPP or market rate" — it is to
avoid a cross-currency conversion for this comparison at all. Both sides are meant to answer a
WITHIN-COUNTRY question ("does this software wage look plausible next to this country's own average
worker?"), so comparing `median_native / oecd_avg_native` directly, in the country's own currency,
would sidestep the PPP-vs-market question entirely — no conversion, no rate-choice, no mismatch.
Checked whether that data already exists: it does not, in what this pipeline currently fetches.
`src_oecd_indicators.py`'s own `avg_wages` block already asks OECD's API to keep both `USD_PPP` and
`XDC` (native-currency) rows (`"keep": lambda r: r.get("UNIT_MEASURE") in ("USD_PPP", "XDC")`), but
the currently committed `data/processed/oecd_indicators.json` carries `WG_USD_PPP` only — checked
directly for US, DE, SE, ES, IE, NL, GB, no `WG_XDC` key present for any of them. Whether that is
because OECD's own `AV_AN_WAGE` dataflow (a curated, comparison-purpose indicator) simply does not
publish a native-currency variant at all, or because one exists but this pipeline's own fetch/keep
step is dropping it, was not investigated further this package — either answer needs its own live
API investigation, not a guess baked into a fix.

Also considered: widening `_OECD_BENCHMARK_LOW`/`_OECD_BENCHMARK_HIGH` to absorb a typical PPP/FX
gap. Rejected — the gap's size and direction are country-specific (not a constant this pipeline
could size once and trust), and this check is FLAG-only already; loosening a threshold to
paper over a basis mismatch, rather than fixing the basis, is exactly the "change a number to make
a check pass" move the work order's own instruction forbids — even the review-visible threshold
counts as a published rule, not just a wage figure.

**Practically:** this does not change any published wage figure — only which countries this one
FLAG-only, human-review-triggering check happens to name. ES, IE, and NL's own flags (Tier 1's gate
4 evidence) are driven by a real, disclosed occupation-scope difference (item's own text above,
NEEDS-DECISION #35), large enough that a PPP/FX correction would not plausibly reverse them; this
finding is about precision and correctness of the check's own arithmetic, not about those three
specific results being wrong.

**Decide:** whether it's worth a short, live investigation into whether OECD's `AV_AN_WAGE`
dataflow publishes a native-currency (`XDC`) series at all for this specific indicator (if yes: wire
it in and switch this check to a same-currency ratio, removing the PPP/FX question entirely; if no:
this disclosure is the durable answer, not a placeholder for a fix that isn't there to make).

## 40. Position.tsx still reads the pairwise `crosswalk` verdict — CoverageMap is correct by design, "Pay against cost" is a real, only partly-mitigated gap

An independent adversarial review (M7) flagged that `Position.tsx`/`CountryProfile.tsx` still use
`row.crosswalk` (`compare()`'s pairwise-against-one-fixed-reference verdict) rather than
`row.chart_comparable` (`resolve_set()`'s set-wide verdict, Tier 1's own fix for the severe finding).
First pass at this entry concluded "correct by design, no gap" for all three surfaces — checked
again against the review's own specific citations, and that conclusion was too quick for one of them.

**CountryProfile.tsx — still correct, unchanged conclusion.** Renders ONE country's own native wage
figure, `crosswalk.degraded_by` used as a `<Figure>` source-attribution note about THAT country's own
comparability, never placed next to another country's number.

**Position.tsx's `CoverageMap` — still correct, unchanged conclusion.** A per-country CAPABILITY
table ("does the position/estimate feature work here, and at what crosswalk depth"), each row stating
its own depth as a fact about that one country, the same way a compatibility matrix lists per-row
support levels — nothing implies two rows' own figures sit on one comparable axis.

**Position.tsx's "Pay against cost" — a real gap, only PARTLY fixed.** The review's own words: it
"renders a per-city estimate row for IE/ES/DE built from those broad distributions, side by side
with 4-digit countries, gated only on `row.crosswalk.comparable`" — correct, and this one IS closer
to Finding 1's own shape than first assessed here. A user comparing "Dublin: 5 years to home" against
"Stockholm: 3 years to home" is implicitly comparing software-developer outcomes, but Dublin's own
figure is drawn from Ireland's "all professionals" distribution (crosswalk forced to 1-digit) — the
same kind of scope mismatch Finding 1 named, in a personalised tool instead of a population chart.
Before this fix, nothing on screen disclosed that outside an SVG hover title elsewhere in the
codebase — worse coverage than WagePanel had even before ITS OWN fix.

**What was actually done, and what wasn't:** added a plain, always-visible text caveat next to any
"Pay against cost" row whose `crosswalk.comparable` is true but `degraded_by` is set — the minimum
honest disclosure, matching the "say so in real text, not a tooltip" standard this package already
applied to WagePanel's own exclusions. What this does NOT do: decide whether a degraded city belongs
in this list at all. WagePanel's own answer to that question (Tier 1) was to EXCLUDE a country the
resolved set can't support; "Pay against cost" cannot cleanly do the same, because the city is one
the USER explicitly chose (via Compare), not one this site is offering up as "the 15 comparable
countries" — dropping a user's own selection outright is a different, more disruptive product
decision than trimming an editorial chart.

**Decide:** whether "Pay against cost" should (a) stay as now — every user-picked city renders with
a plain-text caveat when degraded, nothing dropped, or (b) actively warn more strongly (e.g. visually
distinct, not just parenthetical text) for a degraded city's own estimate, or (c) something closer to
WagePanel's own exclusion model when enough of the user's OWN selected cities share a resolvable
depth (an open design question — quorum semantics don't obviously translate to an arbitrary,
often-small, user-chosen set the way they do to a fixed 15-country editorial panel).

## 41. `postings-refresh.yml`'s reclaim bucket is uncapped and grows every run — a workflow timeout was added as a cheap safety net; whether to cap the bucket itself is still open

An independent adversarial review (L3) flagged that `build_probe_order`'s own docstring
(`postings_common.py`) referenced "See NEEDS-DECISION.md for the runtime tradeoff this creates" —
no such entry existed anywhere in this file. The underlying tradeoff is real: the "reclaim" bucket
(every already-committed-verified company, re-probed live and UNCONDITIONALLY on every scheduled
run — Tier 0.2's own fix for the destructive-refresh finding) has no cap, by design, and only grows
as more companies become verified over time. `postings-refresh.yml` also set no `timeout-minutes`,
relying entirely on GitHub Actions' own 360-minute default.

**Checked the actual current scale before deciding what, if anything, to do:** Ashby's own
`verified_companies` count today is 961 (not the review's own slightly earlier ~1,360 — the count
moves run to run). Each reclaim probe costs a real HTTP request plus a 0.15s polite-pacing sleep
(`src_postings_ashby.py`'s own `_fetch_board()`); at that rate, probing the FULL reclaim bucket costs
roughly 8-12 CPU-minutes today, not hours — nowhere near GitHub's own 360-minute default, and this
review's own implicit "might silently time out" framing does not hold at today's scale. The real risk
is a FUTURE one: the bucket has no ceiling, and nothing would visibly warn as it grows.

**Done:** added `timeout-minutes: 120` to the `refresh` job — a generous, low-risk safety net (roughly
10x today's realistic reclaim-bucket runtime) that fails the job loudly and quickly if a future run
ever does stall or grow unexpectedly large, rather than silently consuming CI minutes for hours. This
does not cap the bucket itself or change any harvest behavior.

**Decide:** whether the reclaim bucket should ever be capped or paginated (e.g. probing only the N
most-recently-unconfirmed companies per run, cycling through the rest over several runs) once it
grows large enough to matter. Not done here — capping it carelessly risks reintroducing a milder
version of the exact destructive-refresh problem Tier 0.2 just fixed (a company that never gets its
turn in a capped rotation is functionally the same as one silently dropped), so this needs real design
attention when the scale actually warrants it, not a number picked defensively today against a
problem that is not yet present.

## 42. `/postings` "Median advertised pay by country" supports one country, not seven — how should it be shown?

Package 15 measured what that chart rests on. Three compounding problems, all quantified in
`REPORT-P15.md` and `docs/DATA-FITNESS.md §1`:

1. **The panel is ~28% software.** The harvest takes every job a seeded company posts, so the median
   is taken over an arbitrary occupational mix that differs by country. Three measurements land in
   the same place: a keyword rule 27.09%, a 400-title hand-labelled sample 29.0% (95% CI
   24.8-33.6%), a trained classifier 27.89%. They are not independent - the classifier is trained
   on the hand labels - so this supports "roughly a quarter to a third", not a two-decimal share.
2. **Six of seven countries have too few postings.** Singapore's published figure rests on **five**
   postings with a 95% bootstrap interval of **$60,177-$317,412** (+/-84%). After cleaning, exactly
   one of the seven clears a 30-posting floor; the rest fall to between 0 and 13.
3. **The published precision is manufactured.** Employer-entered pay is heaped to round thousands
   (77.5% of native annual minima end in 0 or 5; terminal-digit uniformity rejected, p < 0.001). FX
   conversion turns a round native figure into `$152,969.52`.

Re-derived on the de-duplicated, software-only subset, **the US median moves +18.9%**
($82,994 → $98,688). Canada +13.2%. After cleaning, **only the US clears a defensible minimum n.**

The analysis is finished and the corrected form is specified:

> Median advertised pay, software roles only - United States: **$99,000**
> (95% CI $95,000-$101,000, n = 1,117 after de-duplication)

**Decide:** which of these the chart should become —

- **(a)** one country (US only), rounded to $1,000, interval shown;
- **(b)** all seven, each with its interval drawn and an explicit "indicative only, n<30" mark on
  the six thin ones;
- **(c)** retire the chart until the panel covers more countries at usable depth.

This is a product decision about what the page claims, not a data question — which is why package 15
did not make it unilaterally. Everything needed to implement any of the three is committed:
`data/processed/postings_title_classes.json` (per-title class, F1 0.822 for SW),
`postings_duplicate_clusters.json` (precision 0.958), and
`data/quality_history/postings_pay_rederived.json` (per-country re-derived medians with CIs and a
representativeness score against Eurostat ICT employment).

## 43. Teranet's monthly index carries injected per-observation noise — disclose, aggregate, or drop?

All six Teranet cities show residual autocorrelation of **+0.113 to +0.268** about a
smooth trend, with month-over-month autocorrelation near **-0.44**. The two control indices in this
same repo — UK HPI and FHFA, both real published house-price indices — read **+0.985**. A genuine
price index is persistent; independent per-observation noise destroys that persistence and drives
the MoM autocorrelation negative. 60–64% of Teranet months move more than 10%, with swings to 139%.

**This is not a parsing bug.** The stated base holds exactly (2005-06 = 100.0 for every city), the
long-run trend survives (Spearman with time 0.909 for Toronto), and the raw endpoint payload itself
carries the volatility — the pipeline transcribes it faithfully. `housepriceindex.ca`'s endpoint is
undocumented and the index is proprietary, which is the most likely explanation.

The site plots an **annual mean** of the monthly values. That was first recorded here as a
mitigation; on measurement it is not one. Averaging 12 points does cut the noise by root-12, but
what survives is 4.9-6.2% per annual point, which alone implies a year-over-year spread of 7.0-8.7%
against an observed 7.3-10.8% and a true trend of only **3.1-4.1% per year**. The annual residual
autocorrelation stays at 0.39-0.42. **Noise dominates the annual series too**; no single Teranet
value, monthly or annual, is interpretable on its own, and only the multi-year direction survives.

**Decide:** whether to (a) keep only a multi-year direction with a chart-level note that no
individual Teranet value is interpretable; (b) drop Teranet and rely on the other Canadian housing
evidence; or (c) raise it with the publisher. This is a sharper choice than it first appeared -
option (a) is no longer "add a footnote about monthly values", it is "stop plotting a level".

## 44. Percentile transfer is not currently testable, and therefore not defensible

The site intends to infer pay for countries where employers do not publish ranges, by transferring a
percentile position from countries where they do. Package 15 tried to test that assumption and
**could not**: the test needs at least two countries with both posted salaries and official
distributions at a shared occupation depth, and after classification and de-duplication **only the
US clears the sample-size floor**. There is no second country to fit a relationship against.

That is a blocker rather than an omission, and it has a direct consequence: **on current evidence,
percentile transfer is not defensible into any country.** The expected mechanism (Nordic and
continental pay compression) remains plausible and untested.

**Decide:** whether to (a) shelve transfer until the panel covers a second country at usable depth;
or (b) commission a targeted harvest aimed specifically at the countries transfer would serve, so
the assumption becomes testable. Note that the same audit measured the panel as under-sampling
exactly those countries: against each country's share of European ICT specialist headcount, Italy
sits at 0.28x, Denmark 0.30x, Norway 0.45x, Sweden 0.64x and Germany 0.60x, while Great Britain is
over-represented at 2.26x.
