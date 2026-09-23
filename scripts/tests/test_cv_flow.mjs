/* F1 — the CV flow is reachable end to end, at every width.
 *
 * Package 46, Tier 1. The CV panel opened to `max-height: 600px`. Reading a
 * CV adds a review step, a result and package 45's storage consent to that
 * same box, so the consent — the one thing that must be seen before anything
 * is kept — was in the part most likely to be cut off. This walks the whole
 * flow as a reader would and asks, at each step, whether every control is on
 * screen and answers a real click.
 *
 * WHAT IS REAL AND WHAT IS STUBBED, stated so nobody mistakes this for a
 * test of the network path:
 *
 *   real     the PDF (built below, synthetic, no real person in it), text
 *            extraction by pdf.js, PII stripping, the review step, every
 *            click, every layout.
 *   stubbed  the Turnstile widget (it would need Cloudflare's script and a
 *            human), /analyse (it would spend the owner's Gemini quota), and
 *            /profile (the vault Worker is not deployed — package 45 had no
 *            credentials to deploy it, and this package is told not to).
 *
 * The stubs answer with shapes copied from the Worker's own responses, so
 * the UI renders exactly the states a real run would reach.
 *
 * CLICKS ARE MOUSE EVENTS AT SCREEN COORDINATES (Input.dispatchMouseEvent),
 * not el.click(). el.click() works on an element that is clipped, covered or
 * off screen; a reader's click does not. That difference is the whole point.
 *
 *   node scripts/tests/test_cv_flow.mjs [--shots <dir>]   (preview on :4173)
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { launch, openPage } from './cdp.mjs'

const BASE = process.env.BASE ?? 'http://localhost:4173/'
const SHOTS = (() => { const i = process.argv.indexOf('--shots'); return i > 0 ? process.argv[i + 1] : null })()
const TAG = process.env.F1_TAG ?? 'after'
if (SHOTS) mkdirSync(SHOTS, { recursive: true })

let fails = 0
const say = (s = '') => console.log(s)
const check = (ok, label) => { say(`${ok ? 'PASS' : 'FAIL'}  ${label}`); if (!ok) fails++ }

/* A one-page PDF, hand-assembled so pdf.js has real text to extract. The
 * person is invented; the contact details are reserved example values. */
function syntheticCvPdf() {
  const lines = [
    'Sam Placeholder',
    'sam.placeholder@example.com   +45 00 00 00 00',
    '',
    'EXPERIENCE',
    'Senior Software Engineer, Example Systems A/S, 2019 - 2024',
    '  Built and ran backend services in Go and Python.',
    'Software Developer, Sample Labs Ltd, 2015 - 2019',
    '  Web applications in TypeScript and React.',
    '',
    'EDUCATION',
    'MSc Computer Science, Example University, 2015',
    '',
    'SKILLS',
    'Go, Python, TypeScript, PostgreSQL, Kubernetes',
  ]
  const esc = (t) => t.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)')
  let stream = 'BT /F1 11 Tf 56 780 Td 15 TL\n'
  for (const l of lines) stream += `(${esc(l)}) Tj T*\n`
  stream += 'ET'
  const objs = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${Buffer.byteLength(stream, 'latin1')} >>\nstream\n${stream}\nendstream`,
  ]
  let out = '%PDF-1.4\n'
  const offsets = []
  objs.forEach((o, i) => { offsets.push(Buffer.byteLength(out, 'latin1')); out += `${i + 1} 0 obj\n${o}\nendobj\n` })
  const xref = Buffer.byteLength(out, 'latin1')
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`
  for (const off of offsets) out += `${String(off).padStart(10, '0')} 00000 n \n`
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
  return Buffer.from(out, 'latin1')
}
const PDF_PATH = join(tmpdir(), 'compass-synthetic-cv.pdf')
writeFileSync(PDF_PATH, syntheticCvPdf())

