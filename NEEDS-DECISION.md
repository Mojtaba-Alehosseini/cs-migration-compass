# Needs a decision

Raised while porting `design-mockup-compare.html` into the React app (package 4).
Nothing here blocked the build: each item was resolved the least-invasive way and
shipped, and each one is reversible. They are listed because the choice was not
mine to make.

---

## 1. Three surfaces the mockup does not draw, and does not ask to remove

Compare already carried a metric picker (`+ add a metric`), a budget editor and a
climate overlay. The mockup's screen 2 ends after the two footnotes, and the work
order says only that metric selection is out of scope for this package.

**Shipped:** all three kept, moved to sit *after* the mockup's own elements, so
the drawn sequence — toolbar → address strip → chips → table/chart → footnotes —
is exactly as designed and the undrawn extras follow it.

**Decide:** keep them where they are, fold them into the design properly, or drop
them. Deleting working features on the strength of a mockup's silence was not a
call I was willing to make.

---

## 2. The copy-link toast claims a preview image that does not exist

The mockup's toast reads *"Link copied — preview image attached ✓"*.
`scripts/generate_share_pages.py` only builds share shells for `/city/` and
`/country/`. A comparison link is `…/#/compare?places=…`; the hash never reaches
the server, so it gets the site's default Open Graph image — not a preview of
that comparison.

**Shipped:** `Link copied — the whole comparison travels in the address`. Same
shape, same job, no claim the build cannot honour.

**Decide:** either accept the new wording, or add per-comparison OG images and
restore the original line. The second is real work and out of this package.

---

## 3. Sticky header on phones is a CSS impossibility, not an omission

Binding note 4 asks for two things: the city header row pinned under the site
header, and — on phones — the metric-label column pinned left.

A horizontally scrolling container is also a vertical scrollport, so a
`position: sticky` row inside one pins to *the container* and never to the
viewport. Measured across every overflow combination Chrome accepts: only
`overflow-x: clip` preserves viewport-sticky, and `clip` makes wide tables
unreachable. The two requirements cannot both hold in CSS at a width where the
table must scroll sideways.

**Shipped:** the wrapper is marked when the table fits, and only then stops being
a scroll container — so the header row pins under the site header at every width
where nothing needs to scroll (all desktop and tablet cases). Where the table is
genuinely wider than the screen — phones, because the table keeps its 640px
minimum so columns stay readable — horizontal scrolling wins and the metric-label
column pins left instead, which is the half of the note that keeps a row
identifiable there.

**Decide:** accept, or spend a JS-synced duplicate header row on the phone case.

---

## 4. `band` and `lens` stay out of the address until they are touched

The mockup's strip always shows `…&band=mid&lens=gross`. The shipped URL contract
writes a key only once the user changes it, which is what `Compare.tsx` already
did and what the work order said to keep.

**Shipped:** existing contract kept. A default link reads
`…/#/compare?places=berlin,toronto` and grows as controls are used.

**Decide:** whether a shared link should spell out its defaults.

---

## 5. Metric rows are the registry's, not the mockup's

The mockup illustrates screen 2 with six rows of its own choosing
(salary, top-employer pay, rent, living costs, kept, years-to-home). Binding note
13 keeps metric selection out of this package, so the rows are still
`HEADLINE_KEYS` from `site/src/data/registry.ts` — developer salary, kept after
rent and living, years to permanent residency, rent, years to own a flat, people
born abroad — plus the residency row.

**Decide:** if the mockup's set was meant as the new default, that is a change to
`headline: true` in the registry, and it belongs with a metric-selection pass.

---

## 6. Missing-input wording comes from `compute.ts`, not the mockup

Binding note 10 says to use `missingInputs()` rather than re-derive the logic. It
returns `living costs` and `apartment price` where the mockup wrote
`living-costs` and `apartment-price`. The list is used as it comes, with one
exception: the purchase price is dropped from the "kept after rent and living"
and after-living-costs-salary reasons, because that formula never uses it and
naming it would be untrue.

**Decide:** nothing, unless the hyphenated forms were deliberate.
