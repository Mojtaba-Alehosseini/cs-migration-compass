# Needs a decision

Raised while porting the design mockups into the React app. Nothing here blocked
a build: each item was resolved the least-invasive way and shipped, and each one
is reversible. They are listed because the choice was not mine to make.

---

# Package 5 — Explore

## 1. CLOSED, package 21 — Stack Overflow: one wave is wired, six are missing

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

**CLOSED, package 21 — ruling: yes, worth a package, not built here.** Recorded as the agreed next
data package. Reason: Stack Overflow is the only source in this pipeline measuring professional
experience DIRECTLY, rather than through the age proxy item #24 already names as this site's own
known weakness in the position feature. Not built this package — a data-pipeline effort of its own,
outside Tier 1/2's scope.

## 2. CLOSED, package 11 (decision shipped; verified against live code in package 30) — Indeed: eight metros drawn, thirty in the file

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

## 3. CLOSED, package 11 (decision shipped; verified against live code in package 30) — The mockup's prose says four metros; its data says eight

Recorded as the work order asks. `EX.indeed` in the mockup holds eight metros and
its palette note says "four US metros cannot borrow other countries' colours".
The data won; the prose appears to be a leftover from an earlier draft.

**Decided, package 11 tier 3:** the data stands. The palette note and the actual
`EX.indeed` data both independently agree on eight metros; only the prose
disagrees, which is the signature of a stale draft leftover, not a considered
choice — two sources agreeing against one is decidable without the owner. No
change needed; shipped behaviour (eight metros) already matches the evidence.

## 4. CLOSED, package 30 - The OECD overlay applies *real* growth to a *nominal* line

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

**CLOSED, package 30 tier 2 - implemented as decided.** `Money.tsx` (the chart moved out of
`ExploreCharts.tsx`, which no longer holds any of it) now carries the caveat on the level and
indexed lenses, the two that actually DRAW the overlay: "paler line = OECD projected real growth
compounded onto a nominal US$ level - not the same quantity as the solid line". The yearly-change
lens keeps its original overlay-hidden chip. Package 11's stated blocker was unfamiliarity with the
lens-rendering code; it was read in full first, and all three lenses were checked on the rendered
page afterwards, not only the two that changed.

Reading it turned up a second, smaller fault: the chip "dashed = naive extrapolation, not a
forecast" rendered on every lens, but the dashed line is drawn only on the level lens and only with
three or fewer countries selected, so on the indexed lens it described a line that was not there.
The chip is now conditional on the same expression that draws the line.

Evidence: `.status/screenshots/p30-gate3-lens-{level,index,yoy}.png`, driven through the Seg
control the way a visitor drives it. The control fires on `pointerdown`, not `click`, so a scripted
`.click()` changes nothing and would have produced three identical screenshots of the same lens
presented as proof of three.

## 5. CLOSED, package 21 — `bls_oews`, `imf_weo`, `worldbank_gep`, Numbeo city rents

Four datasets that cannot be drawn as series, each verified rather than assumed:
BLS returns one year per metro; `imf_weo` is `status: blocked` with an empty
`data` object (403 from every `imf.org` host); `worldbank_gep` is
`status: unavailable`; `numbeo_history.data.by_city` is `{}`.

**Shipped:** each has a gap card naming the dataset, the reason and where it is
tracked. No panel is blank anywhere on Explore.

**Decide:** whether any of the four is worth a fetch strategy of its own — the
IMF parser is written and would run the day the block lifts.

**CLOSED, package 21 (Rule A — blocked source keeps its honest gap).** Re-checked live:
`imf_weo` still `status: blocked` (403 from every `imf.org` host), `worldbank_gep` still
`status: unavailable`, `numbeo_history.data.by_city` still `{}`. Nothing changed, nothing
in this package's own scope touches any of the four. Stays a documented backlog item —
the IMF parser stays written and ready for the day the block lifts, not rewritten or
removed.

---

# Package 4 — Compare

## 6. CLOSED, package 21 — Three surfaces the mockup does not draw, and does not ask to remove

Compare already carried a metric picker (`+ add a metric`), a budget editor and a
climate overlay. The mockup's screen 2 ends after the two footnotes, and the work
order says only that metric selection is out of scope for that package.

**Shipped:** all three kept, moved to sit *after* the mockup's own elements, so
the drawn sequence — toolbar → address strip → chips → table/chart → footnotes —
is exactly as designed and the undrawn extras follow it.

**Decide:** keep them where they are, fold them into the design properly, or drop
them.

**CLOSED, package 21 — ruling: keep them.** The owner's own words: keep them where they sit, and
fold them into the design properly when Compare is next revisited. Not touched this package —
recorded here as the decision, not deferred as an open question.

## 7. CLOSED, package 11 (decision shipped; verified against live code in package 30) — The copy-link toast claims a preview image that does not exist

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

## 8. CLOSED, package 11 (decision shipped; verified against live code in package 30) — Sticky header on phones is a CSS impossibility, not an omission

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

## 9. CLOSED, package 11 (decision shipped; verified against live code in package 30) — `band` and `lens` stay out of the address until they are touched

**Shipped:** existing URL contract kept. A default link reads
`…/#/compare?places=berlin,toronto` and grows as controls are used.

**Decided, package 11 tier 3:** keep omitting defaults from the URL. Every
package built since this item was raised has independently reached for the same
convention — Position.tsx's own `profileToParams()` (package 10) omits
`?years=5` and `?occupation=isco08:2512` for the identical reason, matching
Compare.tsx's own established `update()` idiom this item already describes. A
convention four packages have now converged on without coordinating is decidable
from that evidence alone, not a live open question.

## 10. CLOSED, package 21 — Metric rows are the registry's, not the mockup's

Binding note 13 keeps metric selection out of package 4, so the rows are still
`HEADLINE_KEYS` from `site/src/data/registry.ts`.

**Decide:** if the mockup's illustrative set was meant as the new default, that
is a change to `headline: true` in the registry.

