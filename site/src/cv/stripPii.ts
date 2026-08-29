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

// Package 23, Gate 1 — the owner's own CV leaked exactly here: a bare
// `firstname-lastname.github.io` (no scheme, no `www.`, no `github.com/`
// path) matched none of the three alternatives this pattern used to have,
// so it went to the model in full view while the panel claimed the name
// had been removed. Bare hostnames across common TLDs are matched here
// too, deliberately case-SENSITIVE on the TLD itself — the reason is not
// a shortcut, it is what keeps a technology name from being read as a
// domain: a real domain's TLD is written in lowercase in ordinary use
// ("github.io", never "GitHub.IO"), while the one realistic collision
// this project's own CVs contain, ".NET" (as in "ASP.NET"), is written
// with the TLD-lookalike part in UPPERCASE -- "asp.net" in lowercase
// would still match, and should: at that point it is indistinguishable
// from a genuine lowercase domain, and the asymmetry this file's own
// header names (redact when uncertain) applies the same way here.
// "Node.js" / "React.js" need no special-casing: ".js" is not in the TLD
// list below at all. A version string ("3.11", "v3.11.2") is excluded by
// construction -- the TLD list is alphabetic strings only, and a bare
// digit run can never match one. A sentence-ending "word.Word" ("...used
// React. My next...") cannot match either: the TLD must follow the dot
// with NO space, and a sentence boundary always has one. All four of
// these are the work order's own named false-positive risks, tested
// directly against exactly this shape before trusting the pattern (see
// site/tests/stripPii.test.ts), not assumed safe from reading the regex.
// The TLD list is deliberately not exhaustive (a real list runs past a
// thousand entries) -- generic ones plus the countries this site's own
// audience and the owner's own CV (Italy) plausibly produce a bare
// personal domain in.
const BARE_DOMAIN_TLDS = 'com|io|dev|me|page|co|net|org|ai|app|info|xyz|tech|pro|cloud|site'
  + '|dk|uk|de|it|nl|se|no|fr|es|ca|us|au'
const BARE_DOMAIN_RE = new RegExp(
  String.raw`\b[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?`
  + String.raw`(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*`
  + String.raw`\.(?:${BARE_DOMAIN_TLDS})\b(?:/\S*)?`,
  'g',
)