/* Installed before the app's own code runs. */
const STUBS = `(() => {
  window.__f1 = { analyse: 0, saves: 0 }
  window.turnstile = {
    render(container, opts) {
      const box = document.createElement('div')
      box.setAttribute('data-f1', 'turnstile')
      box.style.cssText = 'width:300px;height:65px;border:1px solid #999;display:flex;align-items:center;justify-content:center;font:12px sans-serif;background:#f4f4f4'
      const b = document.createElement('button')
      b.type = 'button'; b.textContent = 'Verify (stub)'; b.setAttribute('data-f1', 'verify')
      b.addEventListener('click', () => opts.callback('stub-token'))
      box.appendChild(b); container.appendChild(box)
      return 'w1'
    },
    reset() {}, remove() {},
  }
  const real = window.fetch.bind(window)
  const json = (body) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } }))
  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || String(input)
    const method = ((init && init.method) || 'GET').toUpperCase()
    if (url.endsWith('/analyse')) {
      window.__f1.analyse++
      return json({ ok: true, modelUsed: 'stub (no model was called)', dailyUsage: { count: 1, limit: 1000 },
        profile: { status: 'ok',
          occupation: { isco08: '2512', confidence: 'high', evidence: 'Two roles titled software engineer or developer' },
          years_professional: 9, years_evidence: 'Continuous roles from 2015 to 2024',
          education_level: 'master' } })
    }
    if (url.endsWith('/profile')) {
      if (method === 'POST') {
        window.__f1.saves++
        const now = Date.now()
        return json({ ok: true, retentionDays: 30,
          record: { occupation: 'isco08:2512', yearsProfessional: 9, savedAt: now, expiresAt: now + 30 * 86400000 } })
      }
      if (method === 'DELETE') return json({ ok: true, had: true, gone: true })
      return json({ ok: true, record: null })
    }
    return real(input, init)
  }
})()`

/* Page-side: is this element on screen and the top thing at its centre?
 * `sel` is a CSS selector, or — prefixed with `=` — an expression that
 * returns the element, for one that is best found by what it says. */
const ONSCREEN = (sel) => `(() => {
  const el = ${sel.startsWith('=') ? sel.slice(1) : `document.querySelector(${JSON.stringify(sel)})`}
  if (!el) return JSON.stringify({ present: false })
  el.scrollIntoView({ block: 'center' })
  const r = el.getBoundingClientRect()
  const x = r.left + r.width / 2, y = r.top + r.height / 2
  const hit = document.elementFromPoint(x, y)
  const inView = r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth
  return JSON.stringify({ present: true, inView, top: hit === el || el.contains(hit) || (hit && hit.contains(el) && hit.tagName === 'LABEL'),
    hit: hit ? hit.tagName.toLowerCase() + '.' + String(hit.getAttribute('class') || '') : null,
    x: Math.round(x), y: Math.round(y), w: Math.round(r.width), h: Math.round(r.height) })
})()`

