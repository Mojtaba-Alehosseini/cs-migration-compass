/* Compare — two screens.
 *
 * With no `?places` it opens the browser: every city we hold, with its two
 * defining numbers. That is not an empty state to escape, it is the moment the
 * 73 cities are worth showing. There is no default pair; a comparison the user
 * did not choose is a comparison they cannot trust.
 *
 * With places chosen it is the comparison itself. State lives in the URL, so a
 * comparison is a shareable link, which is the whole distribution model for this
 * project — and the address strip says so out loud instead of hiding it in the
 * browser chrome. The selection is shared with the Home field, so dots picked
 * there arrive here and cities added here light up there.
 *
 * Nothing is ranked: columns stay in the order the user added them and rows
 * never sort themselves.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AnimatePresence, LayoutGroup, motion } from 'motion/react'
import { Flag, FlagRibbon } from '../components/Flag'
import { Figure } from '../components/Figure'
import { BudgetEditor } from '../components/BudgetEditor'
import { MetricPicker } from '../components/MetricPicker'
import { ClimateOverlay } from '../components/ClimateOverlay'
import { PlaceBrowser } from '../components/PlaceBrowser'
import { useToast } from '../components/Toast'
import { useData } from '../data/store'
import { MAX_PLACES, normalise, useSelection } from '../data/selection'
import { HEADLINE_KEYS, METRIC_BY_KEY, citySalarySource, type MetricDef } from '../data/registry'
import {
  LENS_LABEL, UNSTABLE_METRIC_KEYS, instabilityNote, isNeverAffordable, missingInputs,
  salaryByLens, stabilityOf, type Budget,
  yearsToHomeRange,
} from '../data/compute'
import { UnstableMark } from '../components/Unstable'
import { dropApprox, money, residencyRange, yearsRange } from '../data/format'
import type { Band, City, Country, Lens } from '../data/types'
import { downloadCsv, downloadJson } from '../lib/export'

const BANDS: Band[] = ['new_grad', 'mid', 'senior']
const BAND_LABEL: Record<Band, string> = {
  new_grad: 'Starting out',
  mid: 'Mid-level (3–5 yrs)',
  senior: 'Senior (6+ yrs)',
}
const LENSES: Lens[] = ['gross', 'net', 'after']
const LENS_BUTTON: Record<Lens, string> = {
  gross: 'Gross',
  net: 'After tax',
  after: 'After living costs',
}

export function Compare() {
  const data = useData()
  const sel = useSelection()
  const toast = useToast()
  const [params, setParams] = useSearchParams()

  const band = (params.get('band') as Band) ?? 'mid'
  const lens = (params.get('lens') as Lens) ?? 'gross'
  const view = params.get('view') === 'chart' ? 'chart' : 'table'

  const [budget, setBudget] = useState<Budget>({})
  const [pickerOpen, setPickerOpen] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [ready, setReady] = useState(false)

  // `?places` present at all means "a comparison was asked for" — that, not the
  // store, is what decides which of the two screens you are on. Picking places
  // in the browser fills the tray; pressing "Compare these →" is what commits
  // them to the address.
  const urlRaw = params.get('places')
  const comparisonAsked = urlRaw != null
  const urlIds = useMemo(
    () => normalise((urlRaw ?? '').split(',').filter((id) => data.cityById.has(id))),
    [urlRaw, data],
  )

  const update = useCallback(
    (patch: Record<string, string | null>) => {
      setParams((cur) => {
        const next = new URLSearchParams(cur)
        for (const [k, v] of Object.entries(patch)) {
          if (v == null) next.delete(k)
          else next.set(k, v)
        }
        return next
      }, { replace: true })
    },
    [setParams],
  )

  /* URL ⇄ store, one direction at a time.
   *
   * The address is the source of truth on this page: a link someone was sent
   * always wins, whether it arrived as a fresh load, a paste, or the back
   * button. Once the two agree, the store leads and the address follows with
   * replace: true, so six clicks do not cost six back presses.
   *
   * Which side moved is the whole question, and a single render cannot tell —
   * so both previous values are remembered and compared. Deciding from *what
   * changed* rather than from *what the values are* also makes this safe to run
   * twice on the same commit, which StrictMode does on mount. */
  const wanted = sel.ids.join(',')
  const prev = useRef<{ url: string | null; store: string } | null>(null)
  useEffect(() => {
    const before = prev.current ?? { url: null, store: '' }
    const urlMoved = urlRaw !== before.url
    const storeMoved = wanted !== before.store
    prev.current = { url: urlRaw, store: wanted }
    setReady(true)

    if (urlRaw == null || urlRaw === wanted) return

    if (urlMoved) {
      // Came from outside — the address wins, and is normalised back if it held
      // junk, duplicates or more than the six a comparison can hold.
      const clean = urlIds.join(',')
      sel.replace(urlIds)
      if (clean !== urlRaw) update({ places: clean || null })
    } else if (storeMoved) {
      update({ places: wanted || null })
    }
  }, [urlRaw, urlIds, wanted, sel, update])

  // Emptying the comparison returns to the browser and says why, so the screen
  // change never looks like something broke.
  const wasFilled = useRef(false)
  useEffect(() => {
    if (!ready) return
    if (comparisonAsked && sel.ids.length > 0) { wasFilled.current = true; return }
    if (wasFilled.current && sel.ids.length === 0) {
      wasFilled.current = false
      toast('Comparison cleared — choose new places')
    }
  }, [ready, comparisonAsked, sel.ids.length, toast])

  // Before the mount hand-off lands, read the deep link directly, so a shared
  // link paints its comparison on the first frame instead of flashing the browser.
  const activeIds = ready ? sel.ids : urlIds
  const cities = useMemo(
    () => activeIds.map((id) => data.cityById.get(id)).filter((c): c is City => !!c),
    [activeIds, data],
  )

  const metricKeys = useMemo(() => {
    const raw = params.get('metrics')
    const keys = raw ? raw.split(',').filter((k) => METRIC_BY_KEY.has(k)) : []
    return keys.length ? keys : HEADLINE_KEYS
  }, [params])
  const metrics = useMemo(
    () => metricKeys.map((k) => METRIC_BY_KEY.get(k)!).filter(Boolean),
    [metricKeys],
  )

  const rows = useMemo(
    () =>
      metrics.map((m) => ({
        metric: m,
        hint: rowHint(m, lens),
        values: cities.map((city) => ({ city, value: rowValue(m, city, data.countryById.get(city.country), band, lens) })),
      })),
    [metrics, cities, band, lens, data],
  )

  // See the note on .tablewrap[data-fits] in base.css: the wrapper only gets to
  // be a scroll container when it genuinely has something to scroll, so the
  // header row can pin to the viewport everywhere else.
  const tableWrap = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = tableWrap.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const apply = () => {
      el.dataset.fits = String(el.scrollWidth <= el.clientWidth)
    }
    apply()
    const ro = new ResizeObserver(apply)
    ro.observe(el)
    for (const child of el.children) ro.observe(child)
    return () => ro.disconnect()
  }, [view, cities.length, metrics.length])

  // The strip shows the real address, not a reconstruction of it, so it cannot
  // drift from what the browser holds. Commas are decoded back: URLSearchParams
  // escapes them, they are legal in a query string, and `places=berlin,toronto`
  // is the thing a reader is being invited to recognise.
  const shareUrl = useMemo(
    () => window.location.href.replace(/%2C/g, ','),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [params, wanted],
  )

  const exportRows = () =>
    rows.map((r) => {
      const row: Record<string, string | number | null> = { metric: r.metric.label }
      for (const v of r.values) row[v.city.name] = v.value
      return row
    })

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
      toast('Link copied — the whole comparison travels in the address')
    } catch {
      toast('Could not reach the clipboard — the address bar holds the same link')
    }
  }

  const openComparison = (ids: string[]) => {
    if (ids.length === 0) { toast('Pick at least one place first'); return }
    update({ places: ids.join(',') })
    window.scrollTo(0, 0)
  }

  /* ---------------- screen 1: choose your places ---------------- */
  if (!comparisonAsked || cities.length === 0) {
    return (
      <div className="wrap" style={{ paddingTop: 24, paddingBottom: 110 }}>
        <div className="kicker">Compare · {sel.ids.length} of {MAX_PLACES} places</div>
        <h1 className="pg">Choose your places</h1>
        <p className="oneline">
          Every city we hold, with its two defining numbers. Pick two to six —
          columns will keep your order, and nothing here is ranked.
        </p>
        <PlaceBrowser
          variant="page"
          onPair={(ids) => { sel.replace(ids); openComparison(ids) }}
        />
        <SelectionTray onCompare={() => openComparison(sel.ids)} />
      </div>
    )
  }

  /* ---------------- screen 2: side by side ---------------- */
  return (
    <div className="wrap" style={{ paddingTop: 24 }}>
      <div className="kicker">Compare · {cities.length} of {MAX_PLACES} places</div>
      <h1 className="pg">Side by side</h1>
      <p className="oneline">
        Columns stay in the order you added them. Nothing here is ranked or scored —
        tap any number to see exactly where it came from.
      </p>

      <div className="toolbar" role="toolbar" aria-label="Comparison controls">
        <div className="tgroup">
          <span className="tl">Experience</span>
          <div className="seg">
            {BANDS.map((b) => (
              <button key={b} aria-pressed={band === b} onClick={() => update({ band: b })}>
                {BAND_LABEL[b]}
              </button>
            ))}
          </div>
        </div>
        <div className="tgroup">
          <span className="tl">Salary shown as</span>
          <div className="seg">
            {LENSES.map((l) => (
              <button key={l} aria-pressed={lens === l} onClick={() => update({ lens: l })}>
                {LENS_BUTTON[l]}
              </button>
            ))}
          </div>
        </div>
        <div className="tactions">
          {/* The label names where the button goes, so it is not also a pressed
              state — "pressed" plus "⇄ table" reads as a contradiction. */}
          <button className="tbtn"
            onClick={() => update({ view: view === 'chart' ? null : 'chart' })}>
            {view === 'chart' ? '⇄ table' : '⇄ chart'}
          </button>
          {/* Both toasts are true because export.ts writes the notes: the CSV
              preamble says empty means no data, the JSON wrapper carries the
              sources note. */}
          <button className="tbtn" onClick={() => {
            downloadCsv('compass-compare.csv', exportRows())
            toast('CSV saved — empty cells mean no data, never zero')
          }}>⤓ CSV</button>
          <button className="tbtn" onClick={() => {
            downloadJson('compass-compare.json', {
              band, lens, cities: cities.map((c) => c.id), rows: exportRows(),
            })
            toast('JSON saved — with sources note attached')
          }}>⤓ JSON</button>
        </div>
      </div>

      <div className="urlstrip">
        <span>this address <i>is</i> the comparison —</span>
        <code>{shareUrl}</code>
        <button onClick={copyLink}>copy link</button>
      </div>

      <div className="citychips">
        {cities.map((c) => (
          <span key={c.id} className="kchip">
            <Flag cc={c.country} size={16} />
            <Link to={`/city/${c.id}`}>{c.name}</Link>
            {cities.length > 1 && (
              <button onClick={() => sel.remove(c.id)} aria-label={`Remove ${c.name}`}>✕</button>
            )}
          </span>
        ))}
        {cities.length < MAX_PLACES && (
          <button className="addbtn" onClick={() => setSheetOpen(true)}>+ add a city</button>
        )}
      </div>

      {view === 'table' ? (
        <div className="tablewrap" ref={tableWrap}>
          <table className="cmp">
            <thead>
              <tr>
                <th className="mlab-h">Metric</th>
                {cities.map((c) => (
                  <th key={c.id}>
                    <span className="cityh">
                      <Flag cc={c.country} size={16} />
                      <b>{c.name}</b>
                      {cities.length > 1 && (
                        <button onClick={() => sel.remove(c.id)} aria-label={`Remove ${c.name}`}>✕</button>
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ metric, hint, values }) => (
                <tr key={metric.key}>
                  <td className="mlab">{metric.label}<small>{hint}</small></td>
                  {values.map(({ city, value }) => (
                    <td key={city.id}>
                      <Cell metric={metric} city={city} value={value} band={band} lens={lens} />
                    </td>
                  ))}
                </tr>
              ))}
              <tr>
                <td className="mlab">Staying permanently<small>typical — real cases vary</small></td>
                {cities.map((c) => {
                  const k = data.countryById.get(c.country)
                  return (
                    <td key={c.id}>
                      <ResidencyBar cc={c.country} pr={k?.pr_years_typical ?? null}
                        cit={k?.citizenship_years_typical ?? null} />
                      {k?.dual_citizenship.allowed === true && (
                        <div className="staynote">You keep your other passport</div>
                      )}
                      {k?.dual_citizenship.allowed === false && (
                        <div className="staynote">Dual citizenship normally not allowed</div>
                      )}
                    </td>
                  )
                })}
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        <ChartView rows={rows} band={band} />
      )}

      <p className="foot">
        Salary rows currently show: <b>{LENS_LABEL[lens]}</b> · at <b>{BAND_LABEL[band]}</b>.
        Change either above and every figure recalculates — the address bar follows.
      </p>
      <p className="foot">
        <b>Honest by design:</b> a place missing a figure says which one is missing, never a dash
        that could mean anything — add Aarhus to see it. Where nothing is left over after rent and
        living, “years to a home” says <i>never on this salary</i> rather than a four-digit number.
      </p>

      {/* Metric selection is unchanged by this package — same picker, same URL key. */}
      <button className="pill" style={{ marginTop: 14, borderStyle: 'dashed' }}
        onClick={() => setPickerOpen(true)}>
        + add a metric
      </button>

      {pickerOpen && (
        <MetricPicker
          selected={metricKeys}
          onClose={() => setPickerOpen(false)}
          onChange={(keys) => update({ metrics: keys.length ? keys.join(',') : null })}
        />
      )}

      <BudgetEditor cities={cities} budget={budget} onChange={setBudget} band={band} />

      <div className="panel" style={{ marginTop: 12 }}>
        <h2>A year of weather, side by side</h2>
        <div className="sub">
          Twelve-month normals for the places you are comparing. An annual average hides whether a
          February is survivable.
        </div>
        <ClimateOverlay cities={cities} />
      </div>

      {sheetOpen && <AddCitySheet onClose={() => setSheetOpen(false)} />}
    </div>
  )
}