// http(s):// links, and bare "known-profile-host/path" forms a CV commonly
// carries without a scheme (linkedin.com/in/…, github.com/…, LinkedIn's
// own lnkd.in short-link domain — found by Package 23's own Gate 11
// adversarial review, the same class of gap Tier 1 fixed: lnkd.in's own
// TLD, .in, was not on BARE_DOMAIN_RE's curated list, and adding .in
// there generally would make an ordinary English word — "in" — a TLD
// match risk, so it is special-cased here instead, alongside the other
// known, unambiguous profile hosts). General bare domains beyond these
// four special-cased hosts are handled by BARE_DOMAIN_RE above, not here
// — this half stays case-insensitive because there is no tech-term
// collision risk on these specific host names the way there is for a
// generic TLD match.
const URL_RE = /\bhttps?:\/\/\S+|\b(?:www\.|(?:linkedin|github|gitlab)\.com\/|lnkd\.in\/?)\S*/gi

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
function redactLikelyNameLine(
  text: string,
): { text: string; redaction: PiiRedaction | null; tokens: string[] } {
  const lines = text.split('\n')
  const genericHeaders = new Set(['resume', 'cv', 'curriculum vitae', 'profile', 'summary'])
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!.trim()
    if (!line) continue
    // A purely decorative line (a rule of dashes/equals, a bare bullet) has
    // no letters at all -- skip past it rather than stopping the whole
    // scan here, since a template that opens with a divider line would
    // otherwise put the real name permanently out of reach. Found live:
    // "=====\nJane Doe" left the name unredacted under the first version
    // of this function, which stopped at the FIRST non-empty line
    // unconditionally.
    if (!/[a-zA-Z]/.test(line)) continue
    if (genericHeaders.has(line.toLowerCase())) return { text, redaction: null, tokens: [] }
    const words = line.split(/\s+/)
    const looksLikeName = words.length >= 2 && words.length <= 4
      && words.every((w) => /^[A-Z][a-zA-Z'.-]*$/.test(w))
    if (looksLikeName) {
      const before = lines.slice(0, i)
      const after = lines.slice(i + 1)
      return {
        text: [...before, '[NAME]', ...after].join('\n'),
        redaction: { category: 'name', original: line },
        tokens: words,
      }
    }
    // The first line carrying any actual letters was checked; if it is
    // not name-shaped, stop — scanning further down risks redacting an
    // ordinary job title or company name that happens to be title-cased.
    return { text, redaction: null, tokens: [] }
  }
  return { text, redaction: null, tokens: [] }
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Package 23, Gate 2 — the name-LINE redaction above closes exactly one
 *  occurrence. The owner's own leak was a second occurrence of the same
 *  name, inside a domain, that the line-based redaction never looks at.
 *  "A name appearing three times and redacted once is the same failure in
 *  a different place" (the work order's own words) — so once the name is
 *  known, every remaining occurrence of it anywhere in the text is swept,
 *  not just the line it was first found on.
 *
 *  Two levels, run in order:
 *  1. The full name as one flexible unit — tokens joined by any run of
 *     spaces/dots/hyphens/underscores, OR NOTHING — so
 *     "mojtaba-alehosseini" (a domain), "mojtaba.alehosseini" (an email
 *     local-part), "mojtabaalehosseini" (a concatenated filename/handle)
 *     and "MOJTABA ALEHOSSEINI" (a repeated all-caps header) are all one
 *     match each, case-insensitive.
 *  2. Individual tokens on their own — a first name alone in a sentence,
 *     with no surname beside it, which level 1 cannot match. Restricted to
 *     tokens whose alphabetic core is 3+ characters: a bare 1-2 letter
 *     token (an initial, "Jr.", "Li") is too common a substring/word in
 *     ordinary prose to sweep globally without a much broader
 *     false-positive cost than the narrow miss it would close — the SAME
 *     line-based redaction above still catches a short token when it is
 *     actually part of the name line itself, this level only skips
 *     sweeping it EVERYWHERE ELSE in the document.
 *
 *  Each match found is pushed as its own `name` redaction, so a name
 *  appearing twice is counted as two — the honest-count requirement
 *  (Gate 3) this package exists to satisfy. Deliberately run AFTER email/
 *  url/phone/address in stripPii()'s own pipeline: those more specific
 *  patterns get first claim on anything they can positively identify (an
 *  email swallows a name in its own local-part whole, as `[EMAIL]`, not a
 *  separate `name` redaction), and this sweep is the last-resort backstop
 *  for whatever they do not recognise — an uncommon TLD the bare-domain
 *  pattern does not list, a plain repeated headline, a filename mention. */
function sweepNameEverywhere(text: string, rawTokens: string[]): StripPiiResult {
  const redactions: PiiRedaction[] = []
  let out = text
  // A trailing period is a line-ending/OCR artefact far more often than a
  // real part of a name — stripped here only, so a full-phrase match does
  // not require an exact trailing "." that a domain or a repeated
  // headline elsewhere would never carry.
  const tokens = rawTokens.map((t) => t.replace(/\.+$/, '')).filter(Boolean)

  if (tokens.length >= 2) {
    const joined = tokens.map(escapeRegExp).join('[\\s.\\-_]*')
    const fullNameRe = new RegExp(`\\b${joined}\\b`, 'gi')
    out = out.replace(fullNameRe, (m) => {
      redactions.push({ category: 'name', original: m })
      return '[NAME]'
    })
  }

  const qualifying = tokens.filter((t) => t.replace(/[^a-zA-Z]/g, '').length >= 3)
  if (qualifying.length > 0) {
    const tokenRe = new RegExp(`\\b(?:${qualifying.map(escapeRegExp).join('|')})\\b`, 'gi')
    out = out.replace(tokenRe, (m) => {
      redactions.push({ category: 'name', original: m })
      return '[NAME]'
    })
  }

  return { text: out, redactions }
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
  text = redactPattern(text, BARE_DOMAIN_RE, 'url', 'URL', redactions)
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

  if (nameResult.tokens.length > 0) {
    const swept = sweepNameEverywhere(text, nameResult.tokens)
    text = swept.text
    redactions.push(...swept.redactions)
  }

  return { text, redactions }
}