**CLOSED, package 21 — ruling: pay leads.** Checked `registry.ts` directly before changing anything:
`salary_gross` was ALREADY first in `METRICS` and the first `headline: true` entry, so `HEADLINE_KEYS`
(and Compare's default metric set) already led with salary — no change needed there. The real gap was
Home's own default question: `QUESTIONS[0]` was `'home'` (years to a home), not `'pay'`. Fixed by
reordering `QUESTIONS` in `questions.ts` so `'pay'` is first — Home.tsx's `useState(0)` and the pill
row both key off array order, so one reorder satisfies "default question" and "lead" together, with
no separate index to keep in sync. Verified no URL/deep-link scheme keys off question index (none
exists — `qi` is local component state only), so this is not a breaking change for any shared link.

## 11. CLOSED, package 11 (decision shipped; verified against live code in package 30) — Missing-input wording comes from `compute.ts`, not the mockup

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

## 14. CLOSED, package 21 — Germany has no salary source in this package — GENESIS could not be reached

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

**CLOSED, package 21 (Rule D — already resolved on record).** Closed by item #19's own
package-11 resolution below ("this closes items #14, #15 and #19"). This heading stays
as history, not re-opened.

---

## 15. CLOSED, package 21 — Germany, package 9 — DESTATIS_TOKEN unavailable; API confirmed ALIVE, blocked by an account-permission wall (superseded within this item — see the 2026-08-12 tier 2b update below; the original heading here claimed the API path was "confirmed deprecated", which the tier 2b update below found was itself too broad a conclusion)

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

**CLOSED, package 21 (Rule D — already resolved on record).** Closed by item #19's own
package-11 resolution below ("this closes items #14, #15 and #19"). This heading stays
as history, not re-opened.

## 16. CLOSED, package 10 — `phase-4-salary-and-cv-plan.md` assigns package 9 a `stabilityOf()` extension this package's own work order never mentions

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

**Package 30 triage: OPEN, but not a decision anyone can make from this repo.** Item (1) was
resolved by package 10's F3 fix. What is left is item (3): whether the flat-DKK subtraction of
PENS/UREGEL is the right shape at every percentile, or whether it should be proportional. No
preference, cost or scope call settles that — only DST's own methodology documentation, or DST
directly, can. It stays open as a **research task with a named next step** (read the LONMAAL
methodology, or write to DST), not as a question waiting on a ruling. The current assumption is
disclosed on every figure it touches, so nothing is hidden while it waits.

**Triaged, package 11 tier 3:** not an owner decision in the usual sense — no preference, cost or
scope call the owner can make settles which assumption is actually correct; only DST's own
methodology (or DST directly) can answer that. The current disclosed flat-DKK assumption stands as
the pipeline's own honest default until someone reads that documentation or contacts DST — a
research task to flag for whenever there's appetite for it, not a fork this package can close by
picking an answer.

## 18. CLOSED, package 10 — Norway's bonus was named as available and capturable; what this pipeline actually fetched has no such field

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

## 19. CLOSED, package 11 — Germany — `DESTATIS_TOKEN` still absent this session; the registered-account path remains untested

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

**CLOSED, package 21 (Rule D — documentation of an already-made decision).** Formalising the
closure this text already states. #14 and #19 stand closed on this record.

## 20. CLOSED, package 21 — How "the position" can be both experience-linked and `<Figure>`-sourced — the reading this package committed to

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

**CLOSED, package 21 (Rule D — shipped state confirmed).** Re-read against the live site: still
shipped as described, no regression. Nothing in this package's own scope touches it further.

## 21. CLOSED, package 24 — Norway's, Finland's, and Germany's own "native" wage figures use opposite conventions for which basis they represent

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

**STAYS OPEN, package 21.** Not touched by this package's Tier 1/2 items, and not closeable under
any of the four Tier 3 rules — it is a genuine site-wide design choice (a new UI vocabulary item vs.
a data-convention migration across four sources), not a blocked source, a disagreement between two
methods this package can adjudicate, an indefensible number, or an internal note. Belongs with a
future package that owns a Compare/Explore design pass, the same reasoning item #6 was given.

**CLOSED, package 24 — a per-row basis chip, not a data migration.** `CountryStripRow.tsx`'s own
`BASIS_LABEL` map gives Norway, Finland, Germany and Denmark — exactly the four sources this item's
own body names as inconsistent — a small inline text chip beside their estimate: "incl. bonus"
(Norway), "excl. bonus" (Finland, Germany), "incl. pension" (Denmark, naming its own STAND concept
rather than mislabelling it as a plain total-earnings figure). Spain, also total_earnings per this
item's own body, gets none — it was never a DUAL-basis source with a silent choice between two
tables the way Norway/Finland/Germany are (package 11's own update); it has only ever had the one
figure to publish. The chip earns its own mark in the redesign's five-mark budget (`REPORT-P24.md`'s
own Tier 1 mark-budget table) rather than living behind a tap: a reader comparing Norway's and
Finland's numbers side by side needs the "these are not the same measurement" fact at the same
glance as the numbers themselves, not one tap away, since the whole failure mode this item describes
is comparing two figures that look alike without realising they aren't. Nothing else in the budget
was given up to make room — the design totals four marks, one under its own five-mark ceiling.
Unifying every source onto one basis (this item's own other option) stays out of scope, for the same
reason it was out of scope at package 10 and 11: it means revisiting `_extract_no()`, `_extract_fi()`,
`_extract_de()` and Denmark's own STAND derivation, and this package's own governing constraint is
presentation only, no method changes.

This resolves the item's own "Decide" question. It does NOT resolve the PACKAGE 11 REMEDIATION
UPDATE above (finding F13, Norway's own USD estimate path) — that is a computation question, not a
display one, and fixing it would itself be a method change. Carried forward as its own item: #58.

## 22. CLOSED, package 21 — A flat net-take-home percentage is applied to a salary that can range 2.5x under a user-chosen percentile

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

**CLOSED, package 21 — the disclosure note, the more proportionate fix.** `registry.ts`'s
`salary_net` metric now states the limitation directly in its own source disclosure, wherever the
figure renders: "a single flat rate for the whole city — real tax is progressive, so this
understates the true net figure the further a salary sits above what this rate was calibrated
against." Applies whether or not a Budget override is active, since even a city's own three
default bands are not perfectly tuned to any one of them either. A progressive-tax model stays a
future package's scope — modelling bracket schedules for fifteen countries remains a real
harvesting effort, not attempted here.

## 23. CLOSED, package 21 — `_verify_mdrsnit_reconciliation()` re-proves the STAND/MDRSNIT identity against whatever data the harvester actually used this run — cached bytes included

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

**CLOSED, package 21 (Rule D — internal note, not a decision).**

## 24. CLOSED, package 21 — Converting years of professional experience to an assumed age for Sweden's and Norway's own age-banded crosses — `ASSUMED_CAREER_START_AGE`

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

**CLOSED, package 21 (Rule D — tracked TODO, not a live decision).** Package 12 has since shipped
(the postings panel), but its own occupation classifier (#30) carries no `education_level` field —
option (c)'s own precondition still isn't met. Option (a) stands.

## 25. CLOSED, package 21 — `DESTATIS_TOKEN` may have been exposed in this session's own tool-call transcript — consider rotating it

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

**CLOSED, package 21 — checked plainly, as asked, without printing the value.** Compared the token
value (by hash, never printed) across every local runner file that carries it: `prompts/run-
package-9.cmd`, `run-package-9-resume.cmd`, `run-package-10.cmd` and `run-package-11.cmd` all still
carry the byte-identical value — **the exact credential that leaked has not been rotated.** The
current package's own runner (`run-package-21.cmd`) does not reference `DESTATIS_TOKEN` at all, and
the variable is unset in this session's own environment. None of these files are tracked by git
(`prompts/` is gitignored) — the exposure stays confined to this session's local disk and its own
transcript, never reached GitHub. Stated plainly, as asked: **the value is unrotated.** The decision
to rotate it remains the account holder's, not this pipeline's.

---

# Package 12 — the postings panel

## 26. CLOSED, package 21 — Four providers probed and confirmed live but not wired into a harvester this package

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

**CLOSED, package 21 (Rule D — backlog scoping note).** Not touched — the existing six harvesters
already carry the postings panel well past its original coverage target, and none of this package's
own Tier 1/2 items ask for a seventh provider. Stays a recorded option for a future package.

## 27. CLOSED, package 21 — Jobvite and JazzHR — confirmed not usable at scale, not merely unprobed

Distinct from item #26 above: these two were probed and the answer is a real "no," not "not yet."
**Jobvite**: has a REST API and an optional published-jobs feed, but the feed is off by default per
customer and most customers never turn it on — there is no guessable public endpoint the way every
other provider in this package has. **JazzHR**: the public board (`{slug}.applytojob.com`) is
server-rendered HTML with the job list baked into the page markup; the real API and XML feed both
require a customer-specific key. Neither has a path to bulk, unauthenticated, cross-company
harvesting the way Ashby/Greenhouse/Lever/Teamtailor/SmartRecruiters/Workable/BambooHR/Workday all
do. Not re-probed in a future package unless a company-specific key becomes available through some
other channel — this is a structural "no," not a session budget limit.

**CLOSED, package 21 (Rule A — blocked source, disclosed).** Both genuinely require an
authentication path this pipeline does not have and correctly does not attempt to bypass. Nothing to
decide unless a customer-specific key becomes available.

## 28. CLOSED, package 21 — Greenhouse's own `pay_input_ranges` has no period field — this pipeline infers hourly vs. annual from magnitude

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

**CLOSED, package 21 (Rule D — tracked, tested placeholder, no live case observed).** Re-checked
against the current corpus: no posting in the $1,000-$5,000 ambiguous band observed live. The
$1,000 threshold stands, pinned by its own test.

## 29. CLOSED, package 21 — Gig-platform / part-time-freelance postings appear in the panel alongside full-time roles — is that the right scope?

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

**CLOSED, package 21 — ruling: filter from pay statistics, keep and mark in the listing.** Verified
directly against the committed corpus before implementing anything: the pay-statistics candidate pool
(SW-classified, `period=='year'`) already excludes gig/freelance postings STRUCTURALLY. **Correction
(adversarial review):** this entry originally claimed "3,308 of 3,314 (99.8%) are excluded because
they are paid hourly" — arithmetically impossible against the corpus (only 3,626 hourly rows exist in
total) and not reproducible under any keyword set tested. Re-verified with anchored whole-word
matching (the original unanchored scan also inflated the keyword-hit count — "contract" matched
"Contractor Program Security Officer"): of 4,680 postings matching common gig/freelance title words,
67.6% state no compensation at all, 28.3% are hourly, 3.5% are annual. The dominant real reason
gig-keyword postings never reach the pay pool is that most never state pay at all, not that they are
paid hourly. What the gate does verifiably protect: the postings that ARE annual+software-classified
and match a gig keyword are internships (a real USAF program among them), blockchain "Smart Contract
Engineer" roles, and "Contract to Hire" salaried positions — none of them gig/freelance work, and a
title filter would have wrongly excluded all of them. **Rule used: the existing structural gate
(period=='year' + SW classification) already implements the ruling; no new filter was built, because
building one on title text would remove genuine roles without being the mechanism that actually keeps
gig postings out.** For the listing: `PostingPay.tsx`'s new `PeriodNote` marks every non-annual-period
posting "not annual" with a tooltip explaining it is excluded from every salary median, wherever pay
renders (`/openings` and `/work` both).

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

**CLOSED, package 21 (Rule A — blocked credential, disclosed).** `GEMINI_API_KEY` is still absent
from this session's environment — checked directly, not assumed. The merge code is real and tested;
the remaining gap is the credential itself, whose absence stays disclosed rather than worked around.

## 31. CLOSED, package 21 — YC's Work at a Startup and Wellfound (tier 1.3) — both probed live, both closed, neither wired

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

**CLOSED, package 21 (Rule A for Wellfound/WaaS, Rule D for the YC-companies idea).** Wellfound and
Work at a Startup remain genuinely auth-gated, correctly not bypassed. The companies-API seed-hint
idea stays a recorded, low-priority backlog option.

## 32. CLOSED, package 21 — 16 of 14,813 postings-with-compensation (0.11%) carry an implausible min/max ratio — traced to the SOURCE ATS's own structured field, not this pipeline's parsing

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

**CLOSED, package 21 (Rule D — small, tracked residual, not a live defect).** 0.11% of postings-
with-compensation, disclosed via hover title, no fabricated correction. Stays as-is; #33's own
residual below is closed the same way, for the same reason.

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

**CLOSED, package 21 (Rule D — small, tracked residual, not a live defect).** Same reasoning as
#32: 0.023% of postings, disclosed, no fabricated correction, stays as-is. No Tbilisi-based coverage
observed this package either.

---

# Package 14 — fixing what the external data-science audit found

## 34. CLOSED, package 21 — A vintage deflator was investigated for Tier 2 (Finding 2) and declined — disclosure shipped instead

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

**CLOSED, package 21 (Rule D — decision already made; sourcing question is backlog).** The decline
stands. An occupation-matched wage-growth series remains unsourced and is a future package's scope
call, not a live defect in this one.

## 35. CLOSED, package 21 — The new OECD wage-benchmark invariant (Tier 1, Finding 1) is a FLAG, not an ERROR — by design, not oversight

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

**CLOSED, package 21 (Rule D — deliberate design choice, documented).** FLAG stands. Nothing in
this package's own scope asks for stricter CI on an already-investigated, already-disclosed,
structurally-unfixable-by-a-number-change condition.

## 36. CLOSED, package 21 — Postings currency conversion (Tier 3.1) covers 14 currencies, not every currency observed live

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

**CLOSED, package 21 (Rule D — backlog scoping note).** Not extended — each currency remains a small
fraction of total postings, disclosed via a null `compensation.usd`, never estimated.

## 37. CLOSED, package 21 — The OECD wage benchmark (item #35) compares whichever pay basis a country happens to publish, not a composition-matched one

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

**CLOSED, package 21 (Rule D — safe-direction bias, documented, not urgent).** The bias only ever
pushes toward MORE flagging, never a false pass, on a FLAG-only check. Left as-is.

## 38. `/postings` fails the work order's own Lighthouse performance gate — RESOLVED in package 17 (see the resolution at the end of this entry)

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

**RESOLVED, package 17.** Both halves.

The architectural fix turned out not to need pagination. The route was carrying the whole array
because one page did two jobs: show fifteen countries' positions, and be the browsable list. Split
apart, `/work` ships a 154 KB pre-computed per-country summary (counts plus eight examples each) and
never fetches the full payload on any path — verified against the built chunk graph and the live
network, not just the source. It measures **1.00 performance and 1.00 accessibility**, from 0.79.
`/openings` is now the page that IS the list, still loads the full payload on demand, and still
scores 0.76 — which is the honest cost of a page whose entire purpose is 48,267 advertisements, and
is left as such rather than papered over. The two agree by construction: both counts are written by
the same `build_site_data.py` pass over the same array, and both files are committed by the refresh
workflow (they were not, until this package fixed that too).

`compensation.usd` is wired in, via one component — `PostingPay` — which renders the employer's
native figure first and never has a path that withholds it. The converted view is a `<Derived>` with
its rate, its year, and an estimate marker where the rate came from a different year.

*One correction to the record above, from package 17's own adversarial review: this entry's last
line said `/postings` performance was "not fully fixed", and three code comments cited it as the
standing record while a commit message claimed it resolved. Both were true of different moments and
neither said so. It is resolved as described here.*

## 39. CLOSED, package 21 — The OECD wage benchmark (item #35) compares a market-FX-converted published median against a PPP-adjusted OECD figure — two different currency bases, not one

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

**CLOSED, package 21 (Rule D — documented open investigation, not urgent).** Not investigated this
package — the check is FLAG-only and does not gate anything published. Stays a recorded backlog
question.

## 40. CLOSED, package 21 — Position.tsx still reads the pairwise `crosswalk` verdict — CoverageMap is correct by design, "Pay against cost" is a real, only partly-mitigated gap

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

**CLOSED, package 21 (Rule D — shipped partial mitigation stands).** Option (a) — the current
shipped state — stands. (b)/(c) are a future design call this package's own items don't touch.

## 41. CLOSED, package 21 — `postings-refresh.yml`'s reclaim bucket is uncapped and grows every run — a workflow timeout was added as a cheap safety net; whether to cap the bucket itself is still open

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

**CLOSED, package 21 — the bucket is now capped, with the exact risk this item warned against
avoided by design.** `build_probe_order()` gained `reclaim_cap`/`reclaim_cycle_key`: a ROTATING
partition (ISO week number selects which `reclaim_cap`-sized slice of a sorted ordering runs this
week), not a flat first-N truncation — a flat cap would have reintroduced a milder version of the
same destructive-refresh bug Tier 0.2 fixed, and a first implementation of the rotation itself had
exactly that overlap bug (caught by this package's own test before shipping: modulo-wrapping the
last, partial chunk re-included items the first chunk already covered). Fixed with a proper
ceil-division partition; a test now proves every company is reclaimed exactly once across a full
cycle of keys. `RECLAIM_CAP = 5,000` — checked against today's real scale (Ashby's own 961 verified
companies, the largest of the three providers) and set comfortably above it (>5x), so the cap does
not engage today for any provider; it exists for the growth this item warned about, not today's
load. Wired into all three harvesters (Ashby, Greenhouse, Lever) via a shared helper keyed on the
real ISO week, since `postings-refresh.yml` runs weekly. 17 tests, including the exact
overlap-regression case.

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

> Median advertised pay, software roles only - United States: **$205,000**
> (95% CI $202,000-$210,000, n = 1,807 distinct software roles posted 2024 or later)
>
> *(Package 16 superseded the $99,000 / n=1,117 figure first recorded here. That one excluded
> every 2026 posting through an FX bug and was 77% 2016-2017 federal listings — see #48 and #49.)*

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

**STAYS OPEN, package 21 — not in the work order's own 29-item Tier 3 list, flagged rather than
silently skipped.** This item sits directly downstream of #48 (the pay window) and #49 (FX substitution), both
explicitly re-derived this package. The chart this item describes IS effectively what's shipped: the
current, live figure — US $205,000, 95% CI $202,000-$210,000, n=1,783 (moved from n=1,807 by this
package's own #48/#49 re-derivation; the median itself held steady) — already matches option (a),
one country, interval shown. That reads as an implicit resolution of this item's own three-way
choice, not a coincidence: options (b) and (c) were never chosen, (a) is what the panel already does.
Left open formally, since no work order text explicitly ratified (a) over (b)/(c) for this specific
item — but the current shipped state and option (a) are the same thing.

**Package 30 triage: OPEN, and it is a one-line ruling rather than a piece of work.** The panel has
shipped option (a) — one country, US $205,000, 95% CI $202,000–$210,000, n=1,783 — for several
packages. Nothing is wrong on screen; what is missing is a decision that (a) is the answer, so that
nobody re-opens the three-way choice later. Two options, and the first needs no code:

  - **(a) Ratify what is shipped.** One country with its interval, because only the US has enough
    advertised-pay volume to price a year (see #49). This item closes with no change.
  - **(b) Revisit (b)/(c) — several countries, or a country picker.** Only worth doing if the
    coverage that made (a) necessary has changed, and #49 says it has not.

## 43. CLOSED, package 21 — Teranet's monthly index carries injected per-observation noise — disclose, aggregate, or drop?

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
against an observed 7.3-10.8% and an underlying trend of only **3.1-4.9% per year** (log-linear
slope; package 16 replaced the endpoint CAGR first quoted here, which rested on the two noisiest
quantities in the series and read 3.1-4.1%). The annual residual
autocorrelation stays at 0.39-0.42. **Noise dominates the annual series too**; no single Teranet
value, monthly or annual, is interpretable on its own, and only the multi-year direction survives.

**Decide:** whether to (a) keep only a multi-year direction with a chart-level note that no
individual Teranet value is interpretable; (b) drop Teranet and rely on the other Canadian housing
evidence; or (c) raise it with the publisher. This is a sharper choice than it first appeared -
option (a) is no longer "add a footnote about monthly values", it is "stop plotting a level".

**CLOSED, package 21 — recovered a signal for four of six cities, and fell back honestly for the
other two, instead of dropping either outcome.** The owner's own instruction: "fix the noise, and
use the data, act as a data scientist." A state-space local linear trend
(`scripts/derive_teranet_smoothed.py`, Kalman smoother) was fit per city, and validated against
OECD's own independent Canadian house-price index before being trusted at all — a levels-based
first version of that validation was proven unsafe by direct adversarial testing (smoothed pure
noise scored 0.9+ against the real OECD series for 5 of 6 cities), so the real test is the
quarter-over-quarter DIFFERENCED correlation plus a Monte Carlo null test.

The null test itself needed two further, independently-found corrections before its p-values could
be trusted. A first version fit the model to i.i.d. noise per draw, which collapses the model's own
level and trend innovation variances toward zero — a null with almost no real variability, too weak
to mean anything. The fix (a parametric bootstrap from each city's own fitted noise variances)
carried a second defect: simulating from an unanchored starting state let the model's own double
integration explode over the full monthly history, producing synthetic draws in the hundreds of
thousands against a real index that runs 80-430 — a null made artificially EASY to beat, the
opposite failure. Anchoring every simulated draw to the real fit's own starting level and slope
fixed both; verified directly by re-running the corrected pipeline, which is why the result below
differs from an earlier draft of this closure.

**Four of six cities passed: Toronto and Vancouver decisively (p=0.002), Halifax and Ottawa clearly
(p=0.014, 0.022).** Calgary and Montreal did not (p=0.110, 0.126) and remain on package 16's
raw-only treatment — the fallback path this decision always described, not a hypothetical that
happened to go unused. Full evidence, including the two null-test corrections, in
`docs/DATA-FITNESS.md` §5's own package-21 update. The four passing cities publish with their own
uncertainty band, labelled smoothed (`site/src/components/explore/Housing.tsx`'s `TeranetPanel`);
Calgary and Montreal render raw-only in the same file's `CityRibbons`, with the reason stated
inline, not silently absent from the site. Raw values for every city remain available via CSV
regardless of outcome — never a replacement for
`data/processed/teranet_national_bank_hpi.json`, which this package reads and never writes.

## 44. CLOSED, package 21 — Percentile transfer is not currently testable, and therefore not defensible

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

**CLOSED, package 21 (Rule A — blocked by data scarcity, correctly shelved).** Still only the US
clears the sample-size floor after this package's own 2-year window narrowing (#48) — narrower, not
wider. Transfer stays shelved (option a); percentile transfer is not shipped anywhere on the site.

## 45. CLOSED, package 21 — The postings panel covers 85 countries the site does not — scope expansion, or noise?

The site's editorial scope is **15 countries** (AE, AU, CA, DE, DK, ES, FI, GB, IE, IT, NL, NO, QA,
SE, US) across 73 cities. Its postings panel is not scoped to them at all. Measured on the current
corpus:

| | postings | share | countries |
|---|---:|---:|---:|
| Inside the 15 | 35,470 | 73.5% | 15 of 15 |
| **Outside the 15** | **8,241** | **17.1%** | **85** |
| Unresolved | 4,556 | 9.4% | — |

The largest out-of-scope entries are India (1,051), France (686), Brazil (607), Singapore (581),
Mexico (359), Thailand (348), Japan (320), South Korea (314) and Poland (281).

**This is not only a filter-list question.** Until package 16 removed it, the published
"median advertised pay by country" chart showed seven countries — and **three of them (France,
Singapore, Japan) are outside the site's own scope**. The chart invited a comparison between
countries the rest of the site does not cover, has no cost-of-living data for, and cannot compute a
years-to-home or take-home figure for. A reader could reasonably have read "Singapore $152,969" as a
destination this site supports. It does not.

Note also how thin some *in-scope* countries are: Qatar has 12 postings, Denmark 27, Norway 41, Italy
129. The panel is not merely wider than the spine, it is **wider and shallower** — 85 countries it
does not cover, and four it does cover with fewer than 150 advertisements each.

**Decide:** which of these the panel should be —

- **(a)** scoped to the 15, with everything else dropped at harvest time. Smallest, most consistent
  site; loses 17% of a corpus that cost real API budget to collect.
- **(b)** scoped to the 15 for every DERIVED figure and every default view, with the rest reachable
  behind an explicit "outside this site's scope" toggle. Keeps the data, stops it implying coverage.
- **(c)** an explicit scope expansion — pick the out-of-scope countries with enough volume to matter
  (IN, BR, PL at least) and give them the cities, cost-of-living and tax data the other 15 have.
  Much the largest piece of work, and the only option that makes the panel's breadth honest.

Package 16 did **not** choose. It made the current state legible instead: the country filter now
separates "countries this site covers" from "also in the harvest", so nobody reads the second group
as coverage. That is a stopgap, not the decision.

**CLOSED, package 21 — ruling: option (b), scoped for every derived figure and default view, rest
behind a clearly separated section.** `/openings`'s own optgroup split (package 16) already did this
for the country filter. The gap was `/work`'s `PublishedPay` panel (see item #52): it showed
`publishable` countries as headline chips with NO scope filtering at all — a single-posting swing on
any out-of-scope country (France sits closest, at 29 against the 30-posting floor, checked directly)
would have rendered it as an undifferentiated headline chip beside US/GB/CA the moment it crossed.
Fixed: `PublishedPay` now splits both its publishable and withheld rows into in-scope and a new
"Beyond our fifteen" section, using the same `core.citiesByCountry` spine `/openings` and `/work`'s
own section loop already use, with the same disclosure (FX marker, publish window, rounding note)
the fifteen's own rows carry. Nothing outside the fifteen can reach a headline figure without saying
so — including the branch that isn't exercised by today's data, verified directly rather than left
untested because nothing currently triggers it (adversarial review: an earlier draft of this closure
claimed France already cleared the bar, which was checked against the real corpus and found false).

## 46. CLOSED, package 21 — Three country names are deliberately unparsed, because the checking order would misassign a US place

`country_from_location()` checks, in order: exact ISO match, full US state name, the wide country-name
table, bare 2-letter US state code, then a city table. Package 16 added 31 country names to that
table and had to leave out three:

| Name | Would gain | Would break |
|---|---:|---|
| `panama` | 30 postings | `Panama City Beach, FL` → US becomes PA |
| `lebanon` | 6 | `Lebanon, OH` → US becomes LB |
| `jordan` | 1 | `West Jordan, UT`, `South Jordan, UT` → US becomes JO |

Each collides with a US place whose only US signal is the **2-letter state code, which is checked
after the country table**. The same ordering already produces a documented wrong answer in the other
direction: `China Lake, CA` resolves to China rather than the US, while its own sibling record
`China Lake, California` resolves correctly.

Promoting the 2-letter state-code check above the country table would fix all four of these. It
would also change any location where a bare 2-letter token that happens to be a US state code sits
beside a country name — and `Delhi, IN` (Indiana) is the shape that makes this a real trade, not an
obvious win. That case already resolves to US today, so the change would not create it, but it would
entrench it.

**Decide:** whether to (a) reorder, accepting the `Delhi, IN` class of error to fix the
`Panama City Beach, FL` class; (b) build the genuine city+state/country co-occurrence check that
gets both right, which is the correct fix and the most work; or (c) leave the order alone and accept
that three country names stay unparsed. Package 16 took (c) and disclosed it.

**CLOSED, package 21 (Rule D — deliberate, disclosed choice stands).** Option (c) stands. Options
(a)/(b) remain a future package's scope call if the collision cost ever grows.

## 47. CLOSED, package 21 — Puerto Rico is mapped to the US, not to its own ISO code

`"puerto rico"` resolves to **US**. Thirteen postings read "San Juan, Puerto Rico", "Arecibo, Puerto
Rico" and similar; nine of them are USAJOBS federal roles that were already labelled US.

Mapping to `PR` would have been the literal ISO answer and would have moved those nine off US.
Mapping to `US` resolves the rows without this pipeline taking a position on territorial status, and
leaves every existing label untouched. Two other cases were treated the opposite way and are worth
naming, because the reasoning differs: `Bahrain Island` and `Kuwait` are US-government postings
physically located abroad, and those were moved off US, on the grounds that a migration site's
question is where the job IS, not who signs the cheque.

**Decide:** whether territories should ever appear separately from their sovereign state. It affects
nothing today — PR is not in the 15 either way — but it will the moment anyone counts "countries in
the panel".

**CLOSED, package 21 — ruling: give it its own code, PR.** `"puerto rico"` now maps to `PR`, not
`US`, in `postings_common.py`. Re-derived against the real corpus: 13 postings moved from US to PR
(matching this item's own count exactly). Effect on the US published median: **none** — re-ran
`apply_postings_annotations.py` and the US figure held at $205,000 (n unchanged in the software+2024
window before this move; the 13 PR rows were never in that population, all pre-dating the pay window
or non-software). PR itself: 6 postings with compensation, 0 software-classified, correctly withheld
— appears only in `/work`'s new "Beyond our fifteen" section (item #45/#52), never a headline figure.

**Correction (adversarial review): the spelled-out-name fix was only half the picture.** 46 further
postings read `"{municipality}, PR"` (the US-postal-abbreviation form — Caguas, San Juan,
Barceloneta, Carolina, Ponce, Bayamon, Mayaguez) and stayed unresolved, because `PR` is neither a US
state code nor in the country-name table. Fixed the same way, narrowly: a dedicated check keyed on
these seven SPECIFIC known municipality names co-occurring with a `, PR` suffix, deliberately not a
bare abbreviation rule — `PR` is also Brazil's own Parana state code (Curitiba is its capital), and a
generic rule would risk exactly the substring-collision class this pipeline has been bitten by
before. Re-derived: PR's own resolved count moved 13 → 59 (46 filled, 0 reassigned — these were
blanks, not corrections), all still non-software / no compensation, so this also changes no
published figure. Now genuinely complete for the two location formats this corpus actually uses.

## 48. CLOSED, package 21 — How wide should the advertised-pay window be? Package 16 chose three years without authority to

Until package 16 the `/postings` median pooled every vintage in the corpus. Measured, that was not
a summary of anything: the US figure rested on **714 rows from 2017 and 148 from 2016**, 872 of them
USAJOBS federal listings, and **not one row from 2026** — while 31,829 of the 48,267-row corpus is
2026. The cause was an FX bug (see #49). With it fixed, the pooled median became **$175,000**,
sitting between a 2026 population near **$204,000** and a 2016-2017 one near **$87,000**.

A median between two populations $115,000 apart describes neither. So the published figure is now
limited to postings from **2024 onward**: **US $205,000, 95% CI $202,000-$210,000, n = 1,807**.

**Three years is a judgement, not a measurement.** It is wide enough to hold a usable sample and
narrow enough that nominal pay has not moved much across it, but nothing in the data picks it. The
window also has a cost that is real and one-sided: **every USAJOBS row is dated 2016-2018**, so
restricting to recent postings removes US federal listings entirely and leaves private ATS boards.
91.3% of what remains comes from a single provider. The panel states this; it does not resolve it.

**Decide:** (a) keep three years; (b) narrow to the current year only — n = 1,561, and the
provider concentration gets worse, not better; (c) publish two figures, federal and private, and
stop pretending one median covers a labour market that pays $87,000 and $217,000 for the same
title; or (d) deflate the older postings to current prices and pool them, which needs a deflator
this repo does not currently hold and would mix an index into an advertised-pay figure.

**CLOSED, package 21 — ruling: two years, not three.** `PUBLISH_FROM_YEAR` moved from 2024 (three
years: current + two behind) to 2025 (two years: current + one behind). Re-derived every affected
figure: US $205,000 unchanged (n 1,810→1,783); GB $165,000 unchanged (n 123→122); CA $118,000→
$119,000 (+0.8%, n 67→64). No publishable country dropped below the 30-posting floor from the
narrower window — the five already-withheld countries (DE/FR/AU/SG/IT) stay withheld, unchanged.
Every figure moved by at most one rounding step or held exactly steady; none of the underlying
claims in item #48's own text (the bimodal-mixture risk this window exists to prevent) changed.

## 49. CLOSED, package 21 — The current year cannot be priced for any country except the US

`fx_rates` comes from the World Bank's annual period-average series, which ends at **2025**, and
`normalise.to_usd()` refuses to substitute a neighbouring year's rate — correctly, and that rule
should stand.

The consequence is severe and was invisible until package 16 went looking. For every non-USD
country, **88-92% of annual-pay postings cannot be converted**: Great Britain 276 of 312, Canada
270 of 306, Germany 93 of 101, France 95 of 104 — almost all of them 2026. So the withheld
countries on `/postings` are not simply thin. Their recent data is *unpriceable* until the rate is
published, and the sample-floor story the site tells about them is at best half the reason.

Package 16 fixed the US half of this: USD→USD is the identity and needed no rate at all, which
restored 1,566 US postings and is not an exception to the no-substitution rule. Nothing analogous
exists for GBP or EUR.

**Decide:** (a) wait for the World Bank's 2026 rate and accept that the panel is a year behind for
every non-US country; (b) add a second, clearly-labelled FX source with a shorter publication lag
(the ECB daily series package 16 already verifies against reaches the current day) and state per
figure which source priced it; or (c) publish non-US figures in their **native currency**, unconverted,
which is the only option that needs no rate at all and is arguably more honest for a
migration-comparison site — at the cost of losing cross-country comparability, which is the whole
point of the panel.

Option (b) is the one that would make the panel work as designed. It is also the one that puts two
FX sources in the same repo, which this project has so far avoided on purpose.

**Package 17 update — (c) was implemented for the native figure, and a bounded version of the
problem remains.** Every posting now renders in its employer's own currency, always, with no code
path that withholds it; the converted view is a marked estimate reaching at most two years, and
five countries publish where one did. That does not close this item. GB, CA, FR and DE's medians
rest 76–94% on the 2025 rate standing in for 2026 — every one of them is an estimate wearing a
national label, and they are only as good as the assumption that a year's FX drift is tolerable at
this precision. The last observed one-year move is −4.2% for EUR and −7.1% for SEK. **Option (b)
remains the only fix that makes the panel work as designed**, and the decision it needs — two FX
sources in one repo — is unchanged.

**CLOSED, package 21 (Rule A — blocked source keeps its honest gap).** Re-checked with fresh
evidence, not assumed unchanged: after this package's own re-derivation (Puerto Rico #47, two-year
window #48), GB's published median still rests **90.2%** on FX-estimated (substituted-year) rates,
CA **78.1%** — both at or above package 17's own 76-94% figure, confirming the World Bank's rate
series still ends at 2025 and nothing has improved on its own. Option (b) (a second FX source)
remains the only real fix and is not built this package — a genuine infrastructure decision outside
this package's own Tier 1/2 scope, correctly left open rather than worked around with option (c)'s
own comparability cost or a silent substitution this pipeline's own rules already forbid.

## 50. CLOSED, package 21 — `/openings` is nearly unreachable, and `/postings` redirects to the page that is not the list

Package 17 split the old `/postings` in two: `/work` (position + eight openings per country) and
`/openings` (the whole browsable list, its filters and its map). `/postings` redirects to `/work`.

Three things follow that were not deliberately chosen:

* **`/openings` has no navigation entry.** The nav collapsed from two items to one (`Position &
  openings` → `/work`), which was the work order's intent, but `/openings` was created afterwards
  and never added. It has exactly two inbound links in the entire site, both inside `/work`'s prose.
* **`/postings` was the browsable list, and now redirects to a page that is not.** A reader who
  bookmarked `/postings` to search advertisements lands on a page showing eight per country. The
  redirect preserves the query string, but `?country=DK&level=senior` means nothing to `/work`,
  which has no such filters. `/postings → /openings` is arguably the honest redirect; `/work` is
  arguably the better destination for someone who has forgotten what the page was.
* **They cannot both be right.** Whichever way it points, one class of old link lands somewhere
  its author did not mean.

**Decide:** whether `/openings` earns a nav entry (a third item, against a nav deliberately kept to
four), whether `/postings` should redirect to `/openings` instead, and whether the filter parameters
the old route accepted should be forwarded to `/openings` rather than dropped on `/work`.

**CLOSED, package 21 — ruling: fix it, `/postings` should reach the postings.** `main.tsx`'s
`/postings` route now redirects to `/openings` (the real browsable list), not `/work`. `/work`
already carries a real `<Link to="/openings">` in its closing paragraph — kept, not rebuilt. Residual,
disclosed rather than fixed: `Openings.tsx` does not read `country`/`level` from the URL to
pre-populate its filters (they are local component state), so the query string a stale `/postings`
link carries still goes unused on arrival — a distinct gap from which PAGE the link lands on, which
is what this closes.

## 51. CLOSED, package 21 — The classifier's precision is now visible per country, and it is visibly imperfect

Until this package the title classifier's output was an aggregate: a share, a count, a median. `/work`
is the first surface that shows **individual classified rows under a country heading** — "N software
openings in Canada" followed by the rows themselves. Today that renders *Wide Format & Zund Lead*
(Canada), *Senior Venture Lead* and *QA Lead* (Germany), *Sr. Sales Engineer* (Australia).

This is not a new defect. `title_classifier_eval.json` has always reported SW's precision honestly,
and the classifier is the correct set to show: the page must count the same rows its published
medians are computed from, or it contradicts itself — which is exactly why package 17 ships the `sw`
flag rather than re-deriving software from titles in the browser. What changed is that the error rate
is now legible to a reader rather than recorded in an evaluation file.

**Decide:** (a) leave it — the set is the honest one and the eval is published; (b) raise the
probability floor for the rows that are *displayed* while leaving the medians on the full shipped
set, which makes the visible list cleaner than the counted one and must be captioned as such; or
(c) caption the panel with the classifier's measured precision so a reader can price what they see.
(b) is the tempting one and the one that reintroduces two different answers to "how many software
openings", which is the disagreement this package's `sw` flag exists to prevent.

**CLOSED, package 21 — ruling: option (c), caption with the measured precision.** `Work.tsx`'s
per-country `Openings` component now shows the classifier's own out-of-fold F1 and 95% CI (0.82,
CI 0.76–0.87, against 116 hand-labelled titles) beside the "N software openings in {country}" count,
on both the empty-figures and the has-figures rendering paths. Sourced from `title_class_summary.
class_decisions.SW`, already present in the committed pipeline data and already passed through into
the slim `openings.json` `/work` loads — the only gap was the TypeScript type never naming the field,
now added. F1 (not raw precision) is the number used: it is the classifier-quality metric this
codebase already ships with its own CI, and building a new fetch just for a marginally different
statistic was not worth the added surface area.

## 52. CLOSED, package 21 — `/work`'s published-pay panel names 49 countries on a page framed around fifteen

The withheld table lists every country the harvest reached with any software row — 49, of which 35
are outside the site's fifteen-country spine, including France, which is simultaneously shown as a
**publishable** headline figure. The old `/postings` earned this with an explicit sentence ("the
harvest also reaches N countries this site does not cover"), which package 17 restored to
`/openings` but not to `/work`.

**Decide:** whether `/work`'s withheld table should be restricted to the fifteen in scope (losing
the honest disclosure that the harvest is wider), carry the same out-of-scope sentence `/openings`
now carries, or separate in-scope from out-of-scope rows the way `/openings`' country dropdown
already does.

**CLOSED, package 21 — ruling: separate in-scope from out-of-scope, matching `/openings`.** Closed
together with #45 above (`PublishedPay`'s new split covers both the headline/publishable rows this
item names as the sharper problem and the withheld table). **Correction (adversarial review):** this
entry originally claimed France was "still publishable on the current corpus" — checked directly
against the committed data and found false: France sits at 29 distinct software roles, one short of
the 30-posting publish floor, and is not currently publishable at all (it appears only in the
withheld/"too few" table, both in-scope-equivalent and beyond-our-fifteen). Zero out-of-scope
countries currently clear the publish floor. The split itself is not therefore untested busywork:
it exists for the moment one does, which the panel's own numbers put a handful of postings away —
verified the branch renders correctly (FX-estimate marker, publish-window text, rounding note, all
matching the fifteen's own disclosure) rather than trusting it unexercised.

## 53. CLOSED, package 21 — `levels.fyi` converts outside `normalise.py`, at a pinned rate with no year, and it renders on 57 city pages

`normalise.py` opens by claiming that every wage-figure conversion in the pipeline goes through it
and that no component converts inline. Package 17's adversarial review found that this is not true
and was not true when written. `scripts/src_levels_fyi.py` defines a local `to_usd()` over
`data/metrics.json`'s `fx_rates_usd_base` — a pinned snapshot whose own note reads *"Snapshot early
2026… Comparisons robust to small FX drift"* — and the resulting `median_total_comp_usd` renders on
**57 of 73** city pages via `registry.ts`.

It obeys none of the seven rules: no year-matching (there is no year to match), no chain, no
estimate marker, and no refusal path — a currency missing from the block silently yields `None`.
This is exactly the shape of thing package 17 spent its Tier 1 fixing for postings, one module over.

**Why it is not simply a bug.** The pinned block exists on purpose: it is shared across collection
agents so that figures gathered by different agents on different days are mutually consistent.
Moving one consumer onto the World Bank annual series would make that consumer inconsistent with
every other user of the block, and would also expose levels.fyi captures to the same
publication-lag problem package 17 has just spent a package bounding — with no posting date to
match against, since a levels.fyi capture is a scrape of an aggregate, not a dated observation.

**Decide:** (a) leave it, and keep `normalise.py`'s docstring narrowed the way package 17 narrowed
it, so the claim matches the code; (b) migrate `src_levels_fyi.py` onto `normalise.to_usd()` with
the capture date as the conversion year, accepting that it may then refuse figures it currently
converts; or (c) keep the pinned block but route it through `normalise.py` as a named, dated source
so the conversions at least carry a chain and appear in the same audit as everything else.

Not attempted in package 17: it is outside the work order, it changes a value that renders on 57
pages, and the trade it involves is a project decision rather than a defect.

**CLOSED, package 21 (Rule D — deliberate design tension, documented).** Not attempted here either
— same reasoning: it changes a value rendering on 57 pages, and none of this package's own Tier 1/2
items ask for it. Option (a)/(b)/(c) remain a future package's choice.

## 54. The de-duplicator's ground truth is keyed to array position — RESOLVED in package 18

Package 17 found the weekly refresh workflow had never run `classify_titles.py`,
`dedupe_postings.py` or `apply_postings_annotations.py`, while package 16's validator requires
their output — so every scheduled run since package 16 has been blocked at Validate and committed
nothing. Adding the three steps clears three of the four blockers. **It does not clear the fourth.**

Run on a fresh 48,708-row harvest (workflow run 32751240590), `dedupe_postings.py` stops with:

> `FATAL: 240 of 240 labelled endpoints no longer match the corpus -- postings.json has changed
> since labelling. Re-label before trusting any threshold.`

**The guard is right and should not be weakened.** Its threshold is tuned against 120 hand-labelled
pairs, and a threshold tuned on labels that no longer point at the pairs they describe is worse
than no threshold — the de-duplicator deletes rows, and package 15 measured its precision precisely
so that it could not do so unmeasured. The comment above the check even anticipates corpus growth.

**But the labels are keyed by array index** (`"i": 15125, "j": 15156`), and a harvest that adds,
removes or reorders a single row invalidates all 240 endpoints at once. As written, the check can
only ever pass on the exact `postings.json` the labels were built from. A weekly refresh changes
that file every week, on purpose. So the guard does not merely detect drift — it makes the
de-duplicator unrunnable in the pipeline it is part of.

**Each label already carries the stable identity.** Alongside `i`/`j` it stores the display string
the pair was labelled from (`"Program Manager, Capabilities @ hadrian-automation / Los Angeles,
CA"`), which is exactly what the guard compares. Re-resolving each labelled endpoint by that string
instead of by position would survive any re-harvest for as long as the posting is still in the
corpus.

**Decide:** (a) re-key the ground truth to the stored display strings (or to posting `id`), and
have the check report *how many pairs survived* and refuse only below a stated floor — this is the
real fix, and the decision it needs is what that floor should be, since expired postings shrink the
sample every week and a threshold tuned on eleven surviving pairs is not the one package 15
measured; (b) re-label on a schedule, which is manual work at whatever cadence the corpus drifts;
or (c) freeze the clusters — run the de-duplicator only when re-labelled and let the refresh reuse
the committed `postings_duplicate_clusters.json`, accepting that postings harvested since the last
labelling are never de-duplicated and the re-listing rate drifts.

Not attempted here. Any of the three changes what "the labelled sample" means and what the measured
precision applies to, which is a methodology decision rather than a defect — and this is an
unattended run.

**RESOLVED, package 18 — option (a), with the floor chosen from measurement and one thing option
(a) did not anticipate.**

The labels are keyed by `(id, occurrence)`. Not by `id` alone: three ids are carried by two rows
each and **one labelled pair sits on exactly that case** — pair 115 is two rows of
`usajobs:464770500`, one announcement filed under two occupational series, labelled `same_job=true`
at cosine 1.0. Keying on the id would have paired a row with itself, a true positive no threshold
could ever fail. The display string is kept as corroboration and explicitly rejected as a key: 240
endpoints use 219 distinct strings and 43 of those match more than one row, because near-duplicates
share text, which is what these labels describe.

**The floor is per band, not a total, and the reason is measured.** Drop the `[0.98,1.00]` band and
96 of 120 pairs remain — an 80% survival rate — and the tuning reports precision 1.000 recall 0.000,
because 23 of the 32 positive pairs live in that band. A total-count floor passes that. The floor is
**12 surviving pairs in every cosine band and 12 of each `same_job` class**, and the class half is
documented as guarding a future re-labelling rather than today's data: over 4,000 band-satisfying
survivor sets it never once fired.

**What option (a) did not anticipate: an expired posting is not the only way a pair leaves.** The
first implementation treated any id that resolved to changed text as fatal, on the reasoning that it
meant id reuse. Run 32765692993 disproved that in production — the re-key took 240 mismatches down
to **3**, and the run died anyway on three employer title edits (`Sr. Product Designer` → `Staff
Product Designer`). Measured across real consecutive harvests, 0.041%–0.536% of surviving ids have
their display string change each run, and most of those are USAJOBS *locations* drifting because
`positionlocations[0]` picks one of several. So an edited advert now drops its pair like an expired
one; a formatting-only edit does not even do that; and the run is refused only when the edited share
exceeds 25%, which is what a provider recycling its id space looks like.

**A third guard was added, because the floor alone guards the wrong thing.** What matters is not
that the threshold is selected from a smaller sample but that a *different* threshold changes how
many rows are deleted — 0.98 → 0.95 takes removable rows from 2,884 to 3,622. `EXPECTED_THRESHOLD`
refuses any run whose survivor set selects a different threshold at all.

**The remaining risk, stated rather than closed.** All 120 labelled pairs are intra-company across
80 companies, and the one pre-package-14 refresh in this repo's history lost 55% of its ids by
losing whole employers at once. Simulated, the floor survives company truncation to about 30% and
refuses at 55%. Package 14's additive company ledger and reclaim bucket exist to stop that
recurring, and the fresh harvest in run 32765692993 returned 48,691 rows against 48,267 committed —
no truncation. If it does recur, the refresh stops with a clear message instead of tuning a
threshold on a quarter of its sample, which is the right failure.

## 55. WIPO's PDF delivery now sits behind a JS challenge on every URL shape tried — RESOLVED in package 20

Package 19 fixed the actual defect this source shipped with — flattened-text extraction losing the
US and the Netherlands (see `REPORT-P19.md`, `docs/DATA-FITNESS.md` §11). Getting a current PDF to
parse turned up a second, unrelated problem: **there is currently no way to fetch the WIPO GII PDF
with a plain unattended HTTP request, on either URL shape this repo has ever used.**

**Evidence.** The 2024-edition URL this source shipped with
(`tind.wipo.int/record/50062/files/...`) is simply dead now — an empty response body, not a 404,
exactly what this package's own work order predicted might have happened by now ("It is now August
2026 — a newer GII almost certainly exists"). The current
2025 edition lives at `tind.wipo.int/record/58864/files/wipo-pub-2000-2025-...-crossroads.pdf` (found
via the 2024 PDF's own DOI, `10.34667/tind.58864`, resolved through `doi.org`) — but a plain
`requests.get()` with the same browser User-Agent that has always worked for this host gets **HTTP
202, `x-amzn-waf-action: challenge`, an empty body**, not the PDF. So does the newer
`www.wipo.int/web-publications/...` asset path. Both are the identical AWS WAF JS challenge,
confirmed from the response headers on both — this is not one broken URL, it is WIPO's delivery as a
whole now gating PDF downloads behind a challenge only a real browser session can solve.

**What unblocked it for this package.** Navigating to a WIPO page in an interactive browser solves
the challenge silently and sets an `aws-waf-token` cookie; replaying that cookie via `requests`
then fetches the PDF normally (28,547,423 bytes, 27.2 MB, verified as the real 2025 edition). That is how the file
`src_pdf_indices.py` now parses was obtained. It is a one-time, by-hand step — there is no automated
substitute for it in this repo today, and a scheduled job has no browser session to solve the
challenge with.

**This is a real gap, but it is not an active outage.** `wipo_gii` is part of the wage-spine pipeline
(`make pipeline`), which — unlike `postings-refresh.yml` — runs only when a human or a work order
triggers it, never on a schedule; there is no `data-refresh.yml` this repo runs weekly against it.
`fetch()` also reuses an existing non-empty `data/raw/<source>/` file before ever attempting the
network (`scripts/_common.py`'s own caching), so **today's committed `data/processed/wipo_gii.json`
is correct and current** (2025 edition, all 139 rows, all 15 of our countries verified against WIPO's
own published summary) precisely because it was built from that manually-fetched, locally-cached
file. The gap only bites the *next* time someone runs the full pipeline from a clean checkout with no
local cache — `make pipeline-fresh`, or any CI job that did start refreshing this source in the
future — at which point `wipo_gii` would fail closed exactly as EF EPI already does on a genuine
outage: `write_processed(source_id, {}, ...)`, `status: "unavailable"`, 0/15 countries, loud in the
log and in provenance, never a stale or silently wrong number.

**Decide:** three ways to close the gap, in ascending cost:

(a) **Commit the fetched PDF as an explicit input, the same way `levels_fyi`'s capture already is.**
`.gitignore` already carries that exact exception with its own stated reasoning ("this one is an
INPUT, not a cache... nothing re-downloads it, so dropping it would make that step unreproducible")
— WIPO GII would be the second case of it, not a new pattern. Cheapest change (one `.gitignore`
line, ~27 MB in the repo), and matches GII's real publication cadence: it is an annual report, so
"a human re-fetches it by hand once a year when a new edition drops" is not a heavier burden than
this source already carries today. The `data/raw/wipo_gii/wipo-gii-2025.pdf` this package fetched is
sitting ready for this if chosen.

(b) **Leave it uncommitted, documented.** No repo-size cost, but the *next* clean-checkout full
pipeline run silently loses this one source until someone notices the "unavailable" status and
re-runs the browser-cookie-harvest step by hand. Since nothing currently schedules that full
pipeline run automatically, this may simply be acceptable — but it means "re-fetch `wipo_gii`" joins
the list of manual steps a future work order needs to know about, same as `levels_fyi`'s capture
already is.

(c) **Build unattended WAF-solving into the pipeline** (a headless browser, e.g. Playwright, to
solve the challenge and extract cookies without a human). Ruled out here as disproportionate to what
this package was asked to fix — a new, heavy dependency for two PDF values, on a source that is not
even scheduled — and not guaranteed to work besides: WAF vendors specifically target headless/
datacenter traffic, so there is no assurance this would succeed where a plain browser-UA request
already fails.

**Not decided here.** (a) is the smallest change and follows an existing precedent exactly, but
committing ~27 MB of binary PDF to git history is a repo-hygiene call with its own cost (that
history never shrinks even if the file is later removed) — the kind of call this work order's own
preflight reserves for the owner rather than a package unilaterally deciding it. Recorded so the
choice is made once, deliberately, rather than by whichever future package next needs this source to
actually refresh.

**RESOLVED, package 20 — a fourth option, found by reading what WIPO's own ranking page requests
rather than what its PDF-delivery endpoints do.** `wipo.int/gii-ranking/en/` is a Nuxt app, and it
loads its own ranking table client-side from a plain CSV:

```
https://www.wipo.int/gii-ranking/data/bc_results_gii_2025.csv
```

Verified directly, outside a browser: HTTP 200, 29,225 bytes, 140 lines (139 economies), no WAF, no
JS challenge, no cookie, a plain `urllib`/`requests` call with a browser User-Agent. It carries
`iso3` (`CHE`, `SWE`, `USA`, ...), so the extraction now matches on an exact ISO3 code instead of a
free-text country name — removing the mechanism that cost the Netherlands its row in the first
place, not just working around WIPO's PDF delivery. All 15 site countries' rank and score match the
values package 19's PDF parser had already shipped, checked once by hand before writing any code
(exploratory CSV fetch) and once more programmatically after (`REPORT-P20.md` Gate 3, comparing the
real committed pre-package-20 file against the real committed post-package-20 file) — two
independent extraction paths (word-geometry PDF parsing, CSV) agreeing on all 15 rows, which is also
a second, independent confirmation that package 19's parser was correct. That comparison is a
one-time verification, not a standing test: a permanent test asserting "matches these exact values"
would itself become the [[feedback-tests-pinned-to-a-snapshot]] mistake the moment GII publishes a
2026 edition and these numbers correctly change.

None of options (a)/(b)/(c) were needed. No PDF is committed to the repo (`data/raw/wipo_gii/` holds
only the CSV now, still gitignored, still a disposable cache — not an exception like `levels_fyi`'s).
`scripts/pdf_table.py` is unaffected and unremoved: EF EPI still needs it (checked in package 20,
Tier 2 — EF EPI's own ranking page has no equivalent public data file, see `src_ef_epi.py`'s own
docstring for exactly what was checked). `wipo_gii` moved from `src_pdf_indices.py` (now deleted) to
its own `src_wipo_gii.py`; the fetch is unattended-safe end to end, and the underlying problem —
"WIPO's PDF cannot be fetched without a browser" — is gone rather than mitigated, because `wipo_gii`
no longer fetches a PDF at all.

**Traded one visible problem for a quieter one, stated plainly rather than left implicit.** The PDF
URL failed loudly (a WAF challenge, an obvious non-200). The CSV URL is year-stamped with no
confirmed retirement behaviour, so the more likely failure mode now is the URL quietly continuing to
serve 2025 data after a 2026 edition exists elsewhere, with no error at all — found by this
package's own adversarial review, which also found an earlier draft of `src_wipo_gii.py` had
asserted (not established) that a stale CSV would 404 the way the dead 2024 PDF URL did. Mitigated,
not eliminated: the script now probes for next year's URL and flags loudly if it already exists (see
`REPORT-P20.md` Gate 11, `docs/DATA-FITNESS.md` §11). `EDITION_YEAR` still needs a human to update
when WIPO ships a new edition — this closes the fetch-mechanism problem #55 was about, not the
separate, ongoing need for someone to notice when GII's edition changes.

## 56. CV storage was explicitly out of scope for package 22 — deferred to package 23, with what it will need

Package 22 built the CV reader end to end — upload, client-side text extraction, PII stripping, the
model call, applying the result to the profile form — and deliberately stops there. §0 of its own work
order named storage out of scope; nothing in this package writes a CV, its extracted text, or its
redacted text to any persistent store anywhere. The browser holds the reviewed text only in component
state (`CvUpload.tsx`), for the lifetime of that page load; a refresh loses it. The Worker
(`worker/src/index.ts`) forwards `cvText` to Gemini and returns the parsed profile — it is never
written to the Durable Object, a log, or anywhere else server-side.

**What exists today, load-bearing for whatever package 23 decides.** Tier 1's whole design rests on
"the file itself never leaves the browser, and the PII-stripped text is the only thing that does" (see
`site/src/cv/stripPii.ts`'s own header) plus "nothing is sent until the reviewed text is explicitly
confirmed" (Tier 3, checked directly via `performance.getEntriesByType('resource')` showing zero
requests before confirmation). Any storage design has to either preserve both properties deliberately
or say plainly which one it is giving up and why — neither should erode by accident because a later
package added a write path without re-reading why this one didn't.

**What package 23 will need, if CV storage is taken up:**
- **A decision on WHAT gets stored** — the raw file, the extracted text, the PII-stripped text, or only
  the derived profile (occupation/years/skills/education/languages). Each is a materially different
  privacy posture; this package's own design assumed none of them get kept, so this is a fresh decision,
  not an extension of an existing one.
- **A second, separate consent/disclosure.** Gate 11's Article 50-style labelling covers "a model read
  this CV," not "this was kept." Storing anything is a distinct processing purpose under the same
  regulatory frame this package already took seriously, and needs its own explicit disclosure, likely
  its own opt-in — not folded silently into the existing "AI-assisted" chip.
- **An identity concept, which does not exist anywhere in package 22.** The daily counter
  (`worker/src/dailyCounter.ts`) is a single global count, not per-user; there is no login, session, or
  any notion of "whose CV is this." Storage implies retrieval, which implies answering that question
  first.
- **A deletion path designed in from the start**, not retrofitted after storage ships — cheap to build
  alongside the write path, expensive to bolt on once real data exists that needs it.

**Not decided here.** Whether package 23 stores the CV at all, or only ever the derived profile, is a
product decision this package's own work order left to the owner — recorded so the choice is made
once, deliberately, rather than by whichever package next needs a returning user to imply it.

## 57. CLOSED, package 24 — The `/work` redesign and CV storage both remain open; the redesign should not start before package 23's fixes are live

Package 23's own work order was explicit about sequencing: *"A redesign of the page follows separately.
This package fixes what is wrong underneath it. Do not redesign anything here; a redesign built on a
leaking, non-deterministic reader is wasted work."* That package fixed the CV reader's own correctness
defects (a PII leak that contradicted its own disclosure, non-deterministic output, a result that
vanished on apply, unused schema fields, an undefined years figure) — see `REPORT-P23.md`. Recorded
here as its own line item so the dependency is not lost between packages: whoever picks up the `/work`
redesign should confirm package 23's fixes are live first, not assume it from the redesign's own work
order alone.

CV storage (#56, above) is the other open item this same package's finish protocol named, unchanged by
package 23 — still explicitly deferred, still needing the same four decisions #56 lists (what gets
kept, a second consent layer, an identity concept, a deletion path) before any package builds it.

**Not decided here.** Neither when the `/work` redesign begins nor what it changes — only that it
should not begin before this package's own fixes are confirmed live, which is a sequencing fact, not a
design decision.

**CLOSED, package 24 — package 23's fixes are live.** Package 23's own Gate 12 verified the PII fix,
determinism, the apply-persistence fix and the schema cleanup against the deployed site, not just the
build (`REPORT-P23.md`). The `/work` redesign (this package) confirmed that verification before
starting its own Preflight. Sequencing satisfied; the CV-storage half of this same finish protocol
(#56) is unrelated to a presentation-only redesign and remains its own open item, unchanged.

## 58. CLOSED, package 25 — Norway's own USD estimate path shifts a regular-pay figure with a total-earnings-calibrated premium — F13, inherited from #21, still unresolved

Package 11's own remediation update to item #21 (finding F13, above) found that `computeEstimateUsdYear()`
(`site/src/data/profile.ts`) shifts Norway's `usd_regular_pay` combo (bonus excluded) using
`experience_gradient.json`'s own Norway entry — sourced from "SSB 11658, occupation 2512," the same
statistical office and, on the evidence available, the same Manedslønn-family total-earnings concept
`_extract_no()` already uses for this country's own native figure (item #21's own body, above). The
gradient's own `meta.premium_basis` field records `"median"` — which central STATISTIC the premium is
measured against, mean or median — a different axis entirely from which PAY BASIS (regular vs total)
that median was itself computed from; nothing in `experience_gradient.json` states the latter
explicitly for Norway, which is itself part of what this finding names. If the premium really is
calibrated on a total-earnings series, applying it to a regular-pay base assumes the same
proportional bonus-inclusive premium holds for a bonus-excluded figure — not demonstrated, and not
obviously true (bonus components do not necessarily scale with tenure the same way base pay does).

**Not fixed by package 24.** This package's own governing constraint was presentation only, no
method changes — and resolving F13 means picking one of: (a) shifting `usd_total_earnings` instead,
matching the gradient's own probable basis, at the cost of losing the regular-pay figure
`computeEstimateUsdYear()` otherwise prefers; (b) locating or deriving a regular-pay-basis premium
series for Norway specifically; (c) disclosing the mismatch itself as its own chain step, the same
way the function already discloses its regular-to-total FALLBACK (`computeEstimateUsdYear()`'s own
`basis_fallback` chain entry, for the Spain-shaped case) — each is a real method decision, not a
wording choice.

**Decide:** which of the three paths above (or another) resolves the mismatch, and whether it is
Norway-specific or needs the same check run against every other personalising country's own
gradient-to-combo pairing before it is trusted generally.

**CLOSED, package 25 — answered from the source tables, not by judgement. The mismatch is real, it is
Norway-specific, and it is confined to the USD path.**

The item asked which of three paths to take. It turned out to be answerable at the source, because
the field that would settle it simply did not exist: `premium_basis` records mean-vs-median, the
central STATISTIC, and neither gradient entry stated which PAY BASIS its premium was measured on.
That absence was the defect. Both offices publish the answer in their own table metadata:

| | Cross used for the premium | Office's own label for the codes fetched | Basis |
| --- | --- | --- | --- |
| SE | SCB `LonYrkeAlder4AN`, `000007BN` | "Monthly salary" — the same concept as its own dispersion table's `000007CD`/`000007CE` ("Monthly salary"/"Median") | **regular_pay** (SCB's månadslön excludes bonus: *"en 13:e eller 14:e månadslön samt vinstdelning ... ingår inte i lönestatistiken"*) |
| NO | SSB `11658`, `GjMdTotal` + `MedianMndLonn` | "Average monthly earnings (NOK)" and "Median monthly earnings (NOK)" — SSB names the other concept separately, and `11418` labels it `AvtaltManedslonn` "Basic monthly salary" | **total_earnings** (Månedslønn; `pay_composition.json`: `irregular_bonus: true`, "bonus is IN by construction") |

Checked against what each code path actually shifts:

- **SE — matched, everywhere.** SCB publishes one concept, and both its cross and its dispersion are
  on it. `native` is `regular_pay` (55,500 SEK/month × 12 = `native_regular_pay`), and
  `usd_regular_pay` is the same basis. Nothing to fix. Sweden was checked because "is it
  Norway-specific?" cannot be answered by looking only at Norway.

  **CLOSED FULLY, package 26 — the asymmetry package 25 recorded is gone.** It left standing that
  Norway's classification was settled by SSB's own labels directly, while Sweden's leaned on
  `pay_composition.json`'s carried, `"verified_live_this_session": false` note. Settled the same way
  now, twice over:

  1. **SCB's own full ContentsCode metadata** (fetched live from each table's own metadata endpoint,
     not inferred from what this pipeline's harvester happens to request) shows `LonYrkeAlder4AN`
     offers **two** base pay CONCEPTS — `000007BL` "Basic salary" and `000007BN` "Monthly salary" —
     of which `AGE_CONTENTS` (`scripts/src_salary_se.py`) fetches only `000007BN`; `000007BL` is
     never queried at all. The dispersion table (`LoneSpridSektYrk4AN`) offers **12** ContentsCodes —
     mean, median, four percentiles, and six confidence-interval margins on those — and
     `DISPERSION_CONTENTS` fetches all 12, but every one of them is a different STATISTIC of the
     exact same **one** base concept, "Monthly salary"; no "Basic salary" alternative exists on this
     table at all, at any of its 12 codes. (Corrected here from this item's own first version, which
     said "not just the two codes this pipeline happens to query" for both tables — true of the age
     table's 2, false of the dispersion table's 12; caught by package 26's own Tier 2 adversarial
     review re-reading the archived metadata directly rather than trusting the count as written.) So
     "Monthly salary" is provably the concept the two tables share; queried live for occupation 2512,
     2025, it is also provably not the narrowest available ("Basic salary" **54,900** SEK/month vs
     "Monthly salary" **55,500**).
  2. **SCB's own current quality declaration**
     (*Kvalitetsdeklaration, Lönestrukturstatistik, hela ekonomin, 2025*, p.4) defines the difference
     directly: *"Månadslönen avser anställningens sammanlagda grundlön plus rörliga lönetillägg samt
     förmåner. Övertidsersättning ingår inte."* — base pay plus routine, role-based supplements and
     benefits; overtime excluded. The same document (p.11) separately confirms irregular/bonus-type
     pay — a 13th/14th month, profit-sharing, share options — is *"svåra att mäta och ingår inte i
     lönestatistiken"*, excluded from the wage statistics generally. Routine supplements in,
     irregular bonus out: **regular_pay**, confirming the carried note rather than merely repeating
     it — the "rörliga lönetillägg" the definition includes are ongoing, role-based supplements
     (shift/on-call differentials and the like), a different concept from the *irregular* bonus
     `pay_composition.json`'s `irregular_bonus` field tracks, so including them is consistent with
     this pipeline's own regular/total split, not a loophole in it.

  Both citations are now live sources, not carried notes, in `build_experience_gradient.py`'s own
  `pay_basis_source` field. **Confirms `regular_pay`; changes no behaviour** — SE's
  `usd_total_earnings` was already `ok: false`, so the preference list resolves to `usd_regular_pay`
  either way, exactly as before. A check that confirms is not a wasted check.
- **NO — native path already correct.** `native` is `total_earnings` (81,050 NOK/month × 12 =
  `native_total_earnings`), which is the basis its premium was measured on. `/work`'s estimate and
  position were never affected.
- **NO — USD path was the mismatch.** `computeEstimateUsdYear()` preferred `usd_regular_pay`, which
  for Norway is `AvtaltManedslonn` — a basic-salary figure multiplied by a premium built on total
  earnings. The two differ by ~3.5%, and the part that actually varies with the premium (how bonus
  scales with age) is unmeasured on either basis.

**Path taken: (a), shift the basis-matched figure — not (c), the disclosure.** `computeEstimateUsdYear()`
now prefers the combo whose basis equals the gradient's `pay_basis` when a gradient exists, and keeps
the old regular_pay-first preference for every country that has no premium to agree with. Option (c)
was available and cheap — the function already has a `basis_fallback` precedent — but disclosing a
mismatch is not fixing one when the matching figure is already published and committed. Option (b)
(sourcing a regular-pay premium for Norway) would have required a new SSB fetch and would then have
broken the native path, which is currently correct: it would need a premium PER basis, not a
different one.

**The published value this changes, stated rather than buried.** Norway's USD estimate at 8 years'
experience: **$79,917/year → $81,949/year** (+2.54%). Before: `usd_regular_pay` median 87,150.30 ×
**0.917**. After: `usd_total_earnings` median 89,366.57 × **0.917**. It feeds `PayVsCost` only; no
figure on `/work` moved. The source that settles it is the ContentsCode table above — SSB's own
labels.

The multiplier is 0.917, not 0.9169: `_computeShift()` rounds the curve's own premium to one decimal
(`Math.round(gRaw.pct * 10) / 10`, `profile.ts`), so SSB's −8.31% is applied as −8.3%. This item
first recorded $79,908 → $81,940 — the arithmetic done by hand against the unrounded premium instead
of read off the rendered card. Corrected against what the site actually displays, which is the whole
method package 25 exists to enforce.

**The class of defect is now impossible rather than fixed once.**
`build_experience_gradient.py` refuses to write a curve whose `pay_basis` is missing or not one of
`regular_pay`/`total_earnings`, or which cites no `pay_basis_source` (exit 1, demonstrated).
`scripts/tests/test_package25_gradient_basis.py` pins the pairing in CI, including a numeric check
that each personalising country's `native` block really is on the basis its premium claims — a future
curve added without a stated basis fails the build, and a curve whose basis stops matching fails the
suite.

NO's own `vintage_note` (a single quarter, `2026K1`, against an annual dispersion series) is
unchanged and still disclosed; this ruling does not touch it.

## 59. CLOSED, package 27 — Package 26's 30-figure citation-truth sample found 8 failures in 4 code locations, all below the arithmetic layer

Package 25 made every one of 646 figures cite *something* and asserted structure over every card. It
never traced a single citation back to its source. Package 26's Tier 2 drew a stratified 30-figure
sample from `.status/evidence/p25-inventory.json` (12 of the inventory's own 17 distinct source ids
— see "what this does not cover," below; both `<Figure>` and `<Derived>` cards; 22 of the 30 touch
DK/NO/FI/DE/ES/CA; 8 `<Derived>` chain-step cards; 7 from `CityProfile`) and traced each one's full
chain — page figure → data file/key → builder function → harvester → the source office's own table.
**8 of 30 failed (27%), from 4 distinct, code-level root causes, none of them an arithmetic error** —
every number checked was traceable and correct; what failed was what the number was *attributed to*.
Two of the eight (defect D, below) were not caught by the original trace — they were found by this
package's own adversarial review, which re-checked the two "PASS" verdicts that had no
`data/processed/*.json` file behind them, rather than accepting the sample's own first pass. Per this
package's own Tier-2 rule, a rate this far above 10% is a package of its own, not a fix to append to
this one — Tier 3/4 (Explore) were not started. Full trace evidence: `REPORT-P26.md`.

**A — `talent.com + PayScale`, the site's single most common citation, names sources by policy, not
by record.** `site/src/data/registry.ts:97-101`, `site/src/routes/CityProfile.tsx:96-101`, and
`site/src/routes/Compare.tsx:483` each hardcode `name: 'talent.com + PayScale'` for every city's
headline "Developer salary" figure — 222 of 646 figures (34%), the largest single citation bucket on
the site. Swept all 73 records in `data/cities.json` directly, not sampled: **69 of 73 (95%)** have
no talent.com/PayScale URL anywhere in `sources[]`, so `city.sources.find(s => s.includes('talent.com')
|| s.includes('payscale'))` returns `undefined` and the popover's "Open source ↗" link silently never
renders — confirmed live (Oslo, `hasLink: false` on the rendered `[role=dialog]`). **44 of 73 (60%)**
have a `salary_usd_year.note` that names neither source at all — Madrid's is triangulated from
"Glassdoor España + KeepCoding (citing Randstad/Jobted) + 10Code (citing LinkedIn Salary/InfoJobs)."
For Oslo, Copenhagen, and Helsinki, the note states directly that *"talent.com has no salary tool for
\[country\]"* — one of the two named sources is confirmed absent for that specific city, while the
card names it anyway. Stockholm is not the same case (corrected here after package 26's own
adversarial review checked the note directly rather than assuming the Nordic cities all read alike):
talent.com SE *did* return a figure for Stockholm (median SEK 1,050,000) — it was examined and
rejected as a likely outlier, identical to Gothenburg's and more than double PayScale's own read,
flagged with its sample size (128) and reasoned against general knowledge (it would put Stockholm
above London). The rejection itself is sound methodology, fully disclosed in the note. But the
*card* still says "talent.com + PayScale" as if talent.com contributed to the number shown, when its
own reading was explicitly thrown out — the same name/content mismatch as the "no tool" cities,
reached by a different route (a number solicited and rejected, not a tool that was never there).
Toronto is the one clean case sampled: the note genuinely cites both, and both fed the final number,
so the name is accurate — only the link is still dead. The displayed
vintage ("Aug 2026" on every one of these cards) is `cities.json`'s own top-level `as_of`, a
file-regeneration timestamp, not a per-source date — it can never trigger `<Figure>`'s own staleness
warning no matter how old the underlying manually-researched PayScale read is.

**B — `WagePanel.tsx`'s "published: X" line does not track the basis its own chain computes from.**
`site/src/components/explore/WagePanel.tsx:394-401` (Explore → Money's "open each row's own method"
detail list) passes `native={{ value: r.native.value... }}` unconditionally, but `WageCountry.native`
(`site/src/data/explore.ts:168-188`) is **one fixed figure per country** — this pipeline's own
default/native basis, with no per-basis variant — while `chain`/`result` come from `r.combos[key]`,
keyed by whichever basis the panel's own toggle currently has selected. The two only agree when the
selected toggle happens to match the country's own native default. Traced live: viewing this panel
under `regular_pay`, Norway's card reads "published: 77,420 NOK/month (2025)" — `native_nok_month`,
Norway's own *total_earnings* figure, per item #58 above — immediately followed by a chain computing
`75,500 × 12 = 906,000`, where 75,500 is `avtalt_median_nok_month`, the *regular_pay* figure. The
final result (906,000) is correct; the concept block correctly names both Norwegian concepts by name;
but the "published: 77,420" line sits between them citing a number neither the chain nor the result
uses. The docstring at `WagePanel.tsx:25-28` names DK, NO, FI, and DE as the four countries that
"publish BOTH bases natively... absent on neither" — all four are structurally exposed to this same
mismatch on whichever toggle isn't their own default; only Norway under `regular_pay` was traced in
full. **A same-session fix was attempted and reverted, not shipped.** Two versions were written and
checked against `data/processed/wage_distribution.json` directly rather than trusted on inspection —
both were wrong. The first (suppress `native` unless its raw value equals the combo's) fails for
every country, always: SE's own *matching* combo is `53,500 × 12 = 642,000`, not `53,500` — the
combo is always annualised, even when the basis is right, so raw equality never holds. The second
(scale by 12 first) works for FI (`native` month → combo year, always `× 12`) and DE (`native` is
already annualised at extraction, per item's own `annualised_note`; DE's *matching* combo carries
literally the same number) but breaks on DK, whose native figure is an hourly `STAND` concept that
both bases reach only via subtraction *and* an hour→week→year conversion — neither combo is ever a
clean scalar multiple of `native`, so the same check that correctly detects NO's mismatch would also
suppress DK's *correct* case, which was never re-rendered live to confirm either way. Given a
same-session fix could not be verified correct for all four countries' three genuinely different
chain shapes (plain native-swap, extraction-time-annualised, and subtraction-based), it was reverted
rather than shipped on the two cases that happened to check out — the same discipline item #58 used
Sweden's carried note to *not* upgrade an unverified read into a confident fix.

**RESOLVED, package 27, Tier 3.** Both reverted attempts tried to *re-derive* which basis `native`
represents from the combo *values* at render time — the wrong layer to ask the question at, since
`native` and each combo are already annualised, converted and (for Denmark) subtracted by the time
they reach `WagePanel.tsx`; nothing at that point still carries which basis the raw figure started
as. `build_wage_distribution.py` already has a function that answers exactly this, one layer down,
against each source's own raw `pay_composition.json` entry: `normalise.comparison_basis(source_id,
source_id)`. Verified live for every one of the 14 source_ids this pipeline resolves before trusting
it: `salary_no → total_earnings`, `salary_fi → regular_pay`, `salary_de → regular_pay` (matching
each extractor's own docstring, word for word); `salary_dk → None` (STAND is a third,
pre-subtraction concept, matching neither); `salary_ca`/`salary_qa`/`salary_ae → None` (unverified
composition, no combo ever shown regardless); every single-basis country returns exactly the one
basis `WagePanel.tsx`'s own pre-existing docstring already names for it. `resolve_country()` now
writes this onto `native.native_basis`; `WagePanel.tsx` shows the "published: X" line exactly when
`native_basis === basis`, an exact-key comparison, no chain-shape guessing. Verified live in all
three genuinely different shapes: Norway under `regular_pay` (native line now absent — the exact
defect, gone), Norway under `total_earnings` (native line now present and correct: "published:
77,420" beside a chain computing `77,420 × 12`), Denmark under either toggle (never shown, matching
that its own native figure equals neither combo), Finland under `regular_pay` (shown correctly, its
own native basis). Five new tests in `test_wage_distribution_extraction.py` pin this — including one
that calls `resolve_country()` itself rather than the helper in isolation — proved able to fail by
temporarily hard-coding the old always-`regular_pay` behaviour back in (9 of the 9 broke), then
restored.

**C — `Compare.tsx`'s generic fallback names "official sources" and links whichever URL sits first
in an unordered array, regardless of the metric.** `fallbackSource()` (`site/src/routes/Compare.tsx
:466-476`) is the citation for *any* `visa`/`people`/`life`/`jobs`/`net_pct` metric that has no
citation of its own: `{ name: '\${country.name} — official sources', url: country?.sources?.[0], ... }`.
`country.sources` is not ordered by relevance to any specific metric — it is whatever order that
country's own harvesters happened to append URLs in. Traced live: Norway's "~3 yrs, typical time from
arriving to being allowed to stay for good" card links `country.sources[0]`, which is
`eiglaw.com/norway-raises-salary-thresholds-for-skilled-workers...` — a private immigration-law
firm's blog post about *salary thresholds*, not an immigration-timeline claim, and not itself an
official government source, under a label that says "official sources."

**RESOLVED, package 27, Tier 2 — mostly.** Read all 15 countries' own `sources[]` by hand: 8
(Australia, the US, Great Britain, Ireland, the Netherlands, Denmark, Norway, Finland) carry a
genuine, identifiable government immigration-authority domain, just not first in the array —
`registry.ts`'s new `countryImmigrationSource()` finds it by exact host (never position) for
`pr_years`/`citizenship_years`/`tuition`/`post_study_months`. Verified live: Norway's own citation
now reads "Norway — official immigration authority" and links `udi.no`. The other 7 (Canada,
Germany, Italy, Spain, Sweden, UAE, Qatar) never had an official source captured at all — every
visa-related URL on their own record is a law firm, immigration consultancy or news write-up, not a
government one — confirmed by reading each one, not assumed. For those, the fix is honesty rather
than a link: "Compiled — no official source captured," not a guess dressed as one. `net_pct`,
`ict_share`, `healthcare`, `peace_rank` and `hdi` all gained their own fixed or field-shared citation
too (same pattern `happiness_rank`/`ict_specialists` already used correctly), removing five more
metrics from the fallback path entirely. What still reaches `fallbackSource()` — climate figures,
Tehran flight time, `english_work` — never had a per-figure research trail the way `salary_usd_year`
(#59A) or the visa figures turned out to have; the fallback itself no longer guesses a position, it
says plainly there is no single source on record, rather than manufacturing one to avoid saying so.

**D — real arithmetic renders through `<Figure>` (a bare citation) instead of `<Derived>` (this
codebase's own purpose-built, disclosed-chain component), on two figures the original 30-sample had
marked passing.** Found by package 26's own adversarial review re-checking the two "PASS" verdicts
that carried no `data/processed/*.json` behind them, rather than accepting the arithmetic-reproduces
standard applied everywhere else. `site/src/routes/CityProfile.tsx:216-222` (Oslo's "the path to
owning a home" panel): `<Figure source={{name: 'Numbeo', what: 'Crowd-reported purchase price per
square metre.', ...}}>{money(city.apt_price_outside_usd_m2 * HOME_M2)}</Figure>` — the card's own
`what` string admits Numbeo published a *per-square-metre* rate, but the number inside the citation
is that rate **× a fixed 90 m² assumption**, presented as if Numbeo published the total. `registry.ts`
`salary_net` ("Take-home pay," `site/src/data/registry.ts:119-140`): `netFor()` (`compute.ts:50-54`)
computes `city.salary_usd_year[band] * (city.net_pct / 100)` — the SAME defect-A "crowd"-confidence
gross figure, multiplied by an OECD-derived tax-survival rate — and renders the result at
`confidence: 'official'`, under "OECD Taxing Wages + national calculators," a source that publishes
the *rate*, not the dollar figure the card shows, and never discloses that roughly half its own input
is crowd-tier. `Derived.tsx`'s own doc comment states the rule this violates: *"a number this site
calculated FROM one or more \[sources\] — a wage converted currency, annualised, or had a component
subtracted... this is the only way a CALCULATED number is rendered."* Both of these are calculated
numbers rendered the other way. Scope not swept: `registry.ts` has two more computed metrics
(`savings_usd_year` via `savingsPerYear()`, `years_to_home`/`m2_per_year` via `yearsToHome()`/
`m2PerYear()`) that were not individually re-checked for the same pattern, and CityProfile.tsx's
inline `<Figure>` usages elsewhere were not swept beyond the one instance traced — named here as
likely-present, not counted.

**RESOLVED, package 27, Tier 4 — both, plus a third render site the original finding didn't name.**
Both figures now render through `<Derived>`, using a new shared `netPayChain()` (`compute.ts`) for
the tax calculation so the fix lives in one place, not two. Verified live: Oslo's home-price card now
reads *"$7,100/m² — Numbeo's own crowd-reported purchase price per square metre, outside the centre.
x 90 m² — this site's own reference home size, editable in Compare. = $639,000"*; the take-home-pay
figure (three render sites all shared one root cause and are all fixed together — CityProfile's own
"a month in \[city\]" card, `registry.ts`'s `salary_net` metric, and Compare's own salary row under
its "After tax" lens) now reads *"$70,000/year — this city's own market-wide developer salary (a
separately-cited figure)... x 73% — this country's own flat net-of-tax share... = $51,100"* on every
one of the three. `docs/DESIGN.md`'s own words settle which side of the line each case falls on:
`<Figure>`'s optional `steps` field is for "real arithmetic over ONE source's own real numbers,"
`<Derived>` for a number "converted, annualised, or had a component subtracted." Oslo's ×90 is a
pipeline-owned multiplier over one source's number — the same shape as Germany's own ×12
annualisation, already `<Derived>` elsewhere in this codebase; Berlin's net-pay combines TWO
differently-sourced, differently-confidence-tiered numbers — squarely `<Derived>` territory, not
`<Figure>`+`steps`.

**Swept the rest of the codebase's own `<Figure>` usages "by rule," not just by inspection** (10
files import `Figure`). Two already-correct precedents confirm the rule rather than complicate it:
`Position.tsx` and `CountryStripRow.tsx`'s own personalised-position cards use exactly the sanctioned
`<Figure>`+`steps` pattern DESIGN.md itself names as the example (an age-banded figure ranked against
that same country's own percentile table — one source, shown working) — correctly `<Figure>`, left
untouched. `WagePanel.tsx` and `DataMethods.tsx` were already clean. Two more instances found by the
same rule, lower severity, **not fixed this package**:
  - `CountryProfile.tsx:244-250`, "UN DESA ÷ World Bank" (`e.foreign_born.share_pct`) — genuinely
    combines two sources the same way Berlin's net-pay did, but pre-computed at BUILD time with its
    own `formula` string already disclosed via `what` — the reader can already see the working, just
    not through `<Derived>`'s own structured chain UI. Lower harm than Oslo/Berlin (no false
    attribution, no confidence-tier mixing), but the same rule catches it.
  - `Compare.tsx`'s own `COMPUTED_WHAT` map (`savings`, `total_monthly`, `years_to_home`,
    `m2_per_year`) already renders `name: 'Computed — formula on screen'` — honest about being
    calculated, unlike Oslo/Berlin's false company attributions, but still a `<Figure>` with a prose
    paragraph in `what`, not a `<Derived>` with an ordered chain. Four metrics, a genuine but lower-
    severity instance of the same underlying gap between what `<Figure>` can honestly hold (one
    source, "real arithmetic over ONE source's own real numbers") and what these actually are.
  Both are the same shape as the levels.fyi double-use finding (#60): correctly not silently
  patched under this tier's own time budget, and named here rather than left to a future inspection
  to rediscover from scratch. Carried forward as their own item, **#61**, now that this one is closed.

**What this does not mean.** No published number was found wrong — every value traced (222+ figures
checked structurally in the full sweep for defect A, plus the 30-sample's own arithmetic, all
reproduced exactly from source files) is correct. The failure is entirely in what a correct number is
*attributed to*: a source named that wasn't used, a "published" figure that isn't the one the chain
beside it computes from, a link chosen by array position instead of topic, real arithmetic wrapped in
a citation component that discloses none of it. **30 of 646 is a sample, not a proof** — defect A's
true scope (222/646, 34%) was confirmed by a full sweep specifically because it was cheap to sweep
mechanically; defects B, C, and D were each confirmed on one or two live instances and are named as
structurally present elsewhere (four countries for B, every fallback-sourced metric for C, at least
two more `registry.ts` computed metrics and CityProfile's own other inline `<Figure>` uses for D), not
separately re-counted.

**What this does not cover.** The sample touched 12 of the 17 distinct source ids the inventory's own
figures actually carry (`.status/evidence/p26/figures_categorized.json`) — ONS (GB), CBS (NL), ATO
(AU), and CSO (IE) were not in the original 30 (caught by this package's own adversarial review). A
follow-up pass traced one figure from each directly against its own `data/processed/salary_*.json`
file rather than leave the gap standing: AU (`data/processed/salary_au.json`, occupation `261313`
"Computing professional - software engineer," ANZSCO 6-digit) — A$132,758/year matches exactly; GB
(`salary_uk.json`, `2134` "Programmers and software development professionals," SOC 2020 4-digit) —
£55,587/year matches exactly; IE (`salary_ie.json`, `soc1:2` "Professional," 1-digit — the coarser
depth this pipeline's own crosswalk logic discloses for Ireland) — €33/hour matches (32.99 rounds to
33); NL (`salary_nl.json`, `0811` "Software- en applicatieontwikkelaars," BRC 2014) — €35/hour matches
(34.5 rounds to 35). All four passed, extending coverage to 16 of 17. `postings_seed_summary` (the
17th, DataMethods-only) was not additionally traced.

**Options for whichever package takes this on**, roughly in ascending order of how much new work each
requires:
  - **(a) Narrow the claim instead of the gap.** For A, stop naming specific providers in the citation
    and say what's actually true of every city uniformly — e.g. "crowd-sourced salary estimate" with
    the specific providers moved into `what`, read from the note itself rather than asserted in `name`.
    Cheapest, ships without new data, but a reader loses the (currently false) impression of knowing
    which site was consulted.
  - **(b) Record what was actually used, per city, as data — not prose.** For A, add a structured
    `salary_usd_year.sources_used: string[]` field (populated once, by hand, from each city's own
    `note`) that `registry.ts`/`CityProfile.tsx`/`Compare.tsx` render directly instead of a hardcoded
    literal, and add the missing per-city URLs to `sources[]` so the link stops being silently absent.
    For C, the analogous fix is tagging `country.sources` entries by topic at harvest time so
    `fallbackSource()` can filter by the metric's own `theme` instead of taking index 0. Correct, but
    real data-entry/harvesting work across up to 73 cities and however many countries carry
    fallback-sourced metrics — not a same-session patch.
  - **(c) For B specifically, give `WageCountry` a `native_basis: Basis` field at build time**
    (`build_wage_distribution.py` already knows which basis each `obs` came from when it builds
    `native` — it is simply never recorded), then `WagePanel.tsx` can show `native` exactly when
    `native_basis === basis`, correctly, for all four dual-basis countries without per-chain-shape
    guessing at render time. The right fix, and now a small one given this item's own trace of all
    three chain shapes — but still needs `build_wage_distribution.py` changed and its own tests
    extended before it touches the site, which is why it was named here rather than attempted live.
  - **(d) For D, route every computed metric through `<Derived>`, not `<Figure>`.** `registry.ts`'s
    generic rendering loop only ever calls `<Figure>` — a computed `MetricDef` (one whose `value()`
    does arithmetic over more than one field, not a straight passthrough) has nowhere else to go even
    if the author wanted `<Derived>`. Needs the generic loop taught to accept an optional `chain`
    alongside `source`, or these few computed metrics pulled out of the generic loop the way
    `CountryProfile.tsx`'s own dual-basis cards already are — either way, a rendering-architecture
    change, not a one-line fix, and CityProfile.tsx's own inline `<Figure>` uses (the 90 m² multiply
    among them) would still need finding and moving by hand regardless of which path `registry.ts`
    takes.

**CLOSED, package 27.** All four defects resolved — see each defect's own "RESOLVED, package 27" note
above for what changed and how it was verified. A stratified re-sample (package 26's own 30, re-traced
live rather than assumed fixed, plus 30 new figures drawn from the same strata and weighted toward
what this package actually changed — every `citySalarySource()` branch, every metric Tier 2 gave a
real citation for the first time, both directions of the `native_basis` check) found 0 failures across
60 figures — REPORT-P27.md, Tier 6. Two related, lower-severity instances found by defect D's own
rule were named, not fixed, and are carried forward as their own item rather than left implicit here
— see #61. NEEDS-DECISION #60 (the levels.fyi double-use finding, package 27 Tier 1) is a separate,
still-open item — a citation-accuracy fix does not resolve a question about what a figure's own
architecture claims.

## 60. For 21 of 73 cities, "market-wide" and "top-employer" pay are not two independent bands — both trace to the same levels.fyi metro page

Package 27, Tier 1 traced every city's `salary_usd_year` (the "Developer salary" headline figure,
previously mislabelled "talent.com + PayScale" for all 73 — see #59) back to what its own `note`
field says was actually used, city by city, not guessed. `src_levels_fyi.py`'s own docstring states
the site's architecture plainly: *"The dataset already carries MARKET-WIDE salary bands (talent.com,
PayScale, BLS). This adds the other half... The site shows BOTH and never averages them."* The
premise is that `salary_usd_year` (market-wide) and `salary_levels_fyi` (top-employer) are
independent bands from independent source families, and the UI's own comparability caveat
(`registry.ts`, `salary_levels_fyi`'s `what`) tells the reader exactly that: *"Correlated with the
market band (r = 0.90) but NOT interchangeable... Never blended with it."*

**For 21 of 73 cities, that premise does not hold.** Their own `note` says `salary_usd_year`'s bands
were read from the SAME levels.fyi metro page that separately backs `salary_levels_fyi` — usually a
different percentile slice of the identical underlying self-reported sample, not an independent
market-wide survey:

- **13 US metros** (`new_york, boston, chicago, atlanta, raleigh, dallas, houston, san_antonio,
  miami, nashville, washington_dc, philadelphia, sf_bay_area`): the note is explicit —
  *"new_grad=Entry Level band p50 (n=1559); mid approximated from all-levels aggregate median
  (n=8877)... senior=Senior band p50 (n=3422)"* (New York's own numbers) — three different
  percentile/aggregate reads of ONE levels.fyi metro page, with a BLS OEWS figure named only as a
  cross-check, never used as the headline.
- **6 German cities + Amsterdam** (`berlin, munich, hamburg, frankfurt, stuttgart, amsterdam`): same
  pattern — *"levels.fyi self-reported total comp... entry-level range... midpoint used; overall
  average total comp... used as 'mid' proxy"* — again one page, sliced differently per band.
- **Dubai and Abu Dhabi**: explicitly named *"HARMONIZED 2026-08: entry $33k / senior $100k from
  levels.fyi Dubai... Mid $57k = geometric mean interpolation within that same source family"* — and
  the note itself discloses that the market-wide sources (talent.com, PayScale) were checked and
  found to sit far lower, in a *"deeply two-tier"* market, and were deliberately NOT used.

**What this is not.** No number is wrong — `salary_usd_year`'s own bands for these 21 cities still
reproduce exactly from levels.fyi's own published percentiles, same as before. Nothing here changes
what's displayed.

**What this is.** The reader is told two things that are only half true for these 21 cities: (1) the
citation now correctly says "levels.fyi" (package 27 fixed the false "talent.com + PayScale" label —
see #59), so a reader who opens the card sees the real source; but (2) the SEPARATE "top-employer
pay" card beside it still carries the comparability caveat claiming independence and
non-interchangeability from a band that, for these specific cities, is not actually independent —
it is the same dataset read a second way. Dubai/Abu Dhabi are the sharpest case: the "market-wide"
figure there is explicitly, by the note's own words, NOT the market-wide reading at all, but a
big-employer-skewed levels.fyi figure standing in for it because the true market-wide sources were
judged unreliable.

**Options:**
  - **(a) Leave both bands as-is, correct the caveat for these 21 cities specifically.** Cheapest:
    add a per-city flag (`salary_usd_year.primary_source === 'levelsfyi_linked'`) that swaps the
    "top-employer pay" card's `what` text to disclose the shared source, for these 21 cities only.
    Ships without new data or new research.
  - **(b) Re-derive a genuinely independent market-wide band for these 21 cities**, the way the other
    52 already have one (BLS, Indeed, PayScale, talent.com, SEEK, or a real multi-source
    triangulation). Real research work, city by city, not a same-session fix — the reason
    `salary_usd_year` leaned on levels.fyi for these 21 in the first place was that the independent
    sources were unavailable, thin, or (Dubai/Abu Dhabi) judged unrepresentative, so re-deriving one
    means finding a source that wasn't there before, not just re-reading an existing one.
  - **(c) Drop the "top-employer pay" card specifically for these 21 cities**, since it adds no
    independent information over the market band already shown — the two-tier comparison this site
    is built around genuinely does not exist for them. Loses a feature other cities keep, but is the
    most honest single-card fix if (b) is judged not worth the research cost.

Not resolved here — Tier 1's own instruction is to escalate a finding that changes what a figure
means, not to pick an answer under a citation-fix package's own time pressure.

**Correction (adversarial review, package 27 tier 2b): the 21-city membership above was wrong in
both directions.** Verified against `data/cities.json` directly (not against the note text alone —
the note can claim a levels.fyi read happened without the top-employer card actually carrying a
value):

- **`dallas`, `houston`, `nashville`, `philadelphia` do not belong on this list.** Their
  `salary_usd_year.note` does say a levels.fyi metro page was read, but their `salary_levels_fyi`
  block is `median_total_comp_usd: null` with `unavailable_reason: "No
  /t/software-engineer/locations/<slug> route resolved..."` — the harvester that built the
  *headline* figure found a page; the separate harvester behind the top-employer card did not, for
  these four specifically. `CityProfile.tsx`'s own guard (`lf?.median_total_comp_usd != null ? ... :
  lf?.unavailable_reason ? <span className="nodata">No levels.fyi figure for {city}...` renders the
  no-data fallback instead of the caveat-bearing card, so there is no second band on the page for
  these four and therefore nothing to conflict with #59's fix — the premise this entire finding
  depends on does not hold for them. That leaves 9 of the 13 US metros actually affected, not 13.
- **`melbourne`, `brisbane`, `perth` (AU), and `eindhoven` (NL) belong on this list and were
  missing.** All four carry a live, non-null `salary_levels_fyi.median_total_comp_usd`, so the
  caveat-bearing card does render. Their pattern is a partial version of the same defect, not the
  full version the bullets above describe: `new_grad` and `senior` bands trace to the same
  levels.fyi page as the top-employer card (e.g. Melbourne's note — *"levels.fyi Melbourne:
  AU$83,255 median entry-level, AU$148,803 senior... Senior uses the AU-wide levels.fyi band"*),
  while `mid` is independently sourced (Melbourne/Brisbane/Perth: talent.com AU + PayScale
  city-specific, averaged; Eindhoven: Glassdoor + TechPays). So the comparability caveat is false
  specifically when a reader is looking at the new_grad or senior band for these four, true for mid.
- `abu_dhabi` above should read `abu-dhabi` (hyphenated) — the id it actually has in
  `data/cities.json`; the description of its figures checks out.

Net count is unchanged at 21, but four of the original members should not have been on the list and
four real members were missing — a reader auditing this entry city-by-city against the live site
would have found four false positives and, separately, missed four real ones. Whichever of (a)/(b)/(c)
above is chosen should be scoped against this corrected set, enumerated in full so it can be counted
rather than trusted:

- **9 US metros** — new_york, boston, chicago, atlanta, raleigh, san_antonio, miami, washington_dc,
  sf_bay_area
- **5 German cities** — berlin, munich, hamburg, frankfurt, stuttgart
- **amsterdam**, **dubai**, **abu-dhabi**
- **4 partial-overlap** (new_grad and senior only) — melbourne, brisbane, perth, eindhoven

9 + 5 + 3 + 4 = **21**.

*Corrected by package 28's adversarial review, which is the second error in this one paragraph and
the more embarrassing kind:* it read "6 German cities + Amsterdam" from the original bullet above
and carried the 6 forward as if all six were German. There are **five** German cities in
`core.json` (the sixth entry in that bullet is Amsterdam, which is Dutch), so the list as first
written summed to 22 against a headline of 21. The count 21 was right; the enumeration a reader
would scope the options against was not — in an entry whose own correction claimed to have been
"verified against `data/cities.json` directly".

## 61. Two figures found by defect D's own rule, lower severity, not fixed — split out from #59 on its own closure

Package 27, Tier 4 fixed the two computed-figures-in-a-bare-citation cases NEEDS-DECISION #59 named
(Oslo's home price, take-home pay) and swept the rest of the codebase's `<Figure>` usages against
`docs/DESIGN.md`'s own rule for the line between `<Figure>` and `<Derived>`. Two more instances turned
up by the same rule. Lower severity than the two fixed figures (neither misattributes to a real
company, neither mixes a 'crowd'-confidence input with an 'official' badge) — named here rather than
fixed, and kept as their own item now that #59 itself is closed:

- **`CountryProfile.tsx:244-250`, "UN DESA ÷ World Bank"** (`e.foreign_born.share_pct`) — genuinely
  combines two sources the same way the take-home-pay figure did, but it is pre-computed at *build*
  time with its own `formula` string already disclosed via the card's `what` text. The reader can
  already see the working; it just isn't in `<Derived>`'s own structured chain.
  `data/processed/un_migrant_stock.json` ÷ `data/processed/world_bank.json`, resolved at
  `build_site_data.py` time, not at render time.
- **`Compare.tsx`'s own `COMPUTED_WHAT` map** (`savings`, `total_monthly`, `years_to_home`,
  `m2_per_year`) — already renders an honestly-named `"Computed — formula on screen"` card, so it
  does not misattribute to a real company the way the two fixed figures did, but it is still a
  `<Figure>` holding a prose paragraph in `what` rather than a `<Derived>` with an ordered chain.
  Four metrics, one shared map, in `site/src/routes/Compare.tsx`.

**Correction (adversarial review, package 27 tier 2b): a third instance, same file, same rule,
missed by this sweep.** `Compare.tsx`'s own `salarySource()` (line ~494) branches on `lens`: the
`'gross'` branch is a real citation, the `'net'` branch is the take-home-pay figure Tier 4 already
converted to `<Derived>` (`isNetPay` at line 574 covers `salary_net` and `salary_gross`+`'net'`
specifically). The third, `lens === 'after'`, branch does not — it falls through to
`return { name: 'Computed — formula on screen', what: 'Net salary − 12 × (rent + living costs), all
three from the sources on this page.' }`, the exact same formula as `COMPUTED_WHAT.savings` just
above it, rendered through the same bare-`<Figure>` path (`isNetPay` is false for it, so it never
reaches the `<Derived>` branch at line 576). Live and reachable: the salary row under the "after
costs" lens in the comparison table. Same severity class as the `COMPUTED_WHAT` bullet above — an
honestly-labeled computed card, not a misattribution — so it belongs with that bullet's fix, not
with the two Tier-4-fixed figures: whichever of (a)/(b)/(c) below is chosen should cover this branch
of `salarySource()` too, not just the four `COMPUTED_WHAT` entries.

**Options**, cheapest first:
  - **(a) Leave as-is.** Both are honest about being calculated (a disclosed formula string; a
    literal "Computed" label) — the harm is a UI/consistency gap, not a false claim. Zero-cost, but
    the site's own architecture (`<Figure>` = sourced, `<Derived>` = calculated) stays inconsistent
    with these four-plus metrics.
  - **(b) Convert `COMPUTED_WHAT`'s four metrics to `<Derived>`, reusing this package's own pattern**
    (a small chain-builder per metric, mirroring `netPayChain()` in `compute.ts`) — bounded, four
    known call sites, no new data or research needed, similar shape to Tier 4's own fix.
  - **(c) Give the generic `MetricDef` rendering loop itself a `chain` field**, so any future computed
    metric (not just these four) renders correctly by construction instead of by whoever adds it
    remembering to special-case it in `Compare.tsx` the way Tier 4 did for `salary_net`. The
    architectural fix NEEDS-DECISION #59 itself named and did not attempt — larger, touches every
    consumer of `MetricDef` (`Compare.tsx`, the scatter builder, the weights tool), and is why it
    was named rather than attempted under this package's own time budget.

Not resolved here.

## 62. The UAE now plots at $49,000 on "the price of the door", but one of its three routes has no salary floor at all

Package 27's adversarial review found `Visas.tsx`'s `Thresholds` chart reading
`skilled_routes[0]` positionally: the UAE's route 0 (Standard employment visa) carries
`salary_threshold_usd: null`, so the chart listed the country under *"United Arab Emirates —
points or sponsorship, no salary floor"* while routes 1 and 2 (Golden Visa $98,000, Green Visa
$49,000) both carry published floors. Package 28, Tier 0 confirmed the fix live and confirmed it
changes exactly one country's rendered figure: the UAE, now a dot at $49,000 labelled "Green Visa
(skilled worker)". For every other country, `route[0]` already was the lowest-threshold route, so
nothing else moved.

**The fix removed a false claim and left a different incompleteness behind.** The UAE's route 0 is
not a missing number — its own `threshold_note` reads *"No published skill salary threshold; MOHRE
skill-level classification applies"*, and its summary says *"no points or degree-based salary floor
for most roles"*. So the UAE genuinely has a floor-free way in. The chart is called "The price of
the door" and shows one number per country; for the UAE, the honest answer is two facts at once —
a floor-free employer-sponsored route, and two self-sponsored routes gated at $49k and $98k. The
new rendering states the second and hides the first, where the old one did the reverse.

The inconsistency this creates is visible on the same chart: **Qatar** stays in the no-floor chip
list on exactly the shape the UAE just left it for — one employer-sponsored route, `null`
threshold, `threshold_note: "No published salary threshold for skilled roles"`. Both countries
have a floor-free employer route; the UAE now reads as $49,000 and Qatar as no floor, purely
because the UAE *additionally* publishes two salary-gated routes. Offering more ways in makes the
UAE look more expensive than the country offering fewer.

Neither rendering is wrong about the data — the chart's one-number-per-country shape cannot hold
"has both". Which of the two facts leads is a presentation call, so it is not being made here.

**Options:**
  - **(a) Keep the fix as shipped, and mark the dot.** The UAE keeps its $49,000 position (a real,
    published floor, and the reason the fix was made), with its own annotation on the ruler — the
    file already has a `NOTE` map keyed by country code for exactly this (`Visas.tsx:15`, currently
    carrying `AE: 'golden visa only — no citizenship path'`). Cheapest, and the ruler stays a
    ruler: every plotted country is one that really does gate on salary.
  - **(b) Let a country appear as both.** Plot the UAE's floor *and* keep it in the no-floor list,
    with the chip reworded for this case ("also has a route with no salary floor"). Most complete,
    but it breaks the chart's current invariant that `has` and `nulls` partition the country set,
    and the chip list stops being a list of floor-free countries.

Not resolved here — package 28's Tier 2 rule is that a presentation change nobody has ruled on is
escalated, not implemented.

*Package 29 note, still open.* Tier 1 established a fact that narrows this item: the UAE's city
pages render **no journey at all** (`pr_years_typical` is null, so `Journey` returns early), so the
$49,000 appears on the Explore ruler and nowhere else. There is no second surface contradicting it,
and the question here is unchanged — whether one number per country can represent a country that has
both a floor-free route and two gated ones.

## 63. Doha's salary citation lost a working PayScale link to stop it misattributing one band

Package 27's adversarial review reclassified Doha's `salary_usd_year.primary_source` from
`payscale_linked` to `compiled`. Package 28, Tier 0 confirmed why, from Doha's own note: PayScale
Qatar backs `new_grad` (QAR 95,585) and `mid` (QAR 110,000), but `senior` is **Glassdoor's**
(Rheinmetall Barzan Advanced Technologies median, QAR 216,000), with levels.fyi named only as a
range cross-check. `citySalarySource()` takes a city, not a band, so the single label "PayScale"
covered the senior figure too — naming a company that did not produce that number, which is the
defect NEEDS-DECISION #59 existed to remove. The reclassification is correct on those grounds and
changed no published value.

**What it cost:** Doha has a real `payscale.com` URL on file
(`.../research/QA/Job=Software_Engineer/Salary`), and `compiled` renders "Compiled estimate" with
no link at all, so the reader lost a click-through to a source that genuinely backs two of the
three bands.

**Why this is worth a ruling rather than a quiet fix:** the codebase already has the other answer
for the identical shape. `indeed_seek_linked` exists because for Adelaide *"Indeed backs new_grad
and senior, SEEK backs mid — both real, only one URL field to offer, and Indeed covers two of the
three bands"* (`registry.ts`); that case keeps a compound label naming both companies **and** the
Indeed link. Doha is the same shape with different companies, and got the opposite treatment.

**Options:**
  - **(a) Leave Doha as `compiled`.** No misattribution, no new enum value, and the note under the
    card names all three providers and which band each backs. The reader loses the link.
  - **(b) Give Doha the Adelaide treatment** — a `payscale_glassdoor_linked` branch labelled
    "PayScale + Glassdoor", carrying the PayScale URL. Names both real sources, restores the link,
    and matches how the codebase already resolves this exact split. Costs one `primary_source`
    value, one branch in `citySalarySource()`, and one data edit; note that `registry.ts` is
    already allowlisted in `test_citation_derivation.py`'s compound-company-literal check, so the
    label is permitted there and nowhere else.

    *Package 28's adversarial review adds a caveat to (b):* the compound-company-literal check
    would not have caught that label anywhere, allowlist or not. It requires one of the two tokens
    to be domain-shaped (`\w+\.[a-z]{2,4}`), and **neither "PayScale" nor "Glassdoor" contains a
    dot** — so `'PayScale + Glassdoor'` and `'Glassdoor + PayScale'` both pass it. The guard
    catches the shape that actually shipped ("talent.com + PayScale"), not every compound label.
    If (b) is chosen, the label is safe to add but is not being policed; if the guard is meant to
    police it, the domain requirement has to be relaxed to something like "two capitalised names
    joined by + or and", which is a much noisier rule and was deliberately not written that way.

Not resolved here — which of the two the site should standardise on is the owner's call, and
whichever wins should be applied to both cities, not one.

## 64. CLOSED, package 29 — Two generic tools take 22–41% of every Explore theme's height, and no theme feeds either of them

Package 28, Tier 1 measured the claim `Explore.tsx:88-94` makes in its own comment — *"Both tools
live on every theme"* — rather than defending or assuming it. Measured on the served production
build, seven themes, desktop 1440x900:

| | `Ask your own question` (ScatterBuilder) | `Weigh things yourself` (WeightsTool) |
| --- | --- | --- |
| renders on | all 7 themes | all 7 themes |
| height | 708 px, identical on all 7 | 115 px, identical on all 7 |
| network cost on mount | one ~3 KB chunk (`ExploreCharts-*.js`) | none of its own |

Together they occupy **823 px on every theme**, against page heights of 2,012–3,668 px:

| theme | page height with tools | tools' share |
| --- | --- | --- |
| visa | 2,012 | **41%** |
| people | 2,195 | 37% |
| jobs | 2,365 | 35% |
| life | 2,330 | 35% |
| climate | 2,339 | 35% |
| housing | 2,964 | 28% |
| money | 3,668 | 22% |

**Neither tool is theme-aware in any way.** `ScatterBuilder()` and `WeightsTool()` take no props
(`ExploreCharts.tsx:69`, `WeightsTool.tsx`); both read `useData()` (core.json) and the metric
registry, never the theme's own data. Measured consequence: on **all seven themes** the builder
opens preset to the same two axes — *"Apartment price per m²"* against *"Years to own a 90 m²
flat"* — with the same 29 metric options in each dropdown. A visitor who opens **Climate** and
scrolls is offered a housing question, pre-selected, under a heading inviting them to ask their
own.

So the structural claim holds in the direction the work order suspected: they are two generic
panels appended to seven specific pages. What the measurement does **not** support is calling them
expensive — 823 px of layout and ~3 KB of JavaScript, both deferred behind `DeferUntilVisible`
until scrolled to, is cheap. The cost is attention and coherence, not bytes.

This is not being changed here. Dropping a panel and restructuring a page are both explicitly the
owner's calls under package 28's own Tier 2 rule, and the owner has not seen this page since four
packages of change landed around it.

**Options:**
  - **(a) Leave both on every theme, but let the theme feed the builder.** Keep the panels where
    they are and default `ScatterBuilder`'s two axes to metrics belonging to the current theme
    (`AXIS_METRICS.filter(m => m.theme === key)` is already computed at `ExploreCharts.tsx:288` for
    the dropdown groups, so the data to do it is in hand). Smallest change; the tool stops opening
    on a housing question under Climate. Does not reduce the 823 px.
  - **(b) Give both tools their own home and link to it.** Move them off the seven themes to one
    destination reached from the theme bar, so each theme ends at its own last chart. Recovers
    22–41% of every theme's height and removes the repetition; costs a navigation step for the
    visitor who wants them, and is a structural change to a page the owner has not yet reviewed.

Not resolved here.

**RULED by the owner, implemented in package 29's Tier 2.** The ruling: keep both tools on every
theme at full height, and make each default to that theme's own question. Option (a), and
explicitly not (b) — they are not to be moved, shortened or collapsed, and the 823px measurement is
accepted rather than treated as a problem to solve.

Done: every theme now opens the scatter builder on a pair drawn from its own metrics (climate on
summer high against winter low, visa on residency against citizenship, and so on), and the weights
tool starts from whichever of its four existing lenses matches the theme, while staying off by
default. A question the visitor builds themselves overrides the default and survives every theme
switch — verified, and the reason that needed care is that it already worked, so a naive default
would have broken it. Both tools verified still present at full height on all seven.

## 65. CI's browser suites failed once on a 30-second Chrome start budget, and passed on re-run with no change

Package 28, Tier 0 pushed seven package-27 commits. CI went red on the first run
(`33831786400`, 6m1s) at `scripts/tests/test_ui_regressions.mjs:65`:

```
Error: headless Chrome did not expose a debugging port within 30s
  binary: google-chrome-stable
```

No Chrome stderr was captured, which `cdp.mjs` prints when there is any — so the process spawned,
did not exit, and simply had not opened its debugging port inside the budget. Re-running the same
job on the identical commit passed (5m8s, no code change), which is what rules out the commit as
the cause.

**This budget has already been raised once for this exact symptom.** `cdp.mjs`'s own comment
records it: *"30s, not 15. A cold Chrome start on a loaded CI runner is slow, and the old budget
(100 x 150ms) sat close enough to the real start time that a busy runner failed the whole suite
before a single check ran."* Today is the same failure one budget later, on a runner image new
enough that the log also warns Node 20 actions are being forced onto Node 24.

A red build that a bare re-run turns green is worse than a slow one: it trains whoever reads it to
re-run rather than to look. But the right remedy depends on what the true start time is, and this
run did not measure it — it only proved 30s was not enough once.

**Options:**
  - **(a) Raise the budget and record the reason.** One line in `cdp.mjs` (the poll is
    `200 x 150ms`); cheapest, keeps the failure mode visible if Chrome is genuinely broken, but is
    the second guess at a number nobody has measured.
  - **(b) Retry the launch once before failing.** `launch()` throws today; wrapping the spawn in a
    single retry with a fresh profile directory distinguishes "slow to start" from "cannot start"
    and reports which. More code in the one file every browser suite depends on.

Not resolved here — and deliberately not fixed on a hunch, because the failure is intermittent and
neither option can be verified from a single green re-run.

## 66. CLOSED, package 29 — A second positional `skilled_routes[0]` survives on `/city/*`, invisible to the guard built for it

Package 27's Tier 7 fixed `Visas.tsx`'s `skilled_routes[0]` — the read that made the Explore chart
claim the UAE has no salary floor. Package 28's adversarial review found the same shape still in
place one file away:

```
site/src/routes/CityProfile.tsx:261     route={country.visa.skilled_routes[0]?.name}
```

It renders in `Journey` as *"You land on a work visa — typically the {route}."* — array position
standing in for a recorded "typical route" relationship, on a user-facing page, exactly the shape
NEEDS-DECISION #59's defect C describes.

**Nothing is wrong on screen today.** Checked all 13 countries where the line renders (AE and QA
short-circuit earlier on `pr == null`): route 0 is a defensible "typical" route for every one of
them as the data currently stands. This is a latent defect, not a live one — the same data edit
that produced the UAE bug produces one here.

**Two things make it worth recording rather than leaving.** First, Tier 5's guard cannot see it:
`test_citation_derivation.py`'s positional check matches the identifier `sources` only, so
`skilled_routes[0]` is outside its reach — the guard built after this defect class would not catch
this instance of it. Second, it now disagrees with Explore: for the UAE, `/explore/visa` names the
**Green Visa** (the cheapest priced route, after Tier 7) while `/city/dubai` would name the
**Standard employment visa** (route 0). Two pages, two "typical" routes, same country — though as
noted the UAE line does not currently render.

**Options:**
  - **(a) Record which route is typical, and read that.** A `typical: true` flag (or an explicit
    ordering) on `visa.skilled_routes`, consumed by both call sites. Removes position-as-meaning
    everywhere it appears and makes the two pages agree by construction. Costs a data edit for all
    15 countries and a decision about what "typical" means where routes serve different people.
  - **(b) Widen the Tier 5 guard and leave the code.** Extend the positional check beyond the
    identifier `sources` to any `<identifier>[0]` indexing a route/source array in `site/src`, so
    this and anything like it fails the suite until someone justifies it. Cheaper, catches the
    class rather than the instance, but will flag legitimate first-element reads and needs an
    allowlist — the thing Tier 7 just removed one of.

Not resolved here — package 28's Tier 2 rule covers what its own Explore measurement justified, and
this is neither Explore nor measured by it.

**FIXED in package 29, Tier 1.** The naming rule is derived from the `type` field the data already
carries, ranked by how well each kind matches the sentence being rendered ("you land on a work
visa"): employer_offer, then points, then talent, then job_seeker — the last being the permit you
hold when you have no job, which that sentence must never name. Both route rules now sit as named
functions in `site/src/data/visaRoutes.ts`.

Nothing on screen changed: for all fourteen countries whose journey renders, route 0 was already the
right arrival route. Two corrections to this item's own premises, though. It renders for **fourteen**
countries, not thirteen — Qatar's `pr_years_typical` is 20, so Doha's journey renders in full, and
only the UAE short-circuits. And because the UAE's journey never renders, the cross-page
disagreement this item worried about cannot be seen by anyone.

The guard was widened too, which was the more important half: it missed this because it matched the
identifier `sources`, hardcoded, while being named for the whole class. Its watchlist is now derived
from `types.ts`, so a new array field is covered the moment it is declared. Proved by restoring the
`[0]` and watching it fail at `CityProfile.tsx:262`.

## 67. CLOSED, package 30 - "What we take from it" shows one pipeline step out of up to seven, for 51 of the 54 rows the table renders

Package 29's Tier 1 swept every first-element read in `site/src` for the #66 defect class. This one
is **not** that defect — `provenance.entries[].transforms` is an ordered sequence of pipeline steps,
so `transforms[0]` genuinely means "the first step" rather than "an arbitrary one". It is recorded
because the sweep surfaced it and the number is larger than expected.

`DataMethods.tsx` renders the Data & methods table, whose second column is headed **"What we take
from it"**. It renders `e.transforms[0]` — the first step only:

```
provenance entries                       57
entries with more than one transform     52
```

So for 51 of the 54 rendered rows the column describes the first of up to seven steps and silently
omits the rest.

*Corrected by package 29's own adversarial review:* the first version of this item quoted 57 and 52,
which are the FILE's figures. `DataMethods.tsx` renders only rows whose `status` is ok or partial, so
the surface being described is 54 rows, of which 51 carry more than one transform; and the longest
chains (`oecd_indicators`, `wipo_gii`) run to seven steps, not six. Examples: `ef_epi` shows 1 of 6, `bis_property_prices` / `bls_oews` /
`eurostat_ict_specialists` show 1 of 5 each. `bls_oews` reads "Constructed OEWS series IDs for 30
metros..." and drops four further steps including whatever came after.

**Why this is escalated rather than fixed.** Nothing rendered is false — the first step really is a
thing the pipeline does, and each row also carries its own `notes`. What is at stake is how complete
a table cell claims to be under that heading, and how much of a six-step pipeline belongs in it.
That is a presentation decision on a page nobody asked this package to change, and package 28's rule
(fix what is objectively wrong, escalate what is a judgement) puts it here.

**Options:**
  - **(a) Leave it, and change the heading.** The column promises more than one step delivers.
    "First step" or "How we start from it" costs nothing and stops the cell over-claiming. Smallest
    honest change; the full chain stays where it already lives, in `provenance.json`.
  - **(b) Render the whole chain.** All transforms as an ordered list in the cell, or the first with
    an honest "+4 more" disclosure the site already has vocabulary for. Complete, and matches what
    the heading currently implies — at the cost of a much taller table on a page that is already
    dense.

**CLOSED, package 30 tier 3 - option (b), the disclosure, chosen with a measurement rather than a
preference.** Both routes were measured against the live page:

```
baseline, one step shown, heading over-claiming     table  9,023px
heading reworded only  (option a)                   table  9,023px  (+0)
+N more, collapsed     (option b, shipped)          table  9,084px  (+61px, +0.7%)
+N more, all 51 expanded at once                    table 15,593px  (+73%)
```

Option (b) costs 61 pixels across the whole table - 0.7% - because the summary sits inline on rows
that already wrap to several lines; median row height is unchanged at 152px. The objection to (b)
was that it makes a dense table denser, and at 0.7% on arrival it does not. The 73% figure is what
a reader opts into one row at a time, not what the page costs on load. So the heading stays honest
and the cell stops under-delivering: first step, a count of what follows, and the rest one click
away.

Evidence: `.status/screenshots/p30-gate4-transforms-{collapsed,expanded}.png` - 51 disclosures
present on the rendered page, a sample summary reading "+4 more steps", and an expanded row listing
the remainder as an ordered list. No published value changed.

## 68. CLOSED on arrival, package 29 — core.json costs 89.5 KB on every theme, including the two that read nothing else

Package 28's Tier 1 measured that `core.json` is fetched on all seven Explore themes, and that visa
and climate pull no other data at all — so on those two the entire data cost is a bundle largely
about other themes. It was recorded as a measurement, not a defect. Package 29 was asked to rule on
it, in either direction, and the answer is **leave it**.

**What it costs.** 397.8 KB raw, **89.5 KB gzipped**, one fetch, not referenced from `index.html` —
the app requests it (`store.ts`: *"core.json is the only blocking fetch"*).

**Where it hurts: nowhere the site is measured, and nowhere it is not.** The existing gates are
desktop Lighthouse, which package 28 passed 14/14 at >=90/>=95 with TBT 0 ms. That is exactly the
condition under which a payload argument would be invisible, so this ruling looked where the gates
do not — a throttled **mobile** run, simulated network and mobile CPU:

    climate   performance 97   FCP 1.3 s   LCP 2.6 s   TBT 0 ms     SI 1.3 s
    home      performance 96   FCP 1.3 s   LCP 2.1 s   TBT 180 ms   SI 1.4 s

Climate is the theme that reads core.json and nothing else — the strongest case anyone could make
for splitting — and it scores 97 on throttled mobile. There is no measurable cost to remove.

**And splitting could not help while #64's ruling stands.** The owner has just ruled that both
generic tools stay on every theme. The scatter builder offers **29 axis metrics spanning all seven
themes** on every theme, and the weights tool scores **every city** against the metric registry. So
the two panels that are required to be present on the climate page are precisely the ones that need
countries, cities and metrics in full. Splitting `core.json` by theme would either break them or
force a second fetch of the rest the moment a visitor scrolls — trading one 89.5 KB request for two,
to serve a page that already scores 97 on a throttled phone.

**The discipline, stated because it is the point.** A measurement is a reason to look, not an
obligation to change. Packages 24 through 28 fixed things because they were wrong, not because they
had been measured. This number is real, it is recorded, and it is not hurting anyone; re-opening it
should require a concrete cost, not the number's continued existence.

## 69. The figure-inventory suite captures two different pages from the same build, and every assertion passes on both

Package 30 ran `test_figure_inventory.mjs` about fifteen times while working through its gates, on
one unchanged build and one unchanged `core.json`. It reports one of exactly two results:

```
Captured 646 figures, 54 no-data marks, 668 marks     ~11 runs
Captured 646 figures, 61 no-data marks, 764 marks      ~4 runs
```

The figure count is identical every time. What moves is 7 extra "no data" marks and 96 extra marks
in total. Both states pass C1-C6 and R8 with zero findings.

**Why it went unnoticed for five packages.** Every assertion in the suite is shaped "N found, expect
0". A run that renders 7 more no-data marks than another is therefore indistinguishable from one
that does not, as long as none of those marks trips an assertion. The suite counts what it saw and
asserts about defects; it has never asserted that what it saw is the same page twice.

**What was ruled out.** Not the build: the state flips between runs against one build. Not the
preview server holding a stale `dist/`: it flips across two consecutive runs on a server started
seconds earlier. Not the code or the data: neither changed between any two of the runs above.

**Leading hypothesis, not a conclusion.** The 61/764 state clusters immediately after a rebuild or
a server restart -- 3 of its 4 appearances -- which fits a cold file cache making some fetch slower
than the suite's fixed post-navigation wait, so a panel is captured still showing "no data". That
is a guess consistent with the timing; nobody has yet identified WHICH panel, and the cheap way to
find out is to print the 7 marks' own routes and labels rather than only their count.

**Why this matters more than a flaky count.** If a real defect lands in whatever renders those 7
marks, this suite finds it on roughly one run in four. That is worse than not covering the area,
because the passing runs read as coverage. It is the same shape as #65 (a CI browser suite that
failed once and passed unchanged on re-run) and should probably be decided alongside it.

**Options:**
  - **(a) Make the count itself an assertion.** Pin figures/marks/no-data to expected values, so a
    drift fails loudly instead of being averaged away. Cheapest, and turns the flake into a red
    build that someone must then explain -- which is the point.
  - **(b) Find the 7 first.** Log each no-data mark's route and label, run until the 61 state
    appears, and diff. Identifies the panel before deciding anything; costs one run in four.
  - **(c) Wait for quiescence rather than a fixed delay.** Fixes the likely cause if the hypothesis
    holds, and does nothing if it does not.

Not resolved here. Found by package 30 while running its own gates. Nothing in that package caused
it, and the reason is not an alibi but the observation itself: the two states alternate across
runs of ONE build, from ONE commit, over ONE unchanged `core.json`. A source change cannot
produce a difference that appears and disappears without one. This has not been re-run against an
earlier commit, and does not need to be for that conclusion; it would still be worth doing to
learn how long it has been true.