const { port, close } = await launch({ port: 9841 })
let page
const results = []
try {
  page = await openPage(port)
  await page.emulateReducedMotion(true)
  await page.send('Page.addScriptToEvaluateOnNewDocument', { source: STUBS })

  /* A real mouse click at the element's centre. If the element is clipped or
   * covered, this lands on whatever IS there — which is the failure. */
  const mouseClick = async (sel, label) => {
    const at = JSON.parse(await page.eval(ONSCREEN(sel)))
    if (!at.present) { check(false, `${label}: present`); return false }
    const ok = at.inView && at.top
    check(ok, `${label}: on screen and on top at its centre (${at.w}x${at.h} at ${at.x},${at.y}${ok ? '' : `; hit ${at.hit}`})`)
    if (!ok) return false
    for (const type of ['mousePressed', 'mouseReleased']) {
      await page.send('Input.dispatchMouseEvent', { type, x: at.x, y: at.y, button: 'left', clickCount: 1 })
    }
    await page.waitForReady({ quietMs: 250, timeoutMs: 30000, label })
    return true
  }
  const visible = async (sel, label) => {
    const at = JSON.parse(await page.eval(ONSCREEN(sel)))
    const ok = at.present && at.inView && at.top
    check(ok, `${label}: visible (${at.present ? `${at.w}x${at.h}` : 'absent'}${ok || !at.present ? '' : `; hit ${at.hit}`})`)
    return ok
  }
  const shot = async (w, step) => {
    if (!SHOTS) return
    await page.eval(`(() => { const p = document.querySelector('.profline'); if (p) p.scrollIntoView({ block: 'start' }); window.scrollBy(0, -70); return 1 })()`)
    await page.waitForReady({ quietMs: 200, timeoutMs: 20000, label: 'shot' })
    await page.shot(join(SHOTS, `cv-flow-${w}-${step}.${TAG}.png`))
  }
  const panelFits = async (w, step) => {
    const m = JSON.parse(await page.eval(`(() => {
      const b = document.getElementById('profline-body')
      return JSON.stringify({ sh: b.scrollHeight, ch: b.clientHeight,
        open: document.querySelector('button.profline-head').getAttribute('aria-expanded') })
    })()`))
    check(m.open === 'true' && m.sh <= m.ch + 1, `@${w} ${step}: the panel is open and its content fits it (${m.sh}px in ${m.ch}px)`)
  }

  for (const [w, h, mobile] of [[390, 844, true], [1024, 768, false], [1440, 900, false]]) {
    say('')
    say(`=== F1 @ ${w}px ===`)
    /* Each width is its own walk. A flow that is blocked at one width — a
     * button a reader cannot reach — is a FAIL at that step, and the next
     * width still runs; the first version of this file threw at 390 on the
     * original code and never reported 1024 or 1440. */
    try {
    await page.viewport(w, h, mobile)
    await page.goto('about:blank')
    await page.goto(BASE)
    await page.hashGo(`${BASE}#/work`)
    await page.waitForReady({ quietMs: 400, timeoutMs: 60000, label: 'work' })
    await page.eval(`(() => { try { localStorage.removeItem('compass:vault-key') } catch {} return 1 })()`)

    // 1 · open the panel
    await mouseClick('button.profline-head', `@${w} open the CV panel`)
    /* Open means OPEN ON SCREEN, not just aria-expanded: a run against the
     * original code once read the attribute as true while the panel body was
     * still 0px tall, and reported the idle state as "708px in 0px". */
    await page.waitFor(`document.querySelector('button.profline-head').getAttribute('aria-expanded') === 'true'
      && document.getElementById('profline-body').clientHeight > 40`, { timeoutMs: 5000, label: 'panel visibly open' })
    await page.waitForReady({ quietMs: 250, timeoutMs: 20000, label: 'panel open' })
    await visible('#profline-body input[type=file]', `@${w} the file picker`)
    await panelFits(w, 'idle')
    await shot(w, '1-idle')

    // 2 · a real PDF through real extraction
    const doc = await page.send('DOM.getDocument', { depth: -1, pierce: true })
    const { nodeId } = await page.send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: '#profline-body input[type=file]' })
    await page.send('DOM.setFileInputFiles', { files: [PDF_PATH], nodeId })
    await page.waitFor(`!!document.querySelector('#profline-body textarea')`, { timeoutMs: 20000, label: 'review step' })
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'review' })
    const reviewText = await page.eval(`document.querySelector('#profline-body textarea').value`)
    check(/Software Engineer/.test(reviewText) && !/example\.com/.test(reviewText),
      `@${w} review: the extracted text is there and the email was stripped before review`)
    await visible('#profline-body textarea', `@${w} review: the text to be sent`)
    await panelFits(w, 'review')
    await shot(w, '2-review')

    // 3 · send, pass the (stub) check
    const sendSel = '#profline-body button.btn-accent'
    await mouseClick(sendSel, `@${w} review: the send button`)
    await page.waitFor(`!!document.querySelector('[data-f1="verify"]')`, { timeoutMs: 10000, label: 'human check' })
    await panelFits(w, 'human check')
    await shot(w, '3-check')
    await mouseClick('[data-f1="verify"]', `@${w} the human check`)
    await page.waitFor(`!!document.querySelector('#profline-body input[type=checkbox]')`, { timeoutMs: 15000, label: 'result' })
    await page.waitForReady({ quietMs: 300, timeoutMs: 30000, label: 'result' })

    // 4 · the result, and the consent that must be seen before anything is kept
    const consentUnticked = await page.eval(`document.querySelector('#profline-body input[type=checkbox]').checked === false`)
    check(consentUnticked, `@${w} result: the storage consent starts unticked`)
    await visible('#profline-body label:has(input[type=checkbox])', `@${w} result: the storage consent, whole`)
    await panelFits(w, 'result')
    await shot(w, '4-result')

    // 5 · tick it — with a real click on the box
    await mouseClick('#profline-body input[type=checkbox]', `@${w} result: the consent checkbox`)
    const ticked = await page.eval(`document.querySelector('#profline-body input[type=checkbox]').checked === true`)
    check(ticked, `@${w} consent: a click on the box ticked it`)
    await shot(w, '5-consent')

    // 6 · apply and keep
    const applySel = '#profline-body button.btn-accent'
    await mouseClick(applySel, `@${w} consent: the apply-and-keep button`)
    await page.waitFor(`[...document.querySelectorAll('#profline-body .chip')].some((c) => (c.textContent || '').includes('deletes itself on'))`, { timeoutMs: 10000, label: 'saved chip' })
    const saves = await page.eval('window.__f1.saves')
    check(saves === 1, `@${w} apply: exactly one save was sent (${saves})`)
    await visible(`=[...document.querySelectorAll('#profline-body .chip')].find((c) => (c.textContent || '').includes('deletes itself on'))`,
      `@${w} saved: the confirmation that says when it deletes itself`)
    await panelFits(w, 'saved')
    await shot(w, '6-saved')
    results.push({ w, saves })
    } catch (e) {
      check(false, `@${w} the flow could not be completed: ${String(e.message).split('\n')[0]}`)
      await shot(w, 'blocked')
    }
  }
} finally {
  try { page?.close() } catch { /* already closed */ }
  close()
}

say('')
say('-'.repeat(70))
say(fails === 0 ? 'ALL CV-FLOW CHECKS PASS (F1)' : `${fails} check(s) FAILED`)
process.exitCode = fails ? 1 : 0
