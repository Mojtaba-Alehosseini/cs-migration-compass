# Design

Tokens, themes and motion. The rule that makes all of it hold together: **no
component hardcodes a colour, font, radius or duration.** Everything routes
through `site/src/styles/tokens.css`.

---

## The direction

*A statistical annex printed on warm paper.*

The visualisation is the hero; titles stay small and quiet. Editorial serif
carries display text and big numbers, humanist sans carries the interface, and
the flag-dot — every city wearing its country's flag — is the signature motif
that makes a field of 73 dots readable without a legend.

Two files are the binding references and the source of this language:
`design-mockup-v2.html` (the dot field) and `design-mockup-pages.html` (city
profile, Explore theme, Data & methods).

---

## Tokens

`site/src/styles/tokens.css` is organised in four layers:

1. **Primitives** — type stack, type scale, spacing, radii, motion durations and
   easings. These do not change between themes.
2. **Semantic tokens** — what components actually consume: `--surface`,
   `--ink-1/2/3`, `--line`, `--accent`, `--warn`, `--note`, `--hatch`.
3. **Themes** — four, each with light and dark, selected by `data-theme` and
   `data-mode` on `<html>`.
4. **Data palette** — one colour per country, plus the six selection colours and
   the three confidence tiers.

### Type

```
--font-display  Iowan Old Style → Palatino → Georgia → serif
--font-ui       Segoe UI → system-ui → -apple-system → sans
--font-mono     Cascadia Mono → SF Mono → ui-monospace
```

No webfont. A visitor arriving from a Reddit link should not wait on a font
download to see numbers, and Georgia/Iowan have genuinely good numerals — which
matters on a site that is mostly numbers. Figures use
`font-variant-numeric: tabular-nums` so columns align.

The type scale floors at **12px** (`--text-2xs`). The design review forbade
captions below that, so the token simply does not exist.

### Themes

| Theme | Character |
| --- | --- |
| `compass` *(default)* | Warm cream paper, deep green, terracotta. Editorial serif + dashboard cards. |
| `editorial` | White, ink, thin rules. FT-adjacent. |
| `terminal` | Deep surfaces, glowing accent, mono display face. |
| `warm` | Cream, serif interface, terracotta. |

Selected in the header, persisted in `localStorage`, and applied before first
paint by a tiny inline script in `index.html` so there is no flash of the wrong
palette.

### Contrast

Palette A (Ledger) was locked at the design checkpoint. Every text-on-surface
pairing meets WCAG AA in both modes:

| Token | On paper | Ratio |
| --- | --- | --- |
| `--ink-1` | `#191813` on `#F6F3EC` | 15.8:1 |
| `--ink-2` | `#55524A` | 7.4:1 |
| `--ink-3` | `#74705F` | 4.6:1 — the quietest text allowed |
| `--accent` | `#0C6B54` | 5.9:1 |
| `--warn` | `#B5502F` | 4.9:1 |
| `--note` | `#7C5608` | 5.2:1 |

One deliberate change from the mockups: the amber was darkened from `#96690D`
to `#7C5608`. The original was 4.1:1 and failed AA for body text.

### Chart colour

Each country keeps its colour everywhere on the site (`--c-DE`, `--c-CA`, …), so
a line or dot is identifiable without reading a legend. Hues were chosen for
distinguishability under the common colour-vision deficiencies rather than for
flag accuracy — flag accuracy is carried by the flag-dots themselves, which is
where it belongs. Colour is never the only channel: every series is also
labelled.

---

## Motion

Rich where it clarifies, absent where it would obstruct.

| Surface | What moves | Why |
| --- | --- | --- |
| Home | Figures count up; the preset city pair rotates every 6 s until the visitor interacts | The motion *is* the data. It stops permanently on any interaction. |
| Compare | Cards spring on add/remove (Motion `layout` + `AnimatePresence`); bars ease to new widths on lens change | Shows that the number recomputed rather than swapping |
| Charts | Bars and lines transition width/length on data change | Continuity between states |
| Routes | View Transitions API, 160/260 ms | Orientation between pages |
| Controls | Hover lift, `scale(.97)` on press | Tactility |

**Discipline**

- No decorative particle fields, no manifesto text staggering in.
- Scroll effects only on Home; never inside dense data views.
- Data interactions respond immediately — animation is never on the input path.
- Durations live in tokens: `--dur-instant 90ms` → `--dur-swarm 750ms`.

**Reduced motion** is structural, not remembered. The
`prefers-reduced-motion` block zeroes the duration *tokens*, so every component
that animates through them inherits the fallback automatically; a component
cannot opt out by accident. Motion's own animations are covered by
`<MotionConfig reducedMotion="user">`, and `CountUp` renders its final value
immediately.

---

## Components that carry the honesty rules

Three components exist so the data principles hold by construction rather than
by discipline:

- **`<Figure>`** — the only way a sourced number is rendered. It is tappable and
  opens a card with source name, what the figure measures, sample size where
  known, date, and a link. This is why no caption on the site reads
  `○ crowd · talent.com · 2026-08`.
- **`format.ts`** — `null` never formats as a number. It formats as "no data".
  There is no code path that turns a missing value into `0`.
- **`<Flag>`** — real SVG, clipped to a circle, simplified to stay legible at
  13px: correct colours and geometry, fine detail dropped.

---

## Layout

- Container 1060px, matching the approved mockups.
- Panels: `--surface-raised`, 1px `--line`, `--radius-lg`, generous padding.
- Grids collapse at 820px; tables scroll inside their own container so the page
  body never scrolls horizontally.
- Focus is styled, never removed — a data site is navigated by keyboard as much
  as by pointer.
