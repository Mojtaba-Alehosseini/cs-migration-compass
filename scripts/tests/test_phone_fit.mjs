/* P1–P2 — the site header is one row, and Home is never wider than a phone.
 *
 * Package 46, Tier 4. Both were invisible at the widths anyone was looking
 * at, and both are properties a later change can quietly break again, so
 * they are checked as properties — rows and widths — not as pixel counts.
 *
 * P1  The header is ONE row at every width from 360 up, in all four themes,
 *     and its focus order is its visual order (NEEDS-DECISION #77 declined a
 *     reorder for exactly that reason). It was two rows on every phone and at
 *     561–630px: the theme controls wrapped under the nav. They live in the
 *     footer now, and the footer's order is checked too. The theme button's
 *     name says what it is ("Theme: …"), not just the theme's name — which
 *     was "Compass", beside a wordmark that also said "Compass".
 *
 * P2  Home's page is never wider than the screen, on any question:
 *     · WHILE LOADING, with motion on. The dot field's first render used a
 *       1000px fallback width, and the dots' 750ms transition started from
 *       there — at 390 the layout viewport grew to 827px until they landed.
 *     · After landing on "Time to PR & citizenship?" and switching to a dot
 *       question. The width hook measured once, on mount, and that question
 *       mounts no dot field — so the field stayed 1000px wide for good.
 *     · On "Time to PR & citizenship?" itself, whose bars drew 29px a year
 *       whatever the width and ran to 863px.
 *     Widths are read from the browser (innerWidth, scrollWidth) in MOBILE
 *     emulation, where an overflowing page widens the layout viewport the
 *     way a phone's does — the desktop preset clips instead and hides it.
 *
 *   node scripts/tests/test_phone_fit.mjs        (preview on :4173; BASE= to override)
 */
import { launch, openPage } from './cdp.mjs'

const BASE = process.env.BASE ?? 'http://localhost:4173/'
let fails = 0
const say = (s = '') => console.log(s)
const check = (ok, label) => { say(`${ok ? 'PASS' : 'FAIL'}  ${label}`); if (!ok) fails++ }

const preview = await fetch(BASE).catch(() => null)
if (!preview?.ok) {
  console.error(`No site served at ${BASE}.`)
  console.error('Run:  cd site && npm run build && npm run preview')
  process.exit(2)
}

/* Rows by vertical OVERLAP, not by distinct tops: the header row is
 * align-items:center, so a 20px link and a 30px button on one row have
 * different tops. Counting tops reported three rows for a one-row header. */
const ROWS = `((els) => {
  const rs = els.map((e) => e.getBoundingClientRect()).filter((r) => r.width > 0).sort((a, b) => a.top - b.top)
  let rows = 0, bottom = -Infinity
  for (const r of rs) { if (r.top >= bottom - 1) { rows++; bottom = r.bottom } else bottom = Math.max(bottom, r.bottom) }
  return rows
})`
const ORDER = `((root) => {
  const f = [...root.querySelectorAll('a[href], button, input, select, [tabindex]:not([tabindex="-1"])')]
    .filter((e) => e.getBoundingClientRect().width > 0 && getComputedStyle(e).visibility !== 'hidden')
  const name = (e) => (e.getAttribute('aria-label') || e.textContent || '').replace(/\\s+/g, ' ').trim()
  const byVisual = [...f].sort((a, b) => { const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect()
    const sameRow = ra.top < rb.bottom - 1 && rb.top < ra.bottom - 1
    return sameRow ? ra.left - rb.left : ra.top - rb.top })
  return { n: f.length, match: f.every((e, i) => e === byVisual[i]), dom: f.map(name).join(' > '), visual: byVisual.map(name).join(' > ') }
})`
const settled = `(() => { requestAnimationFrame(() => {}); return document.getAnimations().length === 0 })()`

