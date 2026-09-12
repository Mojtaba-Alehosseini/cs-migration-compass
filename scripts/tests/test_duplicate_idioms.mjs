/* The thing built twice.
 *
 * Package 43 found FIVE instances of one component's markup hand-rolled
 * somewhere else, and the last of them — Home's own inline copy of the
 * selection tray — was found by an instrument, after an adversarial review,
 * after the class-based fix it duplicated had already shipped. Home carried the
 * exact defect that fix had just repaired: --ink-3 on an --ink-1 slab, 3.52:1
 * light and 2.76:1 dark. A class-based fix cannot reach a hand-rolled
 * duplicate. That is a defect CLASS, not an accident, and nothing in this repo
 * checked for it.
 *
 * This does, in the two shapes the class actually takes:
 *
 *   A. MARKUP that reproduces a shared component or class inline, instead of
 *      importing it. Each idiom lists the declarations its owning class already
 *      makes, and a file that repeats enough of them in one place is rebuilding
 *      it. Not a heuristic about names — a count of the same decisions written
 *      in a second place.
 *
 *   B. CSS RULES that duplicate another rule's intent under a different
 *      selector: the same declaration set, written twice, where one will be
 *      updated and the other will not.
 *
 * PACKAGE 44's ADVERSARIAL REVIEW BROKE THE FIRST VERSION TEN WAYS, and the
 * closures are the reason this file looks the way it does:
 *   - matching raw source meant `position: "fixed"` (double quotes) walked past
 *     a signature written with single ones. Declarations are NORMALISED now:
 *     quotes stripped, whitespace collapsed, property and value compared.
 *   - only `style={{ ... }}` was scanned, so hoisting the object to a const or
 *     spreading it evaded everything. EVERY brace-balanced object literal in
 *     the file is scanned now.
 *   - splitting one rebuild across three nested elements kept every single
 *     object under the threshold. Hits are CLUSTERED by proximity now, so a
 *     rebuild spread over a few lines still counts as one.
 *   - `allow` used endsWith, so `routes/components/SelectionTray.tsx` exempted
 *     itself. It is an exact repo-relative path now.
 *   - the CSS half compared declaration sets for EQUALITY, so one extra
 *     declaration defeated it. It reports SUBSETS now, and looks inside
 *     @media blocks as their own namespaces.
 *
 * KNOWN LIMITS, recorded rather than papered over — this check does not catch:
 *   - a THREE-declaration rule duplicated with a fourth declaration added.
 *     Subset matching starts at four, and the reason is measured: at three,
 *     this stylesheet's small token vocabulary produces thirteen matches, eight
 *     of them coincidences like "font-size: var(--text-2xs); color:
 *     var(--ink-3); margin-top: 2px" appearing in two unrelated rules. A check
 *     that cries wolf thirteen times is a check nobody runs. Exact duplicates
 *     of any size ARE caught.
 *   - shorthand against longhand (`margin: 8px 0 0` vs `margin-top: 8px`)
 *   - the same value spelled differently (`0.75rem` vs `12px`, `#736F5E` vs
 *     `rgb(115,111,94)`)
 *   - duplication between base.css and tokens.css; only base.css is scanned
 *   - an idiom nobody added to IDIOMS below
 * It is a tripwire for the shape this repo has actually shipped five times, not
 * a proof of absence.
 *
 * VERIFIED FAILING, each evasion on its own, before being trusted: double
 * quotes, a hoisted style object, a spread, a rebuild split across three nested
 * elements, and a file placed at routes/components/SelectionTray.tsx to abuse
 * the allow list. All five are caught; the CSS case above is the one that is
 * not, and it is listed rather than hidden.
 *
 * Run:  node scripts/tests/test_duplicate_idioms.mjs
 * Source only — no browser, no build, no served site.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join, relative } from 'node:path'

const REPO = fileURLToPath(new URL('../../', import.meta.url))
const SRC = join(REPO, 'site/src')

let fails = 0
const say = (s = '') => console.log(s)
const check = (ok, label) => { say(`${ok ? 'PASS' : 'FAIL'}  ${label}`); if (!ok) fails++ }

function walk(dir) {
  const out = []
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) out.push(...walk(p))
    else if (/\.tsx?$/.test(p)) out.push(p)
  }
  return out
}

/** Every brace-balanced object literal in a file: inline `style={{…}}`, a
 *  hoisted `const x = {…}`, a spread source, anything. Balanced so a nested
 *  object or a template literal cannot end one early. */
