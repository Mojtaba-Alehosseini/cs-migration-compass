# Decisions triage

`NEEDS-DECISION.md` reached 25 items across packages 4–11 with none formally answered. This is
that file sorted into three groups so it can be read in one sitting. Every item appears exactly
once. Full reasoning for anything below stays in `NEEDS-DECISION.md` at the same number — this
page is the index, not a replacement.

---

## Genuinely needs you (8 items)

1. **#1 — Stack Overflow: only 2024 is wired, 2017–2023 exist as separate CSVs.** Worth a new
   pipeline package to add the time axis? Real engineering cost, would turn the panel into the
   site's best pay time series.
2. **#5 — Four datasets can't be drawn as series (IMF WEO, World Bank GEP, BLS single-year,
   Numbeo city rents).** Narrowed: IMF WEO is a wholesale 403 block, not fixable by retrying.
   World Bank GEP and Numbeo city rents are genuinely unclear — could be worth a fresh look, could
   be genuinely absent upstream. Worth the investigation time?
3. **#6 — Compare has three surfaces (metric picker, budget editor, climate overlay) the locked
   mockup never drew.** Keep them as-is, fold them into the design properly, or drop them? A
   product/design call, not a data one.
4. **#10 — Should the mockup's illustrative metric set become the registry's actual default
   (`headline: true`)?** A content decision — which metrics the site leads with.
5. **#12 — Canada's NOC 2021 splits "software developer" into two codes (21231, 21232) with
   different pay (Toronto: CAD 56.49/hr vs 48.08/hr).** Sum them, show both side by side (current
   shipped state), or pick one? Changes where Canada lands in every cross-country comparison —
   still open since package 7.
6. **#21 — Norway and Finland use opposite conventions for which basis counts as "native"** (Norway:
   total; Finland: bonus-excluded). Both individually defensible, disagree with each other. Pick
   one convention site-wide, or accept the inconsistency with a per-row basis label?
7. **#22 — A flat net-take-home percentage is applied across a salary range that can now span
   2.5x** (package 11's own profile-driven estimates make this more consequential than it was).
   Worth building progressive tax modelling for fifteen countries, or is a disclosure note enough?
8. **#25 — `DESTATIS_TOKEN` may have been exposed in this session's own tool-call transcript**
   (GENESIS echoes the submitted credential back in its login response; the first live call logged
   it before the bug was caught and fixed). Narrow blast radius — a read-only public-stats
   credential, not a payment method — but rotating it is your call, not this pipeline's.

---

## Decided this package, no action needed from you

- **#2** — No picker for Indeed's other 22 metros; the design brief's own one-control rule already
  forbids it.
- **#3** — The mockup's "eight metros" data stands over its own stale "four metros" prose.
- **#4** — Yes, the OECD real/nominal caveat belongs on the level and indexed lenses too, not just
  yearly-change. Decided, not yet built — small, safe, left for a future pass since it touches
  chart code this package didn't otherwise verify.
- **#7** — Accept "the whole comparison travels in the address" as the copy-link wording;
  per-comparison OG images are infeasible on a static host, not just deferred.
- **#8** — Accept the shipped sticky-header fallback (label column pins left on narrow screens); a
  JS-synced duplicate header row is speculative complexity for an edge case.
- **#9** — Keep omitting default `band`/`lens` values from shared URLs — every package since has
  independently converged on the same convention.
- **#11** — Keep `compute.ts`'s own real wording ("living costs") over the mockup's hyphenated
  guess ("living-costs").
- **#19 — Germany's GENESIS access.** Resolved for real this package: the registered token was
  tried for the first time (four prior sessions only ever checked the environment, never the
  runner script that actually sets it) and cleared the wall instantly. Real KB10-434 wages now
  ship. Nothing left to decide. (#14 and #15 are the two earlier, now-superseded diagnostic
  attempts — see the Superseded section below.)
- **#23** — `_verify_mdrsnit_reconciliation()`'s reproducibility claim was already precise, not
  wrong; a documentation note, not an open question.
- **#24** — The single career-start-age constant (22) stands until package 12's CV path exists to
  supply a real education level; not a live fork today.
- **#17's one residual** (flat-DKK vs flat-percentage for Denmark's PENS/UREGEL) — not actually an
  owner call; only DST's own methodology can answer it. Flagged as a research task, not a decision.

---

## Superseded or obsolete — closed by later work, not by this triage

- **#13** — BLS OEWS's percentile extension: resolved in package 8, tier 0. Already says so in its
  own heading.
- **#14** — Germany, package 8's diagnosis (API unreachable): superseded by #15's better diagnosis,
  then by #19's actual fix (package 11).
- **#15** — Germany, package 9's diagnosis (account-permission wall, no token tested): superseded
  by #19's actual fix (package 11) — see the "Decided" section above.
- **#16** — The plan document assigns `stabilityOf()`'s salary-override extension to a package the
  actual work order text didn't mention it in: superseded by package 10 tier 4, which built exactly
  that, exactly where this item predicted it would land.
- **#17** — Denmark's FORINKL/MDRSNIT gap: superseded by package 10 tier 0.2's full reconciliation
  (STAND, not FORINKL, is what MDRSNIT is built from — reproduced to <0.005% across 35 data
  points). One narrow residual noted in the "Decided" section above, not an owner call.
- **#18** — Norway's bonus: superseded by package 10 tier 0.3 (AvtaltManedslonn is a real published
  field, not a subtraction).
- **#20** — Whether the position can be experience-linked and still `<Figure>`-sourced: superseded
  twice — first by package 10 tier 7 (Spain's own version of this was unsound, personalisation
  removed entirely), then by this package (revived correctly for Sweden and Norway specifically,
  where the population genuinely matches).

---

25 items in, 25 items accounted for exactly once. The owner-needed group is 8, at the tier's own
stated limit — every item above it was tried against the evidence first.