/* ---------------------------------------------------------------- rows ---- */

/** The salary row follows the lens, as drawn: gross → after tax → what is left.
 *  Every other metric is exactly what the registry says it is. */
function rowValue(m: MetricDef, city: City, country: Country | undefined, band: Band, lens: Lens): number | null {
  if (m.key === 'salary_gross') return salaryByLens(city, band, lens)
  return m.value(city, country, band)
}

/** Only the salary row's hint moves, because only its number moves with the
 *  lens. Every other row states what the registry says it states. */
function rowHint(m: MetricDef, lens: Lens): string {
  return m.key === 'salary_gross' ? LENS_LABEL[lens] : m.hint
}

/** Which input is missing, in words. `missingInputs()` is the single source of
 *  truth for the list; the only thing done to it here is to drop the purchase
 *  price from rows whose formula never uses it, so the sentence stays true. */
function missingReason(m: MetricDef, city: City, band: Band, lens: Lens): string {
  const all = missingInputs(city, band)
  const forSavings = all.filter((i) => i !== 'apartment price')
  const list = (xs: string[]) => (xs.length ? xs.join(' and ') : 'an input')

  if (m.key === 'salary_gross') {
    return lens === 'gross' || lens === 'net'
      ? `We have no salary figure for ${city.name}.`
      : `Missing ${list(forSavings)} for ${city.name}, so this can’t be worked out.`
  }
  if (m.key === 'savings') return `Missing ${list(forSavings)} for ${city.name}, so this can’t be worked out.`
  if (m.key === 'years_to_home' || m.key === 'm2_per_year') return `Missing ${list(all)} for ${city.name}.`
  if (m.key === 'salary_levels_fyi') return `No levels.fyi page holds enough reports for ${city.name}.`
  if (m.key === 'salary_net') return `Missing ${list(all.filter((i) => i === 'salary' || i === 'tax rate'))} for ${city.name}.`
  return `We have no ${m.label.toLowerCase()} figure for ${city.name}.`
}

