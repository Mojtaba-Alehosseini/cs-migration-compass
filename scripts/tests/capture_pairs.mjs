/* Package 43, tier 4 — before/after pairs for the judgement calls.
 *
 * The work order's rule for this package: a change that is a matter of taste
 * ships with a before/after screenshot pair and one sentence. The owner reads
 * screenshots, not diffs, and a change he cannot see and compare is a change
 * he cannot reject. So this exists to make every taste call reversible on
 * sight.
 *
 * Run it once against the build BEFORE the change, once after:
 *
 *   PAIR_SIDE=before node scripts/tests/capture_pairs.mjs
 *   ...make the change, rebuild...
 *   PAIR_SIDE=after  node scripts/tests/capture_pairs.mjs
 *
 * Frames land in .status/screenshots/p43/pairs/<side>/ under the same names,
 * so before/J1-seg-city.png and after/J1-seg-city.png are the same frame of
 * the same page in the same theme, and the only difference in them is the
 * change. Same readiness discipline as the tier 1 capture: network-idle plus
 * DOM-stable with a throwing timeout, never a fixed sleep.
 *
 * PAIR_ONLY=J1,J4 narrows the set while iterating.
 */
import { mkdirSync } from 'node:fs'
import { launch, openPage } from './cdp.mjs'
import { REPO } from './inventory_figures.mjs'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const SIDE = process.env.PAIR_SIDE ?? 'before'
const ONLY = new Set((process.env.PAIR_ONLY ?? '').split(',').map((s) => s.trim()).filter(Boolean))
const OUT = `${REPO}/.status/screenshots/p43/pairs/${SIDE}`

/* id, route, theme, mode, [w, h], optional setup expression, optional note.
 * One frame per judgement call, in the theme and at the width where the call
 * is actually visible. */
const SHOTS = [
  ['J1-seg-city', '#/city/berlin', 'compass', 'light', 1440, 900, null,
    'the band picker, against Compare\'s own segmented control'],
  ['J1-seg-openings', '#/openings', 'compass', 'light', 1440, 900, null,
    'the List/Map toggle, third form of the same control'],
  ['J1-seg-compare', '#/compare?places=oslo,copenhagen,berlin', 'compass', 'light', 1440, 900, null,
    'the reference: what a segmented control looks like here'],
  ['J2-seg-thumb', '#/explore/money', 'compass', 'light', 1440, 900, null,
    'the sliding thumb, painted over by a duplicate rule'],
  ['J3-openings-top', '#/openings', 'compass', 'light', 390, 844, null,
    'twelve lines of prose before the first control, on a phone'],
  ['J3-openings-top-wide', '#/openings', 'compass', 'light', 1440, 900, null,
    'the same opening at desktop width'],
  ['J4-loading', '#/openings', 'compass', 'light', 1440, 900, 'SKELETON',
    'the loading state, deliberately unwaited'],
  ['J5-chart-text', '#/explore/housing', 'compass', 'light', 1440, 900, null,
    'axis ticks and the "off this scale" refusal mark'],
  ['J6-country-grid', '#/country/AE', 'compass', 'light', 1440, 2200, null,
    'cards stretched to a common height'],
  ['J6-country-grid-us', '#/country/US', 'compass', 'light', 1440, 2200, null,
    'the same on a country with more to say'],
  ['J7-measure-city', '#/city/berlin', 'compass', 'light', 1440, 1700, null,
    'the reading width across a whole city page'],
  ['J8-seed-density', '#/postings-seed', 'compass', 'light', 1440, 900, null,
    'HIGH / MEDIUM / LOW as prose, on the sibling page of the chip vocabulary'],
  ['J9-header-390', '#/', 'compass', 'light', 390, 844, null,
    'the header: three rows and two labels broken mid-phrase'],
  ['J9-header-1440', '#/', 'compass', 'light', 1440, 900, null,
    'the same header with room'],
]

const chrome = await launch({ port: 9971 })
const page = await openPage(chrome.port)
mkdirSync(OUT, { recursive: true })

/* localStorage belongs to an origin and a fresh tab sits on about:blank, which
 * has none. Load the site once before writing anything, then FULLY reload —
 * the theme is applied by an inline script before first paint, so a hash
 * change would leave the previous theme on screen. */
await page.goto(BASE)
await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'first load' })

let n = 0
for (const [id, route, theme, mode, w, h, setup, note] of SHOTS) {
  if (ONLY.size && ![...ONLY].some((k) => id.startsWith(k))) continue
  await page.viewport(w, h)
  await page.eval(`(() => {
    localStorage.setItem('compass:theme', ${JSON.stringify(theme)})
    localStorage.setItem('compass:mode', ${JSON.stringify(mode)})
    return 'ok'
  })()`)
  /* Reload through the ROOT, then hashGo to the route.
   *
   * goto() waits for a load event, and a navigation that only changes the
   * fragment never fires one — so goto('…/#/openings') from '…/#/city/berlin'
   * hangs forever. Dropping the fragment IS a real navigation, which is why
   * capture_site.mjs also reloads through BASE. The real load is also what
   * re-runs index.html's inline theme script; without it the frame would carry
   * the previous theme while claiming this one. */
  const url = BASE + route
  await page.goto(BASE)
  await page.waitForReady({ quietMs: 250, timeoutMs: 40000, label: `${id} — root` })
  await page.hashGo(url)
  if (setup !== 'SKELETON') {
    // The skeleton is a state you cannot wait for: waiting is what ends it.
    await page.waitForReady({ quietMs: 350, timeoutMs: 40000, label: `${id} — load` })
  }
  const got = await page.eval(`document.documentElement.getAttribute('data-theme') + '/' + document.documentElement.getAttribute('data-mode')`)
  if (got !== `${theme}/${mode}`) throw new Error(`${id}: asked for ${theme}/${mode}, page is ${got}`)
  await page.shot(`${OUT}/${id}.png`, { fullPage: false })
  n++
  console.log(`  [${String(n).padStart(2)}] ${id.padEnd(22)} ${theme}/${mode} ${w}x${h}  ${note}`)
}
console.log(`\nwrote ${n} ${SIDE} frames to ${OUT}`)
chrome.close()
