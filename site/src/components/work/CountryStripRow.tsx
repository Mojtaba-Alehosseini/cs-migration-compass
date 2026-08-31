/* Package 24, Tier 1b — one row, replacing the old page's coverage-matrix
 * pip row AND its own separate "Where you'd stand" / "What's actually
 * open" section below it. Four marks carry what fourteen paragraphs used
 * to say in prose (see design-mockup-work.html's own header for the full
 * mark budget and the reasoning behind it):
 *
 *   1. Track pattern (solid / dashed / none) — how much of a distribution
 *      the office publishes. Independent of...
 *   2. Marker fill (filled / hollow) — personalised to the profile, or
 *      sitting at the published median because this country cannot
 *      personalise.
 *   3. The estimate's dashed underline — <Derived>'s own established
 *      "tap for the method" convention, unchanged.
 *   4. A small text basis chip, NEEDS-DECISION #21's own ruling — shown
 *      only where a source could have published either pay basis and
 *      picked one silently.
 *
 * PRESENTATION ONLY. computePosition()/computeEstimate() are called
 * exactly as CountryRow already called them — same refusals, same
 * values, same chains. A country whose estimate.ok is false today (an
 * unrankable central-tendency-only/mean-only distribution: fewer than two
 * of p10/p25/median/p75/p90) shows no figure here either, matching the
 * page today exactly — surfacing that country's own raw median/mean
 * instead would be a NEW value appearing where none does today, which
 * Gate 14 exists to catch. The track still renders (an abbreviated dashed
 * segment): that is a new PRESENTATION of the distribution TYPE, an
 * already-published field, not a new published number.
 */

import { useEffect, useState } from 'react'
import { Flag } from '../Flag'
import { Figure } from '../Figure'
import { Derived } from '../Derived'
import { computePosition, computeEstimate, knownPercentilePoints,
  type Profile, type ExperienceGradient } from '../../data/profile'
import { fmtNative, ordinal, PERIOD_LABEL } from '../../routes/Position'
import type { WageCountry } from '../../data/explore'

/** Tier 4's own motion rule: the strip draws in once, staggered, and never
 *  replays; a later profile change morphs the marker from where it already
 *  is instead. `drawn` flips true-once on mount (never resets — nothing in
 *  this component's own deps ever sets it back to false) and gates which
 *  transition applies: BEFORE it flips, opacity is what's animating, on a
 *  stagger keyed to this row's own index (`--dur-draw-stagger`, the same
 *  token the chart engine's own draw-in already uses); AFTER, only `left`
 *  (the marker's own position) transitions, on `--dur-morph`, with no
 *  delay and no replay of the entrance. `prefers-reduced-motion` needs no
 *  special-casing here — the duration tokens themselves zero under it. */
function useDrawnIn(): boolean {
  const [drawn, setDrawn] = useState(false)
  useEffect(() => {
    const raf = requestAnimationFrame(() => setDrawn(true))
    return () => cancelAnimationFrame(raf)
  }, [])
  return drawn
}

/** NEEDS-DECISION #21's own ruling (Tier 2): the four sources whose native
 *  figure could have been published on either pay basis and picked one
 *  silently — sourced from the item's own established prose (package
 *  10/11 findings), not re-derived from raw combo values, since Denmark's
 *  own STAND concept is a third, most-inclusive basis (employer pension +
 *  irregular pay) that a numeric comparison against regular_pay/
 *  total_earnings risks mislabelling. */
const BASIS_LABEL: Record<string, string> = {
  NO: 'incl. bonus', FI: 'excl. bonus', DE: 'excl. bonus', DK: 'incl. pension',
}

/** The row list reserves the height it will occupy, standing in with the
 *  SAME row structure rather than a fixed pixel box.
 *
 *  `ChartSkeleton height={320}` was what this panel used first — inherited
 *  from the page it replaced, and wrong twice over. It under-reserved by
 *  210px at 1440 wide (the loaded list measures 530px), and `.wrow`
 *  collapses from one line into a three-area stack under 600px, so no
 *  single number can be right at both layouts — least of all under the
 *  mobile emulation Lighthouse actually scores. Measured: 0.178 CLS, the
 *  whole of a 14-point performance regression, with the `<details>`
 *  sections below named as the shifted element. Standing in with real rows
 *  makes the reservation follow the same CSS the real rows do, at any
 *  width, with no number to keep in sync.
 *
 *  `spine.length` rows, not the loaded list's own count: how many rows a
 *  country contributes is a fact only `wages` carries (Canada publishes two
 *  NOC codes, so the loaded list runs one row longer than the spine).
 *  One row is the honest residual — reserving more would be guessing, and
 *  rendering real country rows against data that has not arrived would be
 *  claiming a distribution this site does not yet have. */