/* Every figure in this table opens its source card — no exceptions. Most
 * metrics carry a source in the registry; these are the ones that do not,
 * because they are worked out here rather than read from a file. The formula is
 * the source, so the card states it. */
const COMPUTED_WHAT: Record<string, (c: City, k: Country | undefined) => string> = {
  savings: (c, k) =>
    'Net salary − 12 × (rent + living costs).'
    + (c.net_pct != null && k ? ` ${c.net_pct}% of gross survives tax in ${k.name}.` : ''),
  years_to_home: (c) => {
    // Package 16 — state the band the figure occupies under one rounding step
    // of its own inputs, rather than implying the point is exact.
    const r = yearsToHomeRange(c, 'mid')
    const band = r && Math.round(r[1]) !== Math.round(r[0])
      ? ` Rounding on rent alone moves this to ${yearsRange(r, null)}.` : ''
    return 'Price of a 90 m² flat outside the centre ÷ what you save in a year.'
      + (c.apt_price_outside_usd_m2 != null ? ` Here: 90 × ${money(c.apt_price_outside_usd_m2)}/m².` : '')
      + band
  },
  m2_per_year: () => 'What a year of saving buys: savings ÷ price per m² outside the centre.',
  salary_net: (c, k) =>
    k?.tax.net_note
    ?? (c.net_pct != null ? `${c.net_pct}% of gross survives tax and social contributions for a single person.` : 'Country tax model.'),
  total_monthly: () => 'Rent outside the centre + living costs for one person, both crowd-reported.',
}

