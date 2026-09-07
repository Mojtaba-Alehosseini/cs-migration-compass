/* Package 43, tier 1 — the site as it actually is.
 *
 * Every route and every material state the inventory reaches, screenshotted
 * in both modes at three viewports, plus all four themes for a representative
 * page from each group, plus the states people actually land in: a loading
 * skeleton, a data error, an open <Derived> card. The screenshots are the
 * artifact; this file is the committable half of it, since .status/ is
 * gitignored.
 *
 * It reuses the inventory's own target list and state setups rather than
 * rebuilding them — package 33 classified the 28 material controls and
 * package 34 built the harness that drives them. What it adds is only what a
 * critique needs and an assertion does not: modes, viewports, themes, and a
 * picture.
 *
 * Readiness, not a timer. A screenshot of a skeleton is not a screenshot of
 * the page — package 40 lost two controls to a probe that sampled before the
 * panel mounted. Every capture waits for network-idle plus DOM-stable, and a
 * viewport change waits again, because the field re-measures its width.
 *
 * Run:  node scripts/tests/capture_site.mjs
 *       CAPTURE_ONLY=openings,compare node scripts/tests/capture_site.mjs
 * Needs a preview server on :4173.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { launch, openPage } from './cdp.mjs'
import { defaultTargets, SETUP_HELPERS, REPO } from './inventory_figures.mjs'

const BASE = process.env.BASE_URL ?? 'http://localhost:4173/'
const OUT = REPO + '.status/screenshots/p43/'
mkdirSync(OUT, { recursive: true })

const ONLY = new Set((process.env.CAPTURE_ONLY ?? '').split(',').map((s) => s.trim()).filter(Boolean))

/* The three viewports the work order names. 390 is captured as a phone —
 * touch, mobile UA — so hover states cannot flatter it. */
const VIEWPORTS = [
  ['1440', 1440, 900, false],
  ['1366', 1366, 768, false],
  ['390', 390, 844, true],
]
const MODES = ['light', 'dark']
const THEMES = ['compass', 'editorial', 'terminal', 'warm']

/* One page per group gets every theme: the two the owner says look right, the
 * one with a design pass behind it, and one from each group that has never
 * had one. Everything else is captured in the default theme. */
const THEME_PAGES = new Set(['home', 'compare', 'work', 'openings', 'data', 'city-berlin', 'country-AE', 'postings-seed'])

const { targets } = defaultTargets(BASE)
const index = []
let seq = 0
const pad = (n) => String(n).padStart(3, '0')

const { port, close } = await launch({ port: 9920 })
const page = await openPage(port)

/* Theme and mode. The ThemeProvider reads both from localStorage at mount and
 * writes them as attributes on <html>; the CSS keys off the attributes. So a
 * MODE change is an attribute flip (no reload), and a THEME change is written
 * to storage and then loaded for real, so the provider's own state agrees with
 * what is on screen. */