const { port, close } = await launch({ port: 9471 })
try {
  const page = await openPage(port)

  say('=== P1: the header is one row, and focus follows what the eye reads ===')
  for (const theme of ['compass', 'editorial', 'terminal', 'warm']) {
    await page.viewport(1024, 800, false)
    await page.goto('about:blank')
    await page.goto(BASE)
    // Origin first: localStorage on about:blank is a SecurityError.
    await page.eval(`localStorage.setItem('compass:theme', ${JSON.stringify(theme)}); 1`)
    for (const w of [360, 390, 414, 630, 768, 1440]) {
      await page.viewport(w, 800, w < 600)
      await page.goto('about:blank')
      await page.goto(BASE)
      await page.waitForReady({ quietMs: 300, timeoutMs: 60000, label: `header ${theme}@${w}` })
      const m = JSON.parse(await page.eval(`(() => {
        const header = document.querySelector('header'), inner = header.firstElementChild
        return JSON.stringify({ rows: ${ROWS}([...inner.children]), head: ${ORDER}(header), foot: ${ORDER}(document.querySelector('footer')),
          themeName: (() => { const b = [...document.querySelectorAll('footer button[aria-expanded]')][0]; return b ? b.textContent.replace(/\\s+/g, ' ').trim() : null })() })
      })()`))
      check(m.rows === 1, `P1 ${theme}@${w}: the header is ${m.rows} row(s)`)
      if (theme === 'compass') {
        check(m.head.match, `P1 @${w}: header focus order is its visual order (${m.head.dom})`)
        check(m.foot.match, `P1 @${w}: footer focus order is its visual order (${m.foot.dom})`)
        check(/^Theme: /.test(m.themeName ?? ''), `P1 @${w}: the theme button says what it is ("${m.themeName}")`)
      }
    }
  }
  await page.eval(`localStorage.setItem('compass:theme', 'compass'); 1`)

  say('')
  say('=== P2: Home is never wider than the screen ===')
  /* Every 20ms from the first script on, the widest the page has been. */
  await page.send('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.__widest = 0
    const t0 = performance.now()
    const rec = () => { if (document.querySelector('.swarm-stage')) window.__widest = Math.max(window.__widest, innerWidth, document.documentElement.scrollWidth) }
    const id = setInterval(rec, 20); setTimeout(() => clearInterval(id), 6000)
  ` })
  const QUESTIONS = [
    ['Who pays the most', 'pay'], ['buy a home', 'home'], ['left at the end', 'left'],
    ['Time to PR', 'stay'], ['sun shine', 'sun'],
  ]
  for (const w of [360, 390, 414, 768]) {
    await page.emulateReducedMotion(false)
    await page.viewport(w, 800, w < 600)
    await page.goto('about:blank')
    await page.goto(BASE)
    await page.waitForReady({ quietMs: 400, timeoutMs: 60000, label: `home@${w}` })
    await new Promise((r) => setTimeout(r, 2600)) // the intro (1.3s) and the settle after it
    const widest = await page.eval('window.__widest')
    check(widest > 0 && widest <= w, `P2 @${w}: while Home loads, with motion, the page is never wider than ${w}px (widest ${widest})`)

    await page.emulateReducedMotion(true)
    for (const [pill, id] of QUESTIONS) {
      await page.eval(`(() => { const b = [...document.querySelectorAll('button.pill')].find((x) => x.textContent.includes(${JSON.stringify(pill)})); b.click(); return 1 })()`)
      await page.waitForReady({ quietMs: 300, timeoutMs: 20000, label: `${id}@${w}` })
      await page.waitFor(settled, { timeoutMs: 10000, label: 'settled' })
      const sw = await page.eval(`Math.max(innerWidth, document.documentElement.scrollWidth)`)
      check(sw <= w, `P2 @${w}: on "${pill}…" the page is ${sw}px in a ${w}px screen`)
    }

    /* The path that kept the field at 1000px for good. */
    await page.goto('about:blank')
    await page.goto(`${BASE}#/?ask=stay`)
    await page.waitForReady({ quietMs: 300, timeoutMs: 60000, label: `stay@${w}` })
    await page.eval(`(() => { [...document.querySelectorAll('button.pill')].find((x) => x.textContent.includes('Who pays the most')).click(); return 1 })()`)
    await page.waitForReady({ quietMs: 300, timeoutMs: 20000, label: `stay->pay@${w}` })
    await page.waitFor(settled, { timeoutMs: 10000, label: 'settled' })
    const s = JSON.parse(await page.eval(`(() => {
      const field = document.querySelector('.swarm-stage div[style*="height"]'), fr = field.getBoundingClientRect()
      const dots = [...field.querySelectorAll(':scope > .swarm-dot')]
      return JSON.stringify({ dots: dots.length, beyond: dots.filter((d) => d.querySelector('.swarm-mark').getBoundingClientRect().right > fr.right + 1).length,
        sw: Math.max(innerWidth, document.documentElement.scrollWidth) })
    })()`))
    check(s.dots > 0 && s.beyond === 0 && s.sw <= w,
      `P2 @${w}: landing on "Time to PR" then switching draws ${s.dots} dots, ${s.beyond} past the field's edge, page ${s.sw}px`)
  }

  page.close()
} finally {
  close()
}

say('')
say('-'.repeat(70))
say(fails === 0 ? 'ALL PHONE-FIT CHECKS PASS (P1, P2)' : `${fails} check(s) FAILED`)
process.exitCode = fails ? 1 : 0