/** What to put on the card when the registry has no source of its own.
 *
 * Package 27, Tier 2: this used to link `country.sources[0]` or
 * `city.sources[0]` — whichever URL a country or city's own harvesters
 * happened to append first, regardless of what this specific metric asked
 * for. For Norway's own `pr_years` (a VISA-timeline figure) that was a
 * private immigration-law firm's blog post about salary thresholds, under a
 * label that said "official sources" — the GulfTalent defect in a different
 * costume, a position in an unordered array standing in for a recorded
 * relationship. Every metric that had an identifiable, verified source has
 * one now (`registry.ts` — pr_years/citizenship_years/tuition/
 * post_study_months read a curated per-country immigration-authority host;
 * ict_share, healthcare, peace_rank, hdi and net_pct all have their own
 * fixed citation). What reaches this function today is only the handful with
 * no verified single source on record at all — climate figures and Tehran
 * flight time, both hand-estimated at project inception with no per-city
 * citation trail the way `salary_usd_year`'s own notes turned out to have
 * (see REPORT-P27.md), and `english_work`, a hand-judged category informed
 * by EF EPI among other things but not identical to it. Honest about that
 * now instead of guessing a link: no URL, just what the figure is. */
function fallbackSource(m: MetricDef, city: City, country: Country | undefined) {
  const computed = COMPUTED_WHAT[m.key]
  if (computed) return { name: 'Computed — formula on screen', what: computed(city, country) }
  return { name: 'Compiled — no single source on record', what: m.hint }
}

