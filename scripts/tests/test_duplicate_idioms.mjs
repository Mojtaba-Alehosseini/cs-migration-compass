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
 *      importing it. Detected by signature: each idiom lists the declarations
 *      its owning class already makes, and an inline style that repeats enough
 *      of them is reproducing it. Not a heuristic about names — a count of the
 *      same decisions written in a second place.
 *
 *   B. CSS RULES that duplicate another rule's intent under a different
 *      selector: the same declaration set, written twice, where one will be
 *      updated and the other will not.
 *
 * Run:  node scripts/tests/test_duplicate_idioms.mjs
 * It reads source only — no browser, no build, no served site.
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

/** Every `style={{ ... }}` block in a file, with balanced braces so a nested
 *  object or a template literal does not end the block early. */
function inlineStyles(src) {
  const out = []
  const re = /style=\{\{/g
  let m
  while ((m = re.exec(src))) {
    let depth = 2
    let i = m.index + m[0].length
    for (; i < src.length && depth > 0; i++) {
      if (src[i] === '{') depth++
      else if (src[i] === '}') depth--
    }
    out.push({ start: m.index, text: src.slice(m.index, i) })
  }
  return out
}

const lineOf = (src, idx) => src.slice(0, idx).split('\n').length

/* ---------------------------------------------------------------- A --- */

/** An idiom this site owns in ONE place, and the marks of it being rebuilt
 *  somewhere else. `signature` entries are strings that appear in an inline
 *  style when someone is reproducing the owner's own declarations. */
const IDIOMS = [
  {
    name: 'the selection tray',
    owner: 'components/SelectionTray.tsx (.tray in base.css)',
    signature: ["var(--z-tray)", "'var(--ink-1)'", "position: 'fixed'", 'var(--shadow-lg)', "'92vw'"],
    threshold: 3,
    // The component itself, and nothing else.
    allow: [join('components', 'SelectionTray.tsx')],
  },
  {
    name: 'a chip',
    owner: '.chip / .chip-ok / .chip-risk / .chip-note / .chip-quiet in base.css',
    signature: ["borderRadius: 'var(--radius-xl)'", "fontSize: 'var(--text-2xs)'", "padding: '4px 10px'", "padding: '5px 12px'"],
    threshold: 3,
    allow: [],
  },
  {
    name: 'a panel',
    owner: '.panel in base.css',
    signature: ["'var(--surface-raised)'", "'1px solid var(--line)'", "borderRadius: 'var(--radius-lg)'"],
    threshold: 3,
    allow: [],
  },
]

say('=== A: markup that rebuilds a shared idiom instead of importing it ===')
const files = walk(SRC)
let rebuilt = 0
for (const idiom of IDIOMS) {
  for (const file of files) {
    const rel = relative(SRC, file)
    if (idiom.allow.some((a) => rel.endsWith(a))) continue
    const src = readFileSync(file, 'utf8')
    for (const block of inlineStyles(src)) {
      const hits = idiom.signature.filter((s) => block.text.includes(s))
      if (hits.length >= idiom.threshold) {
        rebuilt++
        say(`    ${rel}:${lineOf(src, block.start)} rebuilds ${idiom.name}`)
        say(`      owner: ${idiom.owner}`)
        say(`      repeats ${hits.length} of its declarations: ${hits.join(', ')}`)
      }
    }
  }
}
check(rebuilt === 0, `no shared idiom is rebuilt inline (${rebuilt} found)`)

/* ---------------------------------------------------------------- B --- */

say('')
say('=== B: CSS rules that duplicate another rule\'s declaration set ===')

const css = readFileSync(join(SRC, 'styles/base.css'), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '')          // comments carry no declarations
const rules = []
{
  // Top-level rules only: a declaration block inside @media belongs to that
  // query and is not the same rule written twice.
  let depth = 0, buf = '', selector = ''
  for (let i = 0; i < css.length; i++) {
    const c = css[i]
    if (c === '{') {
      depth++
      if (depth === 1) { selector = buf.trim(); buf = '' } else buf += c
      continue
    }
    if (c === '}') {
      depth--
      if (depth === 0) {
        if (selector && !selector.startsWith('@')) rules.push({ selector, body: buf })
        buf = ''; selector = ''
      } else buf += c
      continue
    }
    buf += c
  }
}
const norm = (body) => body.split(';').map((d) => d.trim().replace(/\s+/g, ' ')).filter(Boolean).sort().join('; ')
const byDecls = new Map()
for (const r of rules) {
  const key = norm(r.body)
  if (key.split(';').length < 3) continue      // one or two declarations repeat innocently
  if (!byDecls.has(key)) byDecls.set(key, [])
  byDecls.get(key).push(r.selector)
}
let dupes = 0
for (const [key, selectors] of byDecls) {
  if (selectors.length < 2) continue
  dupes++
  say(`    ${selectors.join('  ==  ')}`)
  say(`      identical declarations: ${key.slice(0, 150)}`)
}
check(dupes === 0, `no CSS rule duplicates another rule's declaration set (${dupes} found)`)

say('')
say('-'.repeat(70))
say(fails === 0
  ? `DUPLICATE-IDIOM CHECK PASSES (${files.length} source files, ${rules.length} CSS rules)`
  : `${fails} check(s) FAILED`)
process.exitCode = fails ? 1 : 0
