/* Minimal Chrome DevTools Protocol driver — no npm dependencies.
 *
 * A tracked copy of .status/evidence/cdp.mjs (that directory is gitignored —
 * ad-hoc, per-package verification scratch space, never meant to be a real
 * dependency). test_ui_regressions.mjs is a PERMANENT regression suite, run
 * in CI against a fresh checkout where .status/ does not exist at all —
 * found live, package 13: CI's own first run of this suite failed with
 * ERR_MODULE_NOT_FOUND on the gitignored path, the exact bug this tracked
 * copy exists to fix. Keep the two in sync by hand if either changes; this
 * one is the one CI and any future permanent test actually depends on.
 *
 * Real screenshots come from a headless Chrome we launch and drive
 * ourselves — Node's own global WebSocket is the only thing CDP needs.
 */

import { spawn } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME = process.env.CHROME_PATH
  ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export async function launch({ port = 9333 } = {}) {
  // A stale Chrome from an earlier run (or another script) already listening
  // on this port answers /json/version too — the poll below can't tell it
  // apart from the instance spawned here, so it silently drives someone
  // else's browser (often one whose own --user-data-dir has since been
  // deleted, which just hangs on the next command). Fail fast instead;
  // callers that need a fresh instance should pass a port nothing is
  // listening on.
  try {
    const res = await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(500) })
    if (res.ok) throw new Error(`port ${port} is already answering CDP — pick a free port instead of reusing it`)
  } catch (e) {
    if (e instanceof Error && e.message.startsWith('port ')) throw e
    // fetch itself failing (connection refused / timeout) means the port is free — proceed.
  }

  const profile = mkdtempSync(join(tmpdir(), 'cdp-'))
  const child = spawn(CHROME, [
    '--headless=new',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--disable-background-networking',
    '--hide-scrollbars',
    '--force-device-scale-factor=1',
    '--force-color-profile=srgb',
    // A CI runner's own root/restricted-uid execution can fail to init
    // Chrome's sandbox with no other symptom than a silent, immediate exit
    // (no CDP port ever opens). Safe specifically because this drives only
    // pages this same job just built and served itself on localhost —
    // never an arbitrary or remote URL — the exact narrow case sandboxless
    // Chrome is an acceptable, common CI trade-off for.
    '--no-sandbox',
    'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'], detached: false })

  // Keep Chrome's own stderr. With stdio ignored the only symptom of a
  // missing binary, a broken shared library or a refused profile directory
  // was "did not expose a debugging port" — true, unactionable, and identical
  // for every cause. CI hit exactly that and the log said nothing else.
  let stderr = ''
  child.stderr?.on('data', (d) => { stderr += d.toString().slice(0, 2000) })
  let spawnErr = null
  child.on('error', (e) => { spawnErr = e })
  let exited = null
  child.on('exit', (code, signal) => { exited = signal ? `signal ${signal}` : `code ${code}` })

  // 30s, not 15. A cold Chrome start on a loaded CI runner is slow, and the
  // old budget (100 x 150ms) sat close enough to the real start time that a
  // busy runner failed the whole suite before a single check ran.
  let version = null
  for (let i = 0; i < 200; i++) {
    if (spawnErr || exited) break
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`)
      if (res.ok) { version = await res.json(); break }
    } catch { /* not up yet */ }
    await sleep(150)
  }
  if (!version) {
    const why = spawnErr ? `could not be started (${spawnErr.message})`
      : exited ? `exited early with ${exited}`
      : 'did not expose a debugging port within 30s'
    throw new Error(
      `headless Chrome ${why}\n  binary: ${CHROME}\n`
      + `  set CHROME_PATH to override\n`
      + (stderr ? `  chrome stderr:\n${stderr.split('\n').map((l) => `    ${l}`).join('\n')}` : ''))
  }

  return {
    port,
    close() {
      try { child.kill() } catch { /* already gone */ }
      setTimeout(() => { try { rmSync(profile, { recursive: true, force: true }) } catch { /* locked */ } }, 400)
    },
  }
}

/** One page, with the handful of CDP calls this project needs. */
export async function openPage(port) {
  const res = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })
  if (!res.ok) throw new Error(`could not open a target (HTTP ${res.status})`)
  const target = await res.json()

  const ws = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true })
    ws.addEventListener('error', reject, { once: true })
  })

  let id = 0
  const pending = new Map()
  const events = []
  /* In-flight requests, tracked so readiness can be a FACT rather than a
   * guess about how long a fetch takes. This is the signal package 30's
   * `/openings` failure needed and did not have: that route's 24 MiB fetch
   * is in flight for ~700ms while the page shell sits there looking settled,
   * and no amount of DOM-stability polling can tell "still loading" from
   * "finished, and this is all there is".
   *
   * Network events are deliberately NOT pushed into `events`: 108 pages of
   * request/response traffic is a lot of retained JSON for a list whose only
   * consumer is the console-error filter. */
  /* requestId -> started-at. A Map rather than a Set because a request that
   * never reports completion — a cancelled preload, a websocket, a connection
   * the server holds open — would otherwise pin the in-flight count above zero
   * for the rest of the session and turn every readiness wait into a timeout.
   * That would be this package's own mistake in miniature: replacing a wait
   * that silently measured less with one that loudly measures nothing. Entries
   * older than STALE_MS stop counting; they are a stuck request, not a page
   * still loading. */
  const STALE_MS = 10000
  const started = new Map()
  const inflight = {
    get size() {
      const cutoff = Date.now() - STALE_MS
      let n = 0
      for (const t of started.values()) if (t > cutoff) n++
      return n
    },
  }
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.id != null) {
      const p = pending.get(msg.id)
      pending.delete(msg.id)
      if (!p) return
      if (msg.error) p.reject(new Error(`${msg.error.message} (${JSON.stringify(msg.error.data ?? '')})`))
      else p.resolve(msg.result)
    } else if (msg.method === 'Network.requestWillBeSent') {
      started.set(msg.params.requestId, Date.now())
    } else if (msg.method === 'Network.loadingFinished' || msg.method === 'Network.loadingFailed') {
      started.delete(msg.params.requestId)
    } else {
      events.push(msg)
    }
  })

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const mid = ++id
      pending.set(mid, { resolve, reject })
      ws.send(JSON.stringify({ id: mid, method, params }))
    })

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Log.enable')
  await send('Network.enable')

  const page = {
    send,
    events,
    consoleErrors: () =>
      events
        .filter((e) => e.method === 'Log.entryAdded' && e.params.entry.level === 'error')
        .map((e) => e.params.entry.text),

    async viewport(width, height, mobile = false) {
      await send('Emulation.setDeviceMetricsOverride', {
        width, height, deviceScaleFactor: 1, mobile,
      })
    },

    async goto(url, { waitMs = 0 } = {}) {
      const loaded = new Promise((resolve) => {
        const onMsg = (ev) => {
          const m = JSON.parse(ev.data)
          if (m.method === 'Page.loadEventFired') { ws.removeEventListener('message', onMsg); resolve() }
        }
        ws.addEventListener('message', onMsg)
      })
      await send('Page.navigate', { url })
      await loaded
      if (waitMs) await sleep(waitMs)
    },

    /* Hash routing means most navigations never fire a load event, so goto()
     * would wait forever. This drives the SPA the way a link does — and keeps
     * the app's state, which is exactly what the selection gates need.
     *
     * `waitMs` now defaults to 0. It used to be 900, which is a guess about a
     * machine: too long on a laptop, too short on a loaded CI runner, and
     * wrong in a way that never failed — it just measured less. Callers wait
     * for `waitForReady()` instead. */
    async hashGo(url, { waitMs = 0 } = {}) {
      await send('Runtime.evaluate', { expression: `location.href = ${JSON.stringify(url)}` })
      if (waitMs) await sleep(waitMs)
    },

    /** How many network requests are in flight right now. */
    inflight: () => inflight.size,

    /**
     * Poll a page-side boolean expression until it is true.
     *
     * A timeout is an ERROR, never a shrug. The whole point of replacing fixed
     * waits is that "we waited and it never happened" must be louder than
     * "we waited and moved on", which is what a `sleep()` does by design.
     */
    async waitFor(expression, { timeoutMs = 15000, pollMs = 50, label = expression } = {}) {
      const t0 = Date.now()
      let lastErr = null
      for (;;) {
        try {
          if (await page.eval(`Boolean(${expression})`)) return Date.now() - t0
          lastErr = null
        } catch (e) { lastErr = e }
        if (Date.now() - t0 > timeoutMs) {
          throw new Error(`waitFor timed out after ${timeoutMs}ms: ${label}`
            + (lastErr ? `\n  last evaluation error: ${lastErr.message}` : ''))
        }
        await sleep(pollMs)
      }
    },

    /**
     * Wait until the page is genuinely ready: nothing in flight, and the DOM
     * has stopped changing — both continuously for `quietMs`.
     *
     * Network idle is what a DOM-stability check cannot substitute for. A page
     * whose data is still downloading has a perfectly stable DOM; that is the
     * exact state in which this suite captured `/openings` for six packages,
     * and no stability window fixes it, because the shell stays stable for the
     * whole duration of the fetch. Requiring both means the wait ends when the
     * page is finished, not when it has been quiet for long enough to look it.
     *
     * `also` is an optional page-side expression for a route that knows what
     * its own arrival looks like.
     */
    async waitForReady({ quietMs = 300, timeoutMs = 20000, also = null, label = 'page ready' } = {}) {
      const t0 = Date.now()
      let lastCount = -1
      let stableSince = 0
      let idleSince = 0
      for (;;) {
        const now = Date.now()
        if (inflight.size === 0) { if (!idleSince) idleSince = now } else { idleSince = 0 }

        const count = await page.eval('document.querySelectorAll("*").length')
        if (count !== lastCount) { lastCount = count; stableSince = 0 }
        else if (!stableSince) stableSince = now

        const complete = await page.eval('document.readyState === "complete"')
        const quiet = idleSince && stableSince
          && now - idleSince >= quietMs && now - stableSince >= quietMs
        if (complete && quiet && (!also || await page.eval(`Boolean(${also})`))) {
          return now - t0
        }
        if (now - t0 > timeoutMs) {
          throw new Error(`waitForReady timed out after ${timeoutMs}ms: ${label}\n`
            + `  in-flight requests: ${inflight.size}\n`
            + `  DOM nodes: ${count} (stable: ${stableSince ? `${now - stableSince}ms` : 'no'})\n`
            + (also ? `  extra condition never became true: ${also}\n` : ''))
        }
        await sleep(50)
      }
    },

    async eval(expression, { awaitPromise = false } = {}) {
      const r = await send('Runtime.evaluate', {
        expression, returnByValue: true, awaitPromise,
      })
      if (r.exceptionDetails) {
        throw new Error(`page threw: ${r.exceptionDetails.exception?.description ?? r.exceptionDetails.text}`)
      }
      return r.result.value
    },

    async shot(path, { fullPage = false } = {}) {
      const r = await send('Page.captureScreenshot', {
        format: 'png',
        captureBeyondViewport: fullPage,
      })
      const { writeFileSync } = await import('node:fs')
      writeFileSync(path, Buffer.from(r.data, 'base64'))
      return path
    },

    async emulateReducedMotion(on) {
      await send('Emulation.setEmulatedMedia', {
        features: [{ name: 'prefers-reduced-motion', value: on ? 'reduce' : 'no-preference' }],
      })
    },

    close() { try { ws.close() } catch { /* already closed */ } },
  }

  return page
}

export { sleep }