/** The salary row's own source card changes with the lens, because the number
 *  it explains changes with the lens. */
function salarySource(city: City, country: Country | undefined, lens: Lens) {
  if (lens === 'gross') {
    return {
      ...citySalarySource(city),
      what: city.salary_usd_year.note ?? 'Market-wide band for this city, gross per year.',
    }
  }
  if (lens === 'net') {
    return {
      name: 'OECD Taxing Wages + national calculators',
      what: country?.tax.net_note
        ?? (city.net_pct != null
          ? `${city.net_pct}% of gross survives ${country?.name ?? 'this country'}’s tax and social contributions for a single person.`
          : 'Country tax model.'),
    }
  }
  return {
    name: 'Computed — formula on screen',
    what: 'Net salary − 12 × (rent + living costs), all three from the sources on this page.',
  }
}

function Cell({ metric, city, value, band, lens }:
  { metric: MetricDef; city: City; value: number | null; band: Band; lens: Lens }) {
  const data = useData()
  const country = data.countryById.get(city.country)

  // years-to-home has a third state: computable inputs, but nothing is saved.
  if (metric.key === 'years_to_home' && value == null && isNeverAffordable(city, band)) {
    return (
      <span className="nvr">
        never on this salary
        <small>nothing is left over after rent and living costs</small>
      </span>
    )
  }

  if (value == null) {
    return <Figure missing missingReason={missingReason(metric, city, band, lens)}>{null}</Figure>
  }

  const src = metric.key === 'salary_gross'
    ? salarySource(city, country, lens)
    : metric.source?.(city, country) ?? fallbackSource(metric, city, country)
  const negative = value < 0
  // A figure smaller than the rounding on its own inputs keeps its place and
  // its number, and says so — here and on every other surface.
  const shaky = UNSTABLE_METRIC_KEYS.has(metric.key) && stabilityOf(city, band) === 'unstable'
  const note = shaky ? instabilityNote(city, band) : null
  const body = (
    <span className="big" style={negative ? { color: 'var(--warn)' } : undefined}>
      {/* Package 16 — gated by `shaky`, which was already computed two lines up
        * and already scopes the mark to UNSTABLE_METRIC_KEYS. This rendered
        * UNCONDITIONALLY before, and UnstableMark's own internal test is only
        * "is this CITY unstable" — so every metric on an unstable city got the
        * mark, including ones with no savings input at all. Milan's "Years to
        * permanent residency" (a visa-policy constant: 5 years, nothing
        * derived) was labelled "smaller than the rounding on its own inputs".
        * compute.ts already says why the set exists: "The three savings-derived
        * metrics share one root cause, so they share one flag." This is that
        * flag finally being read here. Found by reading the rendered page while
        * chasing an unrelated "≈~" typography glitch. */}
      {shaky && <UnstableMark city={city} band={band} />}
      {/* Package 16 — the "≈" above is the stronger marker; drop the "~" the
        * formatter adds so the cell does not read "≈~5 yrs". */}
      {shaky
        ? dropApprox(negative ? `−${metric.format(Math.abs(value))}` : metric.format(value))
        : (negative ? `−${metric.format(Math.abs(value))}` : metric.format(value))}
    </span>
  )

  return (
    <>
      <Figure source={{
        ...src,
        asOf: city.as_of,
        confidence: metric.confidence,
        what: note ? `${src.what ? `${src.what} ` : ''}${note}` : src.what,
      }}>{body}</Figure>
      {note && <span className="unstable-note">{note}</span>}
    </>
  )
}

