/* Package 22, Tier 1 — the CV file never leaves the browser. Only the text
 * this module extracts (after stripPii.ts runs on it) is ever sent
 * anywhere. pdfjs-dist is dynamically imported here, and ONLY here, behind
 * the upload handler that calls extractCvText() — the base bundle carries
 * none of its ~490 KB gzipped (126 KB main + 364 KB worker) until a user
 * actually picks a file.
 *
 * Reading order: PDF.js hands back text items in the order the PDF's own
 * content stream places them, which for a single-column CV usually reads
 * fine but for a two-column layout interleaves left and right columns
 * line by line. Sorting by each item's own position (`transform[4]` is x,
 * `transform[5]` is y in PDF user space, Y increasing upward) into rows,
 * then left-to-right within a row, is the same fix package 19's
 * scripts/pdf_table.py applied to tables for the same underlying reason —
 * the work order names that precedent directly. This does not guarantee a
 * perfect reconstruction (a genuine two-column layout still has no single
 * "correct" reading order once flattened to plain text), and does not
 * need to: the model tolerates jumbled text far better than a rigid
 * parser downstream would, so residual noise here is an accepted cost,
 * not a bug to chase to zero.
 */

export const MAX_CV_TEXT_CHARS = 20_000

export interface ExtractResult {
  /** Empty string exactly when `scanned` is true — never a partial guess. */
  text: string
  /** True when no page produced any real text — a scanned/image-only PDF
   *  (no text layer) rather than a native one. The caller must fall back
   *  to the manual form, not send this. */
  scanned: boolean
  pageCount: number
}

export interface PositionedItem {
  str: string
  x: number
  y: number
  height: number
}

/** Zero-width and bidirectional control characters: invisible in a PDF
 *  viewer (so a reviewer proofreading their own CV would never notice
 *  one), but each is a real, distinct code point to a model — a title
 *  with a zero-width space spliced into it does not match anything in
 *  the occupation crosswalk, and bidi override characters can make text
 *  visually misrepresent the very string being sent. Stripped here,
 *  before anything downstream ever sees the text. */
export function stripInvisibleChars(s: string): string {
  // U+200B-200D (ZWSP/ZWNJ/ZWJ), U+FEFF (BOM/ZWNBSP), U+202A-202E and
  // U+2066-2069 (bidi embedding/override/isolate controls).
  return s.replace(/[​-‍﻿‪-‮⁦-⁩]/g, '')
}

/** Groups items into rows by Y position (PDF space, larger y = higher on
 *  the page), tolerant of the small baseline jitter real PDFs have even
 *  within what a reader would call "one line" — then orders each row
 *  left to right by X. Tolerance scales to this page's own median item
 *  height rather than a fixed constant, since two CVs set in a 9pt and a
 *  14pt font do not share one sensible pixel threshold. */
export function sortIntoReadingOrder(items: PositionedItem[]): string {
  if (items.length === 0) return ''
  const heights = items.map((it) => it.height).filter((h) => h > 0).sort((a, b) => a - b)
  const medianHeight = heights.length ? heights[Math.floor(heights.length / 2)]! : 10
  const tolerance = medianHeight * 0.4

  const sorted = [...items].sort((a, b) => b.y - a.y)
  const rows: PositionedItem[][] = []
  for (const item of sorted) {
    const row = rows[rows.length - 1]
    if (row && Math.abs(row[0]!.y - item.y) <= tolerance) {
      row.push(item)
    } else {
      rows.push([item])
    }
  }
  return rows
    .map((row) => [...row].sort((a, b) => a.x - b.x).map((it) => it.str).join(' '))
    .join('\n')
}

export async function extractCvText(file: File): Promise<ExtractResult> {
  const [{ getDocument, GlobalWorkerOptions }, workerUrlModule] = await Promise.all([
    import('pdfjs-dist'),
    import('pdfjs-dist/build/pdf.worker.min.mjs?url'),
  ])
  GlobalWorkerOptions.workerSrc = workerUrlModule.default

  const buf = await file.arrayBuffer()
  // Kept separately from `doc` (the resolved PDFDocumentProxy) -- destroy()
  // lives on the LOADING TASK, not the proxy it resolves to; the proxy's
  // own cleanup() only clears caches and leaves the worker running.
  const loadingTask = getDocument({ data: buf })
  const doc = await loadingTask.promise
  try {
    const pageTexts: string[] = []
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i)
      const content = await page.getTextContent()
      const items: PositionedItem[] = []
      for (const raw of content.items) {
        // TextMarkedContent entries carry no `str`/`transform` -- only
        // TextItem does (see this module's own header for the shape).
        if (!('str' in raw) || !('transform' in raw)) continue
        const str = raw.str
        if (!str || !str.trim()) continue
        items.push({ str, x: raw.transform[4], y: raw.transform[5], height: raw.height })
      }
      pageTexts.push(sortIntoReadingOrder(items))
    }

    let text = stripInvisibleChars(pageTexts.join('\n\n')).trim()
    const scanned = text.length === 0
    if (scanned) text = ''
    if (text.length > MAX_CV_TEXT_CHARS) text = text.slice(0, MAX_CV_TEXT_CHARS)

    return { text, scanned, pageCount: doc.numPages }
  } finally {
    // Tears down the worker and releases the parsed document's own memory
    // (fonts, image data) — this runs once per upload, but a CV can carry
    // embedded images and there is no reason to hold any of it, or keep
    // the worker alive, past extraction.
    await loadingTask.destroy()
  }
}