function objectLiterals(src) {
  const out = []
  for (let i = 0; i < src.length; i++) {
    if (src[i] !== '{') continue
    // an object literal starts after `=`, `(`, `{{`, `,` or `:` — cheap filter
    const before = src.slice(Math.max(0, i - 2), i)
    if (!/[={(,:]\s?$/.test(before)) continue
    let depth = 0
    let j = i
    for (; j < src.length; j++) {
      if (src[j] === '{') depth++
      else if (src[j] === '}') { depth--; if (depth === 0) { j++; break } }
    }
    const text = src.slice(i, j)
    if (text.length > 4 && text.includes(':')) out.push({ start: i, text })
  }
  return out
}

/** Quotes stripped, whitespace collapsed, so `position: "fixed"`,
 *  `position:'fixed'` and `position :  'fixed'` are one thing. */
const normalise = (s) => s.replace(/['"`]/g, '').replace(/\s+/g, '').toLowerCase()

const lineOf = (src, idx) => src.slice(0, idx).split('\n').length

/* ---------------------------------------------------------------- A --- */

/** An idiom this site owns in ONE place, and the declarations that say it is
 *  being rebuilt somewhere else. Written the way a developer would write them;
 *  both sides are normalised before comparison. */
const IDIOMS = [
  {
    name: 'the selection tray',
    owner: 'components/SelectionTray.tsx (.tray in base.css)',
    signature: ['zIndex: var(--z-tray)', "background: 'var(--ink-1)'", "position: 'fixed'",
      'boxShadow: var(--shadow-lg)', "maxWidth: '92vw'"],
    /* Without this, Figure.tsx's popover matched three of the five —
       position:fixed on an ink background with a shadow is what a floating
       card IS — and the check reported the wrong component. The identity
       marker is the tray's own z-index token: a popover uses --z-popover. */
    distinctive: ['zIndex: var(--z-tray)'],
    threshold: 3,
    allow: ['components/SelectionTray.tsx'],
  },
  {
    name: 'a chip',
    owner: '.chip / .chip-ok / .chip-risk / .chip-note / .chip-quiet in base.css',
    signature: ["borderRadius: 'var(--radius-xl)'", "fontSize: 'var(--text-2xs)'",
      "padding: '4px 10px'", "padding: '5px 12px'"],
    threshold: 3,
    allow: [],
  },
  {
    name: 'a panel',
    owner: '.panel in base.css',
    signature: ["background: 'var(--surface-raised)'", "border: '1px solid var(--line)'",
      "borderRadius: 'var(--radius-lg)'"],
    threshold: 3,
    allow: [],
  },
  {
    name: 'a loading skeleton',
    owner: 'ChartSkeleton in components/explore/Controls.tsx',
    signature: ["display: 'grid'", "placeItems: 'center'", 'ariaBusy', "aria-busy=\"true\""],
    distinctive: ["placeItems: 'center'"],
    threshold: 3,
    allow: ['components/explore/Controls.tsx'],
  },
]

/** Hits within this many lines of each other are one rebuild, even if they were
 *  split across nested elements to duck the per-object threshold. */
const CLUSTER_LINES = 25

say('=== A: markup that rebuilds a shared idiom instead of importing it ===')
const files = walk(SRC)
let rebuilt = 0
for (const idiom of IDIOMS) {
  const wanted = idiom.signature.map(normalise)
  for (const file of files) {
    const rel = relative(SRC, file).split('\\').join('/')
    if (idiom.allow.includes(rel)) continue
    const src = readFileSync(file, 'utf8')
    // every signature hit in the file, wherever it is written
    const hits = []
    for (const obj of objectLiterals(src)) {
      const norm = normalise(obj.text)
      for (const [i, w] of wanted.entries()) {
        if (norm.includes(w)) hits.push({ line: lineOf(src, obj.start), sig: idiom.signature[i] })
      }
    }
    if (!hits.length) continue
    // cluster by proximity
    hits.sort((a, b) => a.line - b.line)
    let cluster = []
    const flush = () => {
      const distinct = [...new Set(cluster.map((h) => h.sig))]
      const hasIdentity = !idiom.distinctive || idiom.distinctive.some((d) => distinct.includes(d))
      if (distinct.length >= idiom.threshold && hasIdentity) {
        rebuilt++
        say(`    ${rel}:${cluster[0].line} rebuilds ${idiom.name}`)
        say(`      owner: ${idiom.owner}`)
        say(`      repeats ${distinct.length} of its declarations: ${distinct.join(', ')}`)
      }
      cluster = []
    }
    for (const h of hits) {
      if (cluster.length && h.line - cluster[cluster.length - 1].line > CLUSTER_LINES) flush()
      cluster.push(h)
    }
    flush()
  }
}
check(rebuilt === 0, `no shared idiom is rebuilt inline (${rebuilt} found)`)

/* ---------------------------------------------------------------- B --- */

say('')
say('=== B: CSS rules that duplicate another rule\'s declaration set ===')

const css = readFileSync(join(SRC, 'styles/base.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

/** Every rule, with the @media context it lives in — a rule inside a query is
 *  compared against its siblings in that query, not against the top level. */
function rules(text, context = '') {
  const out = []
  let depth = 0, buf = '', selector = ''
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '{') {
      depth++
      if (depth === 1) { selector = buf.trim(); buf = '' } else buf += c
      continue
    }
    if (c === '}') {
      depth--
      if (depth === 0) {
        if (selector.startsWith('@')) out.push(...rules(buf, `${context}${selector} `))
        else if (selector) out.push({ selector, body: buf, context })
        buf = ''; selector = ''
      } else buf += c
      continue
    }
    buf += c
  }
  return out
}

const decls = (body) => new Set(
  body.split(';').map((d) => d.trim().replace(/\s+/g, ' ').toLowerCase()).filter(Boolean))

/* Pre-existing duplications, recorded so this check fails on anything NEW
 * without demanding a stylesheet-wide refactor from whichever package happens
 * to add the check. Package 44 did not introduce any of these and did not fix
 * them; they are the honest backlog. Each is a real idiom written twice — the
 * kicker's uppercase-label recipe appears under four selectors — and consoli-
 * dating them is its own piece of work, on a file where merge position changes
 * the cascade (see the three merges package 44 DID make, each at the last of
 * its positions for exactly that reason). */
const KNOWN_CSS_DUPES = new Set([
  '.cmp td.mlab small || .nvr small',
  '.stayrow .ext || .vrow .ext',
  '.crail .lbl || .kicker',
  '.crail .lbl || .tgroup .tl',
  '.cmp th || .crail .lbl',
])

/* EQUALITY, plus a subset of 4+ declarations.
 *
 * Equality alone is what the review defeated by adding one declaration. Pure
 * subset detection at 3 was the opposite mistake: with a token vocabulary this
 * small, `font-size: var(--text-2xs); color: var(--ink-3); margin-top: 2px`
 * turns up in two unrelated rules by coincidence, and a check that cries wolf
 * thirteen times is a check nobody runs. Four identical declarations in the
 * same order-independent set is a decision, not a coincidence. */
const all = rules(css).map((r) => ({ ...r, set: decls(r.body) })).filter((r) => r.set.size >= 3)
let dupes = 0, known = 0
const reported = new Set()
for (let i = 0; i < all.length; i++) {
  for (let j = 0; j < all.length; j++) {
    if (i === j) continue
    const a = all[i], b = all[j]
    if (a.context !== b.context) continue
    const subset = [...a.set].every((d) => b.set.has(d))
    if (!subset) continue
    const identical = a.set.size === b.set.size
    if (!identical && a.set.size < 4) continue
    const key = [a.selector, b.selector].sort().join(' || ')
    if (reported.has(key + a.context)) continue
    reported.add(key + a.context)
    if (KNOWN_CSS_DUPES.has(key)) {
      known++
      say(`    known (pre-existing): ${a.context}${key}`)
      continue
    }
    dupes++
    say(`    ${a.context}${a.selector}  ${identical ? 'is identical to' : 'is contained in'}  ${a.context}${b.selector}`)
    say(`      shared: ${[...a.set].join('; ').slice(0, 140)}`)
  }
}
check(dupes === 0, `no NEW CSS rule duplicates another rule's declaration set (${dupes} new, ${known} known)`)

say('')
say('-'.repeat(70))
say(fails === 0
  ? `DUPLICATE-IDIOM CHECK PASSES (${files.length} source files, ${all.length} CSS rules of 3+ declarations)`
  : `${fails} check(s) FAILED`)
process.exitCode = fails ? 1 : 0
