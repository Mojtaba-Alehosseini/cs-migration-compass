/* A file this site names to a reader is a file the reader can open.
 *
 * NEEDS-DECISION #70 asked whether naming repository files in reader-facing
 * copy — `salary_es.json`, `build_postings.py`, `NEEDS-DECISION.md` — is the
 * voice this project wants. The ruling kept the names and removed what made
 * them unhelpful: they were strings you had to take on faith. Now each one is
 * a link into the public repository at a pinned commit.
 *
 * Three properties this file exists to hold:
 *
 *   The visible TEXT does not change. Splitting a sentence into runs and
 *   anchors leaves `.textContent` byte-identical, which is what C3b, C3's
 *   forbidden-key scan and the arithmetic-reproduction check all read. A
 *   change that made the copy read differently would have to be argued on its
 *   own merits; this one does not.
 *
 *   A token with no known path stays plain text. `compass-compare.csv` is a
 *   file the site GENERATES for the reader to download, not one in the
 *   repository, and there are eleven more like it. Linking those would be an
 *   invented promise; the map simply does not contain them.
 *
 *   Anchors only, no block elements. These sentences render inside the source
 *   popover, which is a `<span role="dialog">` and takes phrasing content
 *   alone — an `<ol>` in there was finding F15 in an earlier review.
 */
import { Fragment, cloneElement, isValidElement, type ReactNode } from 'react'
import { FILE_REF } from '../data/fileRefs.generated'

declare const __REPO_BLOB_BASE__: string

/** Same shape as C3b's own token regex, so the check and the link agree on
 *  what counts as naming a file. */
const FILE_TOKEN = /\b[A-Za-z][A-Za-z0-9_./-]*\.(?:json|md|py|csv|ts|tsx|jsonc|yml|yaml)\b/g

/** The repository's own page. Derived from the same build-time value as the
 *  file links, so it cannot drift from them or point at a fork's parent — the
 *  footer's "Open source" link was `https://github.com/`, the site's front
 *  page, which is a link that goes nowhere in particular. */
export const REPO_URL: string = __REPO_BLOB_BASE__
  ? __REPO_BLOB_BASE__.slice(0, __REPO_BLOB_BASE__.indexOf('/blob/'))
  : 'https://github.com/'

/** The repository URL for a named file, or null if this site cannot promise
 *  one — an unknown token, or a build with no remote to point at. */
export function fileHref(token: string): string | null {
  const path = FILE_REF[token]
  if (!path || !__REPO_BLOB_BASE__) return null
  return __REPO_BLOB_BASE__ + path
}

/**
 * `text` with every known file name turned into a link to that file.
 *
 * Returns the original string unchanged when nothing matches, so the common
 * case costs one regex test and allocates no array.
 */
export function linkifyFiles(text: string | null | undefined): ReactNode {
  if (!text) return text
  FILE_TOKEN.lastIndex = 0
  if (!FILE_TOKEN.test(text)) return text

  FILE_TOKEN.lastIndex = 0
  const out: ReactNode[] = []
  let at = 0
  let m: RegExpExecArray | null
  while ((m = FILE_TOKEN.exec(text)) !== null) {
    const href = fileHref(m[0])
    if (!href) continue
    if (m.index > at) out.push(text.slice(at, m.index))
    out.push(
      <a
        key={`${m.index}-${m[0]}`}
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        /* The accessible name says where the link goes; the visible text stays
         * exactly the filename, because adding hidden text inside a card body
         * would change the very .textContent the checks read. */
        aria-label={`${m[0]} — open this file in the repository`}
        style={{ color: 'inherit', textDecoration: 'underline', textUnderlineOffset: 2 }}
      >
        {m[0]}
      </a>,
    )
    at = m.index + m[0].length
  }
  if (at === 0) return text
  if (at < text.length) out.push(text.slice(at))
  return out
}

/**
 * A file name as a link, for copy that is already JSX rather than a string.
 *
 * Two cards said "Full account in NEEDS-DECISION.md →" and navigated to
 * `/data` — a label naming one thing and a link going to another, which is the
 * precise mismatch #70 raised. `/data` summarises; the file IS the full
 * account the sentence promises, so the label now goes where it says.
 *
 * Falls back to plain text when the token has no known path, so this can never
 * render a link to nowhere.
 */
export function FileLink({ name, children }: { name: string; children?: ReactNode }) {
  const href = fileHref(name)
  const label = children ?? name
  if (!href) return <>{label}</>
  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
      aria-label={`${name} — open this file in the repository`}
      style={{ color: 'inherit', textDecoration: 'underline', textUnderlineOffset: 2 }}>
      {label}
    </a>
  )
}

/**
 * Linkify every plain-text child in a subtree.
 *
 * The card wiring reached the sentences a source popover renders, which turned
 * out to be the minority. A page-wide sweep found file names in ordinary prose
 * on seven routes — most of them on `/data`, whose whole subject is the
 * pipeline — and a name in a paragraph is exactly as unclickable as a name in
 * a card. Wrapping the page is one change instead of one per sentence, and a
 * paragraph added later is covered without anyone remembering to wrap it.
 *
 * Only STRING children are touched. Elements are returned as they are (their
 * own children get the same treatment on their own render), so this cannot
 * reorder, clone or re-key anything, and a component that inspects its own
 * children still sees what it expects.
 */
export function LinkFiles({ children }: { children: ReactNode }): ReactNode {
  return mapText(children)
}

function mapText(node: ReactNode): ReactNode {
  if (typeof node === 'string') return linkifyFiles(node)
  if (Array.isArray(node)) return node.map((c, i) => <Fragment key={i}>{mapText(c)}</Fragment>)
  if (isValidElement(node)) {
    const kids = (node.props as { children?: ReactNode }).children
    if (kids === undefined) return node
    return cloneElement(node, undefined, mapText(kids))
  }
  return node
}
