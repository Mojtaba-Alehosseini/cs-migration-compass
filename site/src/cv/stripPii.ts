/* Package 22, Tier 1 — PII stripped client-side, before anything is sent
 * anywhere. This is a good-faith, regex/heuristic pass, not a guarantee:
 * there is no reliable model-free way to find every name or every
 * address in free text, and using the CV-reading model ITSELF to find
 * PII before the CV-reading model sees the CV is circular. The real
 * safety net is Tier 3's own review step — "show the user exactly what
 * will be transmitted, before it is transmitted" — which is why every
 * redaction here leaves a visible `[LABEL]` marker rather than silently
 * vanishing: a reviewer can tell stripping happened, and can tell if
 * something looks like it survived that should not have.
 *
 * Order matters: email and URL patterns are checked before phone, because
 * a domain or an email's own digits (a numbered subdomain, a path
 * segment) can otherwise get mis-read as a phone number once the
 * surrounding structure is gone.
 */

export type PiiCategory = 'email' | 'phone' | 'url' | 'address' | 'name'

export interface PiiRedaction {
  category: PiiCategory
  original: string
}

export interface StripPiiResult {
  text: string
  redactions: PiiRedaction[]
}

const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g

// http(s):// links, and bare "known-profile-host/path" forms a CV commonly
// carries without a scheme (linkedin.com/in/…, github.com/…) — general
// bare domains (e.g. a company name in prose that happens to end .com)
// are deliberately NOT matched here; that would over-redact ordinary text
// for a marginal recall gain on a form of PII the scheme-based match
// already covers for anyone who pasted a real link.
const URL_RE = /\bhttps?:\/\/\S+|\b(?:www\.|(?:linkedin|github|gitlab)\.com\/)\S*/gi

// International-friendly: an optional leading +, then 7-15 digits with
// optional spaces/dots/dashes/parens between groups. Requires at least 7
// DIGITS specifically (not 7 characters), so a short date-like run
// ("05/2023") or a section heading numbered "2." cannot match — a real
// phone number's own digit count is the actual distinguishing signal, not
// its punctuation.
const PHONE_RE = /(?:\+\d{1,3}[\s.-]?)?(?:\(\d{1,4}\)[\s.-]?)?(?:\d[\s.-]?){6,14}\d/g

// A physical-address LINE, not a bare word: requires a leading building/
// street number followed by a recognisable street-type token, OR a
// postal/ZIP-code-shaped token. Line-scoped deliberately -- a CV's own
// prose ("5 years leading a team of 12 engineers") should never match a
// pattern meant for "123 Example Street".
const STREET_LINE_RE = /^\s*\d{1,5}[A-Za-z]?\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,4}\s+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct|place|pl|square|sq|terrace|apt|apartment|suite|ste|floor|fl)\b.*$/i
const POSTAL_CODE_RE = /\b\d{5}(?:-\d{4})?\b|\b[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d\b|\b[A-Za-z]{1,2}\d{1,2}[A-Za-z]?\s?\d[A-Za-z]{2}\b/

/** A CV's own first meaningful line is conventionally the candidate's
 *  name — the one place free text this generic, without a curated name
 *  database, can guess at with reasonable confidence. 2-4
 *  capitalised words, no digits, not one of the generic header labels a
 *  template sometimes puts there instead. False negatives (a name this
 *  misses) leave real text for the reviewer to catch by hand; a false
 *  positive here at worst redacts an ordinary section heading — the
 *  asymmetry favours redacting when uncertain, not the reverse. */
function redactLikelyNameLine(text: string): { text: string; redaction: PiiRedaction | null } {
  const lines = text.split('\n')
  const genericHeaders = new Set(['resume', 'cv', 'curriculum vitae', 'profile', 'summary'])
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!.trim()
    if (!line) continue
    if (genericHeaders.has(line.toLowerCase())) return { text, redaction: null }
    const words = line.split(/\s+/)
    const looksLikeName = words.length >= 2 && words.length <= 4
      && words.every((w) => /^[A-Z][a-zA-Z'.-]*$/.test(w))
    if (looksLikeName) {
      const before = lines.slice(0, i)
      const after = lines.slice(i + 1)
      return {
        text: [...before, '[NAME]', ...after].join('\n'),
        redaction: { category: 'name', original: line },
      }
    }
    // The first non-empty line was checked; if it's not name-shaped, stop
    // — scanning further down risks redacting an ordinary job title or
    // company name that happens to be title-cased.
    return { text, redaction: null }
  }
  return { text, redaction: null }
}

function redactPattern(
  text: string, re: RegExp, category: PiiCategory, label: string, redactions: PiiRedaction[],
): string {
  return text.replace(re, (match) => {
    redactions.push({ category, original: match })
    return `[${label}]`
  })
}

/** The phone pattern's one real false-positive risk on a CV specifically:
 *  an employment or education date range ("2020-2023", "2016 - 2020") is
 *  two 4-digit groups joined by exactly one separator, which is also a
 *  valid shape for a phone number's own digit groups — found live by
 *  testing against ordinary CV date ranges before trusting this pattern,
 *  not assumed safe from the regex alone. Excluded specifically rather
 *  than loosening the phone pattern generally, since a genuine phone
 *  number sharing this exact "two 4-digit groups, one separator" shape is
 *  the rarer case (e.g. an unusual grouping of a longer number would
 *  still have more than 8 digits total, which this check does not touch). */
function looksLikeYearRange(match: string): boolean {
  const digitGroups = match.match(/\d+/g) ?? []
  if (digitGroups.length !== 2 || digitGroups.some((g) => g.length !== 4)) return false
  return digitGroups.every((g) => {
    const y = Number(g)
    return y >= 1950 && y <= 2035
  })
}

export function stripPii(rawText: string): StripPiiResult {
  const redactions: PiiRedaction[] = []
  let text = rawText

  text = redactPattern(text, EMAIL_RE, 'email', 'EMAIL', redactions)
  text = redactPattern(text, URL_RE, 'url', 'URL', redactions)
  text = text.replace(PHONE_RE, (match) => {
    if (looksLikeYearRange(match)) return match
    redactions.push({ category: 'phone', original: match })
    return '[PHONE]'
  })

  text = text
    .split('\n')
    .map((line) => {
      if (STREET_LINE_RE.test(line) || POSTAL_CODE_RE.test(line)) {
        redactions.push({ category: 'address', original: line.trim() })
        return '[ADDRESS]'
      }
      return line
    })
    .join('\n')

  const nameResult = redactLikelyNameLine(text)
  text = nameResult.text
  if (nameResult.redaction) redactions.push(nameResult.redaction)

  return { text, redactions }
}