function ResidencyBar({ cc, pr, cit }: { cc: string; pr: number | null; cit: number | null }) {
  if (pr == null) {
    return (
      <span className="staywarn">
        {cc === 'AE' ? 'golden visa only — no citizenship path' : 'no permanent path'}
      </span>
    )
  }
  const scale = 9
  return (
    <span className="stayrow">
      <FlagRibbon cc={cc} width={Math.max(12, pr * scale)} />
      {cit != null && cit > pr && (
        <span aria-hidden="true" className="ext" style={{ width: (cit - pr) * scale }} />
      )}
      <b>{residencyRange(pr, cit)}</b>
    </span>
  )
}

/* --------------------------------------------------------------- chart ---- */

/** One small multiple per metric, bars in the user's column order. */
function ChartView({ rows, band }: {
  rows: { metric: MetricDef; hint: string; values: { city: City; value: number | null }[] }[]
  band: Band
}) {
  return (
    <LayoutGroup>
      <motion.div layout className="chartgrid">
        <AnimatePresence mode="popLayout">
          {rows.map(({ metric, hint, values }) => {
            // Only positive values set the scale — a negative "kept per year" is
            // a fact about that city, not a new zero for everyone else. Nor does
            // a figure the site has flagged as rounding-limited: it keeps its
            // bar and its number, but it does not decide the scale.
            const risky = UNSTABLE_METRIC_KEYS.has(metric.key)
            const nums = values
              .filter((v) => !(risky && stabilityOf(v.city, band) === 'unstable'))
              .map((v) => v.value).filter((v): v is number => v != null && v > 0)
            const max = nums.length ? Math.max(...nums) : 0
            return (
              <motion.div key={metric.key} className="panel" layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97 }}
                transition={{ type: 'spring', stiffness: 380, damping: 32 }}>
                <h2>{metric.label}</h2>
                <div className="sub">{hint}</div>
                {values.map(({ city, value }) => {
                  const shaky = risky && stabilityOf(city, band) === 'unstable'
                  return (
                    <div key={city.id} className="brow">
                      <div className="l">
                        <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                          <Flag cc={city.country} size={13} />{city.name}
                        </span>
                        <b className="tnum">
                          {shaky && <UnstableMark city={city} band={band} />}
                          {value == null
                            ? 'no data'
                            : shaky
                              ? dropApprox(value < 0 ? `−${metric.format(Math.abs(value))}` : metric.format(value))
                              : (value < 0 ? `−${metric.format(Math.abs(value))}` : metric.format(value))}
                        </b>
                      </div>
                      <div className="track">
                        {value != null && value > 0 && max > 0 && (
                          // A flagged value runs the full track in the warning
                          // colour: it is past the scale, and the number beside
                          // it is the real one.
                          <div className="fill" style={{
                            width: `${Math.min(100, Math.max(2, (value / max) * 100))}%`,
                            background: shaky ? 'var(--warn)' : `var(--c-${city.country})`,
                          }} />
                        )}
                      </div>
                    </div>
                  )
                })}
                <div className="chartnote">
                  Bars scale to the largest value shown — not to a ranking.
                  {values.some((v) => v.value == null) && ' Cities with no data have no bar.'}
                  {values.some((v) => risky && stabilityOf(v.city, band) === 'unstable')
                    && ' A ≈ marks a figure smaller than the rounding on its own inputs — it keeps its number but does not set the scale.'}
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </motion.div>
    </LayoutGroup>
  )
}

/* ---------------------------------------------------------------- bits ---- */

/** The dark tray on screen 1: what you have picked, and the way forward. */
function SelectionTray({ onCompare }: { onCompare: () => void }) {
  const data = useData()
  const sel = useSelection()
  const cities = sel.ids.map((id) => data.cityById.get(id)).filter((c): c is City => !!c)

  return (
    <div className={`tray${cities.length ? ' show' : ''}`} aria-live="polite">
      <span className="cnt">{cities.length} {cities.length === 1 ? 'place' : 'places'}</span>
      <div className="chips">
        {cities.map((c) => (
          <span key={c.id} className="tchip">
            <Flag cc={c.country} size={13} />
            {c.name}
            <button onClick={() => sel.remove(c.id)} aria-label={`Remove ${c.name}`}>✕</button>
          </span>
        ))}
      </div>
      <button className="go" onClick={onCompare}>Compare these →</button>
      <button className="clear" onClick={() => sel.clear()}>Clear</button>
    </div>
  )
}

/** The same browser, opened as a sheet. One component, two presentations. */
function AddCitySheet({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <>
      <div className="sheetbg show" onClick={onClose} />
      <div className="sheet show" role="dialog" aria-label="Add a city">
        <PlaceBrowser variant="sheet" onClose={onClose} />
      </div>
    </>
  )
}

export { money }