export function RowListSkeleton({ count }: { count: number }) {
  return (
    <div aria-busy="true">
      <span className="visually-hidden">Loading each country&rsquo;s published pay distribution…</span>
      {Array.from({ length: count }, (_, i) => (
        // aria-hidden: these carry no country and no figure — the one line
        // above is the whole accessible content of a loading list.
        <div className="wrow" key={i} aria-hidden="true" style={{ opacity: 0.4 }}>
          <div className="wrow-id"><b>&nbsp;</b></div>
          <div className="wrow-strip"><div className="wrow-track-wrap" /></div>
          <div className="wrow-est">&nbsp;</div>
          <div className="wrow-opn">&nbsp;</div>
        </div>
      ))}
    </div>
  )
}

export function CountryStripRow({ row, cc, name, secondCode, profile, gradient, openings,
  openingsSharedWithCode, absentReason, highlighted, index }: {
  row: WageCountry | undefined
  cc: string
  name: string
  /** Canada's second NOC code shares this row's flag/name but is its own
   *  wage row and its own section id — shown as a small suffix, same as
   *  the old page's own `key !== cc` convention. */
  secondCode?: string
  profile: Profile
  gradient: ExperienceGradient
  openings: { software: number; named: number } | undefined
  /** Set only on Canada's second NOC row: the FIRST row's own national
   *  code, so the tap card can say the count is shared rather than
   *  double-counted — the old page's own on-screen note, relocated rather
   *  than dropped now that the row has no room for permanent prose. */
  openingsSharedWithCode?: string
  highlighted: boolean
  /** The source's own stated reason this country has no wage row at all
   *  (wages.absent) — Italy: "ISTAT publishes no occupation-level (CP2011)
   *  earnings flow at all". The old page printed this inline; this row has
   *  no room for a permanent second line, so it is the text alternative
   *  (title + screen-reader text) on the em-dash mark instead — relocated,
   *  not dropped (Gate 6). */
  absentReason?: string
  /** This row's own position in the list — the stagger delay is keyed to
   *  it, nothing else. */
  index: number
}) {
  const drawn = useDrawnIn()
  if (!row) {
    const reason = absentReason ?? `The site holds no published wage distribution for ${name} at this occupation depth`
    return (
      <div className="wrow" data-cc={cc} data-key={cc} style={{ ['--rowc' as string]: 'var(--ink-3)' }}>
        <div className="wrow-id">
          <span className="wrow-flag"><Flag cc={cc} size={14} /></span>
          <b>{cc}</b><span className="wrow-name">{name}</span>
        </div>
        <div className="wrow-strip" title={reason}>
          <span className="visually-hidden">{reason}</span>
          <span className="nodata" aria-hidden="true" style={{ fontSize: 'var(--text-xs)' }}>— no series published</span>
        </div>
        <div className="wrow-est"><span className="nodata">no table</span></div>
        <div className="wrow-opn">—</div>
      </div>
    )
  }

  const position = computePosition(profile, row, gradient)
  const estimate = computeEstimate(profile, row, gradient)
  const points = knownPercentilePoints(row.native.value)
  const hasTrack = points.length >= 2
  const filled = position.ok && position.personalised

  let markerLeft = 50, iqrLo: number | null = null, iqrHi: number | null = null
  if (hasTrack && estimate.ok) {
    const sorted = [...points].sort((a, b) => a.value - b.value)
    const lo = sorted[0]!.value, hi = sorted[sorted.length - 1]!.value
    const pos = (v: number) => (hi === lo ? 50 : ((v - lo) / (hi - lo)) * 100)
    markerLeft = pos(estimate.value)
    const p25 = points.find((p) => p.pct === 25)
    const p75 = points.find((p) => p.pct === 75)
    if (p25) iqrLo = pos(p25.value)
    if (p75) iqrHi = pos(p75.value)
  }

  const solidTrack = row.native.distribution === 'full' || row.native.distribution === 'quartile-only'
  const distText = row.native.distribution === 'full' ? 'publishes the full distribution (p10-p90)'
    : row.native.distribution === 'quartile-only' ? 'publishes quartiles only (p25-p75), no tails'
    : `publishes only a ${row.native.distribution.replace(/-/g, ' ')}`
  const srLabel = !hasTrack
    ? `${name}: ${distText}, no distribution to rank inside`
    : `${name}: ${distText}. ${filled ? `Personalised — ranks at the ${ordinal(position.ok ? position.pct : 50)} percentile`
      : 'Not personalised — marker sits at the published median'}`

  const basisLabel = BASIS_LABEL[cc]

  // The `transition` property itself must stay the SAME string across the
  // drawn flip, not swap which properties it covers — a CSS transition is
  // resolved from the style in effect AFTER a change, so a style object
  // that changes `opacity` and REMOVES `opacity` from `transition` in the
  // same React commit never animates that change at all; it jumps. Caught
  // by tracing computed opacity frame-by-frame (0 then straight to 1, no
  // interpolation), not by reading the code — the earlier "transition
  // removed... inert, not wrong" reasoning here was itself wrong. Kept
  // stable instead: opacity's OWN transition (staggered by index) covers
  // the one-time reveal and then sits inert once opacity settles at 1,
  // same as `left`'s own transition sits inert until a profile change
  // first moves the marker.
  const staggerDelay = `calc(var(--dur-draw-stagger) * ${index})`
  const trackEntranceStyle: React.CSSProperties = {
    opacity: drawn ? 1 : 0,
    transition: `opacity var(--dur-draw) var(--ease-out) ${staggerDelay}`,
  }
  const markerEntranceStyle: React.CSSProperties = {
    opacity: drawn ? 1 : 0,
    transition: `opacity var(--dur-draw) var(--ease-out) ${staggerDelay}, left var(--dur-morph) var(--ease-out)`,
  }

  return (
    <div className="wrow" data-cc={cc} data-key={row.country}
      style={{ ['--rowc' as string]: `var(--c-${cc})`, background: highlighted ? 'var(--surface-sunk)' : undefined }}>
      <div className="wrow-id">
        <span className="wrow-flag"><Flag cc={cc} size={14} /></span>
        <b>{cc}{secondCode ? ` · ${secondCode}` : ''}</b><span className="wrow-name">{name}</span>
      </div>
      <div className="wrow-strip" title={srLabel}>
        <span className="visually-hidden">{srLabel}</span>
        <div className="wrow-track-wrap" aria-hidden="true">
          {hasTrack ? (
            <>
              <span className={`wrow-track ${solidTrack ? 'solid' : 'dashed'}`} style={trackEntranceStyle} />
              {iqrLo != null && iqrHi != null && (
                <span className="wrow-track iqr"
                  style={{ ...trackEntranceStyle, left: `${iqrLo}%`, width: `${iqrHi - iqrLo}%` }} />
              )}
            </>
          ) : (
            <span className="wrow-track dashed" style={{ ...trackEntranceStyle, left: '32%', right: '32%' }} />
          )}
          <span className={`wrow-marker ${filled ? '' : 'hollow'}`}
            style={{ ...markerEntranceStyle, left: `${markerLeft}%` }} />
        </div>
        {/* The position's own tappable trigger — CountryRow always had one
          * (a <Figure>, separate from the estimate's own <Derived>), and an
          * early version of this row dropped it: the percentile was plain
          * text, so a reader could see P62 but never how it was ranked —
          * position's own chain (the rank interpolation) is DIFFERENT
          * content from estimate's own chain (the currency shift), and
          * losing it was a real regression, not a simplification. Restored
          * here rather than left dropped. */}
        {hasTrack && position.ok && (
          // The positioning (absolute, left:%, the entrance transition) has
          // to live on THIS wrapper, not on <Figure>'s own root — Figure
          // sets its own inline `position: relative`, which would win over
          // a CSS class's `position: absolute` (inline styles always beat
          // an external stylesheet rule) and silently break the placement.
          <span style={{ position: 'absolute', left: `${markerLeft}%`, top: -14,
            transform: 'translateX(-50%)', ...markerEntranceStyle }}>
            <Figure
              source={position.personalised ? {
                name: position.sourceLabel, asOf: String(position.year), confidence: 'official',
                what: `Personalised to ${profile.yearsProfessional} years of professional experience — `
                  + 'ranked against this country\'s own percentile table, not stated directly.',
                steps: position.chain.map((s) => s.detail),
              } : {
                name: position.sourceLabel, asOf: String(position.year), confidence: 'official',
                what: position.reason,
              }}
            >
              <span style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)',
                fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
                {ordinal(position.pct)}
              </span>
            </Figure>
          </span>
        )}
      </div>
      <div className="wrow-est">
        {estimate.ok ? (
          <>
            <Derived chain={estimate.chain} result={{ value: estimate.value, currency: estimate.currency }}>
              {fmtNative(estimate.value, estimate.currency)}{PERIOD_LABEL[row.native.period]}
            </Derived>
            {basisLabel && <span className="wrow-basis">{basisLabel}</span>}
          </>
        ) : (
          <span className="nodata" title={estimate.reason} style={{ fontSize: 'var(--text-2xs)' }}>{estimate.reason}</span>
        )}
      </div>
      <div className="wrow-opn">
        {openings ? (
          <Figure source={{
            name: `${name} software openings`,
            what: `${openings.software.toLocaleString()} of the harvest's own advertisements here classify as software.`
              + (openingsSharedWithCode
                ? ` Shared with ${openingsSharedWithCode}, above — the same advertisements, classified by title, `
                  + 'never by national occupation code, so both codes show the same count rather than double-counting it.'
                : ''),
            sample: `${openings.named.toLocaleString()} of ${openings.software.toLocaleString()} name a figure — the `
              + 'employer\'s own range, never this site\'s estimate. Not ranked; the full list is under Every opening.',
          }}>
            {openings.software.toLocaleString()}
          </Figure>
        ) : <span className="nodata">—</span>}
      </div>
    </div>
  )
}