const setMode = async (mode) => {
  await page.eval(`document.documentElement.setAttribute('data-mode', ${JSON.stringify(mode)})`)
}
const setThemeAndLoad = async (theme, mode, url) => {
  /* localStorage belongs to an origin, and a fresh tab sits on about:blank,
   * which has none — reading it there is a SecurityError. So the first call
   * loads the site once to get onto its origin before writing anything. */
  const here = await page.eval('location.href')
  if (!here.startsWith(BASE)) {
    await page.goto(url)
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'first load' })
  }
  await page.eval(`(() => {
    localStorage.setItem('compass:theme', ${JSON.stringify(theme)})
    localStorage.setItem('compass:mode', ${JSON.stringify(mode)})
    return 'ok'
  })()`)
  await page.goto(url)
  await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${theme}/${mode} load` })
}

/* The inventory's own landing sequence, reused rather than re-derived: bounce
 * through a route that does not exist so a state target cannot inherit the
 * previous capture's state, scroll so deferred panels mount, then run the
 * state's setup with the shared helpers. */
async function land(id, url, setup) {
  if (setup) {
    await page.hashGo(url.replace(/#.*$/, '#/no-such-route'))
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — remount` })
  }
  await page.hashGo(url)
  await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — ${url}` })
  if (setup) {
    await page.eval('window.scrollTo(0, document.body.scrollHeight)')
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — deferred panels` })
    await page.eval(SETUP_HELPERS)
    const applied = await page.eval(setup)
    if (typeof applied === 'string' && applied.startsWith('NO ')) {
      throw new Error(`setup for "${id}" did not find its control: ${applied}`)
    }
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — after setup` })
  }
  await page.eval('window.scrollTo(0, 0)')
}

async function shotAt(id, theme, mode, vp, { fullPage = false, note = '' } = {}) {
  const [name, w, h, mobile] = vp
  await page.viewport(w, h, mobile)
  await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: `${id} — ${name} settle` })
  const file = `${pad(seq)}-${id}--${theme}-${mode}-${name}${fullPage ? '-full' : ''}.png`
  await page.shot(OUT + file, { fullPage })
  index.push({ file, id, theme, mode, viewport: name, fullPage, note })
}

/* ---- the sweep ---------------------------------------------------------- */
const errors = []
let done = 0
const list = targets.filter(([id]) => !ONLY.size || ONLY.has(id))

await setThemeAndLoad('compass', 'light', BASE)
for (const [id, url, setup] of list) {
  seq += 1
  done += 1
  process.stdout.write(`  [${String(done).padStart(3)}/${list.length}] ${id}` + String.fromCharCode(10))
  try {
    await land(id, url, setup)
    for (const mode of MODES) {
      await setMode(mode)
      for (const vp of VIEWPORTS) await shotAt(id, 'compass', mode, vp)
    }
    // The whole page, once, in the default theme — what a critique reads.
    await setMode('light')
    await shotAt(id, 'compass', 'light', VIEWPORTS[0], { fullPage: true })
  } catch (e) {
    errors.push({ id, error: String((e && e.message) || e) })
    index.push({ file: null, id, error: String((e && e.message) || e) })
  }
}

/* ---- the other three themes, on the representative pages ---------------- */
for (const theme of THEMES.slice(1)) {
  for (const mode of MODES) {
    for (const [id, url, setup] of list.filter(([i]) => THEME_PAGES.has(i))) {
      seq += 1
      process.stdout.write(`  theme ${theme}/${mode}: ${id}` + String.fromCharCode(10))
      try {
        await setThemeAndLoad(theme, mode, BASE)
        await land(id, url, setup)
        for (const vp of VIEWPORTS) await shotAt(id, theme, mode, vp)
      } catch (e) {
        errors.push({ id: `${id}/${theme}/${mode}`, error: String((e && e.message) || e) })
      }
    }
  }
}
await setThemeAndLoad('compass', 'light', BASE)

/* ---- the states people actually land in --------------------------------- */
if (!ONLY.size) {
  /* Loading: the one screenshot that is deliberately NOT waited for, and is
   * labelled as such. Taken straight after navigation, before readiness. */
  seq += 1
  try {
    await page.hashGo(BASE + '#/no-such-route')
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'reset' })
    await page.viewport(1440, 900)
    await page.hashGo(BASE + '#/openings')
    const file = `${pad(seq)}-openings-LOADING--compass-light-1440.png`
    await page.shot(OUT + file)
    index.push({ file, id: 'openings-LOADING', theme: 'compass', mode: 'light', viewport: '1440', fullPage: false,
      note: 'deliberately unwaited: the skeleton a reader sees before the index arrives' })
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'openings after loading shot' })
  } catch (e) { errors.push({ id: 'openings-LOADING', error: String(e.message || e) }) }

  /* Error: block the data a theme needs and load it. This is the "could not
   * be loaded — nothing is drawn rather than something approximate" surface. */
  seq += 1
  try {
    await page.send('Network.setBlockedURLs', { urls: ['*bis_property_prices*', '*teranet*', '*housing*'] })
    await page.hashGo(BASE + '#/no-such-route')
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'reset' })
    await page.hashGo(BASE + '#/explore/housing')
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'housing error' })
    for (const mode of MODES) {
      await setMode(mode)
      for (const vp of VIEWPORTS) await shotAt('explore-housing-ERROR', 'compass', mode, vp, { note: 'history data blocked at the network layer' })
    }
    await setMode('light')
    await page.send('Network.setBlockedURLs', { urls: [] })
  } catch (e) {
    errors.push({ id: 'explore-housing-ERROR', error: String(e.message || e) })
    await page.send('Network.setBlockedURLs', { urls: [] })
  }

  /* A <Derived> card open — the method behind a tap, as a reader sees it. */
  seq += 1
  try {
    await page.hashGo(BASE + '#/no-such-route')
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'reset' })
    await page.hashGo(BASE + '#/city/berlin')
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'berlin' })
    const opened = await page.eval(`(() => {
      const b = [...document.querySelectorAll('button')].find((x) => /show how this number was calculated/i.test(x.textContent || ''))
      if (!b) return 'NO derived trigger'
      b.scrollIntoView({ block: 'center' }); b.click(); return 'ok'
    })()`)
    if (opened !== 'ok') throw new Error(opened)
    await page.waitFor(`!!document.querySelector('[role="dialog"]')`, { timeoutMs: 10000, label: 'derived card' })
    for (const mode of MODES) {
      await setMode(mode)
      for (const vp of VIEWPORTS) {
        const [name, w, h, mobile] = vp
        await page.viewport(w, h, mobile)
        await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'card settle' })
        // Keep the card in frame at every size.
        await page.eval(`(() => { const d = document.querySelector('[role="dialog"]'); if (d) d.scrollIntoView({ block: 'center' }) })()`)
        const file = `${pad(seq)}-city-berlin-DERIVED-OPEN--compass-${mode}-${name}.png`
        await page.shot(OUT + file)
        index.push({ file, id: 'city-berlin-DERIVED-OPEN', theme: 'compass', mode, viewport: name, fullPage: false, note: 'a <Derived> method card open' })
      }
    }
    await setMode('light')
  } catch (e) { errors.push({ id: 'city-berlin-DERIVED-OPEN', error: String(e.message || e) }) }
}

/* ---- the index ---------------------------------------------------------- */
const shots = index.filter((i) => i.file)
writeFileSync(OUT + 'index.json', JSON.stringify({ generated_at: new Date().toISOString(), base: BASE, count: shots.length, errors, shots: index }, null, 1))
const md = [
  `# Package 43 capture — ${shots.length} screenshots`, '',
  `Generated ${new Date().toISOString()} against ${BASE}.`, '',
  errors.length ? `**${errors.length} target(s) could not be captured:**\n` + errors.map((e) => `- \`${e.id}\` — ${e.error}`).join('\n') : 'Every target captured.', '',
  '| # | target | theme | mode | viewport | file |', '|---|---|---|---|---|---|',
  ...shots.map((s) => `| ${s.file.slice(0, 3)} | ${s.id}${s.note ? ` — ${s.note}` : ''} | ${s.theme} | ${s.mode} | ${s.viewport}${s.fullPage ? ' (full page)' : ''} | \`${s.file}\` |`),
]
writeFileSync(OUT + 'INDEX.md', md.join(String.fromCharCode(10)))
console.log(`\n${shots.length} screenshots, ${errors.length} error(s) -> ${OUT}`)
errors.forEach((e) => console.log(`  ERROR ${e.id}: ${e.error}`))
page.close()
close()
