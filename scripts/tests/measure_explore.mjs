/* Package 28, Tier 1 — measure Explore before touching it.
 *
 * Package 26's Tier 3 was written and never run; this is that tier, carried
 * forward. The owner's whole brief is four words ("explore need more edit and
 * analyze"), it predates packages 24-27, and the `/work` redesign only worked
 * because the complaint was measured against the source first. So: numbers and
 * screenshots, no opinions, nothing changed.
 *
 * Reads a SERVED PRODUCTION BUILD, the same target the regression suites use:
 *     cd site && npm run build && npm run preview     # http://localhost:4173/
 *     node scripts/tests/measure_explore.mjs
 *
 * Two things this file is careful about, both learned from this repo's own
 * history:
 *   - Paths anchor to this module, never to the working directory. CI runs the
 *     browser suites with `working-directory: site`, and package 25's Gate 12
 *     lost time to exactly that.
 *   - Every navigation carries a cache-busting query so it is a real document
 *     load. A bare hash change fires no load event (cdp.mjs's goto would wait
 *     forever) AND would leave resource timings belonging to the previous
 *     theme. The cost pass additionally launches a FRESH Chrome per theme, so
 *     each number is a cold-cache first visit rather than a warm re-read of
 *     what an earlier theme already pulled.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { launch, openPage } from './cdp.mjs'

const REPO = fileURLToPath(new URL('../../', import.meta.url))
const SHOTS = REPO + '.status/screenshots/'
const BASE = process.env.BASE ?? 'http://localhost:4173/'

const THEMES = ['money', 'visa', 'jobs', 'housing', 'people', 'life', 'climate']
// 'all' | 'shots' | 'measure' — lets a corrected phase be re-run on its own.
const ONLY = process.env.ONLY ?? 'all'
const VIEWPORTS = { desktop: [1440, 900], mobile: [390, 844] }
const MODES = ['light', 'dark']

mkdirSync(SHOTS, { recursive: true })
const say = (s) => console.log(s)
let nav = 0
const url = (theme) => `${BASE}?m=${++nav}#/explore/${theme}`

const preview = await fetch(BASE).catch(() => null)
if (!preview?.ok) {
  console.error(`No site served at ${BASE}. Run: cd site && npm run build && npm run preview`)
  process.exit(2)
}

const results = { fold: {}, cost: {}, tools: {}, intro: {} }

// ---------------------------------------------------------------- screenshots
// One browser: a warm cache changes nothing about what the page looks like.
if (ONLY === 'all' || ONLY === 'shots') {
  say('=== capturing 28 screenshots (7 themes x light/dark x desktop/390) ===')
  const chrome = await launch({ port: 9351 })
  const page = await openPage(chrome.port)
  // Pin the palette so "light"/"dark" is the only thing varying across the set.
  await page.goto(url('money'), { waitMs: 1500 })
  for (const theme of THEMES) {
    for (const [vp, [w, h]] of Object.entries(VIEWPORTS)) {
      await page.viewport(w, h, vp === 'mobile')
      for (const mode of MODES) {
        await page.eval(`(() => { try { localStorage.setItem('compass:mode', ${JSON.stringify(mode)});
          localStorage.setItem('compass:theme', 'compass') } catch {} ; return 1 })()`)
        await page.goto(url(theme), { waitMs: 3200 })
        // Scroll to the bottom and back before capturing. Both bottom panels
        // sit behind DeferUntilVisible, so a full-page capture taken without
        // scrolling shows two large EMPTY reserved boxes — an artefact of the
        // capture, not of the page, and the owner reads these screenshots.
        await page.eval(`(async () => {
          for (let i = 0; i < 3; i++) {
            window.scrollTo(0, document.documentElement.scrollHeight)
            await new Promise((r) => setTimeout(r, 1400))
          }
          window.scrollTo(0, 0)
          await new Promise((r) => setTimeout(r, 700))
          return 1
        })()`, { awaitPromise: true })
        await page.shot(`${SHOTS}p28-explore-${theme}-${vp}-${mode}.png`, { fullPage: true })
      }
      say(`  ${theme}/${vp} (light+dark)`)
    }
  }
  chrome.close()
}

// ------------------------------------------------- fold + cost, on a cold cache
// Mode is left unset on purpose: with no stored value the app falls back to
// prefers-color-scheme, which headless Chrome reports as light — so no
// localStorage write is needed, and the very first load of this browser is the
// measured one.
say('\n=== measuring fold + cost (fresh browser per theme, cold cache) ===')
let port = 9360
for (const theme of THEMES) {
  for (const [vp, [w, h]] of Object.entries(VIEWPORTS)) {
    const chrome = await launch({ port: port++ })
    const page = await openPage(chrome.port)
    await page.viewport(w, h, vp === 'mobile')
    await page.goto(url(theme), { waitMs: 4000 })

    // 2 — how far down is the first real answer? `/work`'s own defect (its h1
    // rendering fourth) was found by measuring exactly this.
    const fold = JSON.parse(await page.eval(`(() => {
      const y = (el) => el ? Math.round(el.getBoundingClientRect().top + window.scrollY) : null
      const heroVal = document.querySelector('.hero .hstat .v')
      // Any leaf node carrying a digit, not just text/.big/.tnum — the
      // narrower selector found nothing on five of seven themes at 390px,
      // which measured the selector rather than the page.
      const panelNum = [...document.querySelectorAll('.egrid .panel *')]
        .find((n) => n.children.length === 0 && /[0-9]/.test(n.textContent || ''))

      // Does anything fail to fit 390px? Objective, and one of the things
      // Tier 2 is allowed to fix without asking. Reported as the elements
      // that overflow their own box horizontally, with what they are.
      const overflow = [...document.querySelectorAll('.egrid .panel, .egrid .panel *')]
        .filter((el) => el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0)
        .slice(0, 12)
        .map((el) => ({
          tag: el.tagName.toLowerCase(),
          cls: (el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className || '').toString().slice(0, 40),
          scrollW: el.scrollWidth,
          clientW: el.clientWidth,
          text: (el.textContent || '').trim().slice(0, 50),
        }))

      return JSON.stringify({
        vh: window.innerHeight,
        h1Top: y(document.querySelector('h1.pg')),
        introTop: y(document.querySelector('p.oneline')),
        heroTop: y(heroVal),
        heroText: heroVal ? heroVal.textContent.trim() : null,
        firstPanelTop: y(document.querySelector('.egrid .panel')),
        firstPanelNumTop: y(panelNum),
        firstPanelNumText: panelNum ? (panelNum.textContent || '').trim().slice(0, 24) : null,
        docHeight: Math.round(document.documentElement.scrollHeight),
        docScrollW: Math.round(document.documentElement.scrollWidth),
        docClientW: Math.round(document.documentElement.clientWidth),
        pageOverflows: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        overflow,
        panels: document.querySelectorAll('.egrid .panel').length,
        prose: document.querySelectorAll('.egrid .panel .sub').length,
      })
    })()`))
    ;(results.fold[theme] ??= {})[vp] = fold

    // 3 — what does the theme cost, measured BEFORE scrolling so the deferred
    // tools are excluded: this is what a visitor pays for the theme they
    // actually opened. encodedBodySize is reported alongside transferSize so
    // the weight is readable even where a response was served from cache.
    const cost = JSON.parse(await page.eval(`(() => {
      const res = performance.getEntriesByType('resource')
      const nav = performance.getEntriesByType('navigation')[0]
      const paint = performance.getEntriesByType('paint')
      const kb = (n) => +(n / 1024).toFixed(1)
      const sum = (f, k) => res.filter(f).reduce((a, r) => a + (r[k] || 0), 0)
      const isData = (r) => /\\/data\\//.test(r.name)
      return JSON.stringify({
        requests: res.length,
        totalKB: kb(sum(() => true, 'transferSize')),
        dataKB: kb(sum(isData, 'transferSize')),
        codeKB: kb(sum((r) => !isData(r), 'transferSize')),
        coreKB: kb(sum((r) => /core\\.json/.test(r.name), 'transferSize')),
        wireKB: kb(sum(() => true, 'encodedBodySize')),
        fcpMs: Math.round(paint.find((p) => p.name === 'first-contentful-paint')?.startTime ?? -1),
        domContentLoadedMs: nav ? Math.round(nav.domContentLoadedEventEnd) : -1,
        dataFiles: res.filter(isData)
          .map((r) => r.name.split('/').pop() + ' ' + Math.round((r.encodedBodySize || 0) / 1024) + 'KB')
          .sort(),
      })
    })()`))
    ;(results.cost[theme] ??= {})[vp] = cost

    if (vp === 'desktop') {
      // 5 — does the one-line INTRO duplicate what the hero already states?
      results.intro[theme] = JSON.parse(await page.eval(`(() => {
        const one = document.querySelector('p.oneline')
        return JSON.stringify({
          intro: one ? one.textContent.trim() : null,
          introLen: one ? one.textContent.trim().length : 0,
          stats: [...document.querySelectorAll('.hero .hstat')].map((s) => ({
            v: s.querySelector('.v')?.textContent?.trim(),
            l: s.querySelector('.l')?.textContent?.trim(),
            s: s.querySelector('.s')?.textContent?.trim(),
          })),
        })
      })()`))

      // 4 — ScatterBuilder and WeightsTool render on every theme regardless of
      // relevance (Explore.tsx:88-94). Both sit behind DeferUntilVisible, so
      // scrolling to the bottom is what actually mounts them; the delta against
      // the pre-scroll numbers above is their true cost. Matched on their exact
      // headings: a looser regex read "Weigh things yourself" as absent, because
      // "Weigh" does not contain "weight".
      const tools = JSON.parse(await page.eval(`(async () => {
        for (let i = 0; i < 4; i++) {
          window.scrollTo(0, document.documentElement.scrollHeight)
          await new Promise((r) => setTimeout(r, 2000))
        }
        const res = performance.getEntriesByType('resource')
        const kb = (n) => +(n / 1024).toFixed(1)
        const panels = [...document.querySelectorAll('.panel')]
        const byTitle = (t) => panels.find((p) => (p.querySelector('h2')?.textContent || '').trim() === t)
        const scatter = byTitle('Ask your own question')
        const weights = byTitle('Weigh things yourself')
        const h = (el) => el ? Math.round(el.getBoundingClientRect().height) : null
        // What the builder is PRESET to on this theme — the question is whether
        // the theme feeds it at all, not merely whether it renders.
        const sel = scatter ? [...scatter.querySelectorAll('select')] : []
        return JSON.stringify({
          requestsAfter: res.length,
          totalKBAfter: kb(res.reduce((a, r) => a + (r.transferSize || 0), 0)),
          scatterTitle: scatter?.querySelector('h2')?.textContent?.trim() ?? null,
          weightsTitle: weights?.querySelector('h2')?.textContent?.trim() ?? null,
          scatterHeight: h(scatter),
          weightsHeight: h(weights),
          axisPreset: sel.map((s) => s.options[s.selectedIndex]?.text?.trim() ?? null),
          axisOptionCounts: sel.map((s) => s.options.length),
          docHeight: Math.round(document.documentElement.scrollHeight),
          mountedFiles: res.filter((r) => r.startTime > 3000)
            .map((r) => r.name.split('/').pop() + ' ' + Math.round((r.encodedBodySize || 0) / 1024) + 'KB'),
        })
      })()`, { awaitPromise: true }))
      results.tools[theme] = {
        ...tools,
        addedRequests: tools.requestsAfter - cost.requests,
        addedKB: +(tools.totalKBAfter - cost.totalKB).toFixed(1),
        heightWithoutTools: fold.docHeight,
      }
    }

    chrome.close()
    say(`  ${theme}/${vp}`)
  }
}

writeFileSync(SHOTS + 'p28-explore-measurements.json', JSON.stringify(results, null, 2))

// -------------------------------------------------------------------- report
say('\n=== 2 · how far down is the first real answer? (px from document top) ===')
say('theme      vp       vh    h1    hero#  where          1st panel #  doc height  panels  prose')
for (const t of THEMES) for (const vp of ['desktop', 'mobile']) {
  const f = results.fold[t][vp]
  const where = f.heroTop == null ? 'NO HERO' : f.heroTop < f.vh ? 'above fold' : 'BELOW FOLD'
  say(`${t.padEnd(10)} ${vp.padEnd(8)} ${String(f.vh).padEnd(5)} ${String(f.h1Top).padEnd(5)} `
    + `${String(f.heroTop).padEnd(6)} ${where.padEnd(14)} ${String(f.firstPanelNumTop).padEnd(12)} `
    + `${String(f.docHeight).padEnd(11)} ${String(f.panels).padEnd(7)} ${f.prose}`)
}

say('\n=== 3 · what does each theme cost? (cold cache, before the tools mount) ===')
say('theme      vp       reqs  total KB  data KB  core KB  wire KB  FCP ms  DCL ms')
for (const t of THEMES) for (const vp of ['desktop', 'mobile']) {
  const c = results.cost[t][vp]
  say(`${t.padEnd(10)} ${vp.padEnd(8)} ${String(c.requests).padEnd(5)} ${String(c.totalKB).padEnd(9)} `
    + `${String(c.dataKB).padEnd(8)} ${String(c.coreKB).padEnd(8)} ${String(c.wireKB).padEnd(8)} `
    + `${String(c.fcpMs).padEnd(7)} ${c.domContentLoadedMs}`)
}
say('\n  data files pulled per theme (desktop):')
for (const t of THEMES) say(`   ${t.padEnd(10)} ${results.cost[t].desktop.dataFiles.join(' · ') || '(none)'}`)

say('\n=== 4 · the two generic tools, on every theme ===')
say('theme      scatter panel                 weights panel            +reqs  +KB     height without / with')
for (const t of THEMES) {
  const x = results.tools[t]
  say(`${t.padEnd(10)} ${String(x.scatterTitle).slice(0, 28).padEnd(29)} ${String(x.weightsTitle).slice(0, 23).padEnd(24)} `
    + `${String(x.addedRequests).padEnd(6)} ${String(x.addedKB).padEnd(7)} ${x.heightWithoutTools} / ${x.docHeight}`)
}

say('\n=== 5 · INTRO line vs what the hero already says ===')
for (const t of THEMES) {
  const i = results.intro[t]
  say(`\n  ${t} — intro is ${i.introLen} chars`)
  say(`    intro: ${i.intro}`)
  for (const s of i.stats) say(`    hero:  ${s.v} — ${s.l}${s.s ? ' — ' + s.s : ''}`)
}

say(`\nwrote ${SHOTS}p28-explore-measurements.json`)
say(`wrote 28 screenshots to ${SHOTS}p28-explore-*.png`)
