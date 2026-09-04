/* Which of a country's skilled routes answers which question.
 *
 * `visa.skilled_routes` is an ARRAY WITH NO RECORDED ORDERING. Nothing in the
 * data says the first element is the main one, the cheapest one, or the one
 * most people use — the harvester appended them in whatever order it found
 * them. Reading `[0]` therefore makes array position stand in for a
 * relationship nobody recorded, which is NEEDS-DECISION #59's defect C.
 *
 * It has now escaped twice. Package 27 fixed it in the Explore ruler, where
 * `[0]` made the UAE look like it had no salary floor at all while its Green
 * Visa publishes $49,000. Package 28's adversarial review found it still live
 * on every city page (#66), naming the first element as "the legal road" from
 * landing to a passport.
 *
 * So the two questions the site actually asks get one named function each,
 * side by side, because they have DIFFERENT right answers and conflating them
 * is how this keeps recurring:
 *
 *   - "what does the door cost?"  -> the LOWEST published floor (Explore's
 *     ruler). The cheapest way in is the honest answer to a price question.
 *   - "what do you land on?"      -> the route you actually ARRIVE on
 *     (CityProfile's journey). The cheapest route is emphatically not the
 *     answer here: for the UAE that is the Green Visa, a self-sponsored
 *     residence permit, not the thing a hired engineer lands on.
 */
import type { Country, VisaRoute } from './types'

/* How well each recorded `type` matches "you land on a work visa" — the
 * sentence CityProfile renders. Derived from the field the data already
 * carries, not from a judgement added on top of it:
 *
 *   employer_offer  you arrive with a job, sponsored. The sentence's literal
 *                   case, and 18 of the 27 recorded routes.
 *   points          you arrive on your own score, no employer needed
 *                   (CA Express Entry, AU Skilled Independent). Still an
 *                   arrival route, and Canada has ONLY this one.
 *   talent          self-sponsored or exceptional-ability (O-1A, Golden
 *                   Visa, Digital Nomad). A real way in, never the typical
 *                   one.
 *   job_seeker      you arrive WITHOUT a job, to look for one (DE
 *                   Opportunity Card, NO job-seeker permit). Naming this as
 *                   "the work visa you land on" would be false.
 */
const ARRIVAL_RANK: Record<string, number> = {
  employer_offer: 0,
  points: 1,
  talent: 2,
  job_seeker: 3,
}
const UNRANKED = 9

/** The route a person most typically ARRIVES on — what CityProfile's journey
 *  names. Ranked by `type` first; where two routes share a type, the one with
 *  the LOWER barrier to entry wins — no published salary floor beats a floor,
 *  and a lower floor beats a higher one.
 *
 *  That second rule is not decoration. Denmark records two `employer_offer`
 *  routes: the Pay Limit Scheme, which needs $85,000, and the Positive List,
 *  which has no floor and whose own summary says "software developers
 *  regularly listed". Copenhagen's and Aarhus's own published bands are
 *  $70,000 new-grad and $81,000 mid — BELOW the Pay Limit floor — so naming
 *  it as the route you typically land on was wrong for most of the people
 *  this site is written for. Package 29's adversarial review caught it, in a
 *  tie the first version of this file had claimed to check by hand.
 *
 *  Where routes tie on type AND barrier the data records nothing further and
 *  recorded order stands: NL's two routes publish the identical $82,100, and
 *  Italy's two publish none, and in both the first is the standard one —
 *  Italy's second even says so ("Blue Card is the realistic dev route"). */
export function typicalArrivalRoute(country: Country | undefined): VisaRoute | undefined {
  const routes = country?.visa?.skilled_routes ?? []
  // A route with no published floor gates on no salary at all, so it is open
  // to more people than one that does; among floors, the lower is the lower bar.
  const barrier = (r: VisaRoute) => r.salary_threshold_usd ?? -1
  let best: VisaRoute | undefined
  let bestRank = Infinity
  for (const r of routes) {
    const rank = ARRIVAL_RANK[r.type] ?? UNRANKED
    if (rank < bestRank) { best = r; bestRank = rank; continue }
    if (rank === bestRank && best && barrier(r) < barrier(best)) best = r
  }
  return best
}

/** The cheapest published way in — what Explore's salary-floor ruler plots.
 *  Countries whose routes publish no floor at all return null, which the
 *  ruler renders as "points or sponsorship, no salary floor" rather than
 *  dropping them. Package 27 fixed this reading `[0]`, which reported the
 *  UAE as floorless because its first recorded route happens to be the one
 *  without a threshold. */
export function lowestSalaryFloorRoute(country: Country | undefined): VisaRoute | null {
  const routes = country?.visa?.skilled_routes ?? []
  let cheapest: VisaRoute | null = null
  for (const r of routes) {
    if (r.salary_threshold_usd == null) continue
    if (cheapest == null || r.salary_threshold_usd < cheapest.salary_threshold_usd!) cheapest = r
  }
  return cheapest
}
