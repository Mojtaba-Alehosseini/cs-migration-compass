/* Package 12, tier 4 — the seed-list transparency page. The work order's
 * own test, stated plainly: "if publishing the seed list would embarrass a
 * country, that country is not ready to show a number." This page is that
 * test, applied — every company in the panel, which ATS it uses, which
 * country it was counted toward, whether that provider's own data ever
 * carries a pay figure at all, and a plain statement of what the list
 * over-represents and why (an ATS-seeded panel skews hard toward
 * US/UK VC-backed tech — the wrong shape for a site covering Denmark, Italy
 * and the Gulf, named here rather than left implicit).
 */

import { useMemo, useState } from 'react'
import { useAsync } from '../components/explore/useAsync'
import { Flag } from '../components/Flag'
import { loadPostings, fmtCompany, KNOWN_PROVIDERS, PROVIDER_LABEL, PROVIDER_HAS_COMPENSATION_FIELD, PROVIDER_LICENSE } from '../data/postings'

const DENSITY_NOTE: Record<string, string> = {
  US: 'HIGH — expected: California, Colorado, Illinois, Maryland, Massachusetts, Minnesota, New '
    + 'Jersey, New York, Vermont, Washington and DC all require pay ranges in postings; most ATS '
    + 'providers this panel reads are US-headquartered by default.',
  GB: 'MEDIUM — no legal requirement yet; UK-founded tech has strong ATS-provider overlap regardless.',
  IE: 'MEDIUM — same ATS-provider overlap as the UK, smaller company count.',
  NL: 'MEDIUM — same reasoning as GB/IE.',
  CA: 'HIGH (Ontario) — Ontario\'s own pay-transparency law took effect 1 Jan 2026; British Columbia\'s since 2023.',
  IT: 'Expected to grow — Italy is the only EU state that transposed the EU pay-transparency '
    + 'directive with an in-advert mandate, in force 7 Jun 2026. Not yet reflected much in this '
    + "panel's own seed list, which predates that date's practical effect on postings volume.",
  DE: 'LOW — no in-advert mandate; this panel\'s own German coverage leans on Personio/Teamtailor '
    + 'candidates this session could not fully verify (see NEEDS-DECISION.md).',
  ES: 'LOW — same reasoning as Germany.', SE: 'LOW — same reasoning as Germany.',
  DK: 'LOW — same reasoning as Germany.', NO: 'LOW — same reasoning as Germany.', FI: 'LOW — same reasoning as Germany.',
  AU: 'LOW — no in-advert mandate; smaller ATS-provider overlap than US/UK/CA in this panel\'s own sample.',
  QA: 'LOW — no ATS provider in this panel independently verified a Gulf-headquartered company this session.',
  AE: 'LOW — same reasoning as Qatar.',
}

export function PostingsSeed() {
  const { data, error } = useAsync(loadPostings, 'postings')
  const [providerFilter, setProviderFilter] = useState('')

  const companies = useMemo(() => {
    if (!data) return []
    return Object.values(data.seed_companies)
      .filter((c) => !providerFilter || c.provider === providerFilter)
      .sort((a, b) => b.job_count - a.job_count)
  }, [data, providerFilter])

  const countryRows = useMemo(() => {
    if (!data) return []
    return Object.entries(data.country_counts).sort((a, b) => b[1] - a[1])
  }, [data])

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <h1 style={{ fontSize: 'var(--text-xl)' }}>Where the postings panel's own data comes from</h1>
      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)', padding: '8px 0 12px', maxWidth: '74ch' }}>
        No ATS publishes a directory of which companies use it. This panel's own company list was
        built by probing real candidate tokens against each provider's live API and keeping only
        the ones that resolved with at least one real posting — every row below is a company this
        session actually verified, not a claim. <b>If this list would embarrass a country, that
        country is not ready to show a number</b> — the panel's own filters (
        <code>Postings</code>) reflect exactly this same set, nothing hidden or pre-filtered here.
      </p>

      {error && <div className="panel" style={{ borderColor: 'var(--warn)' }}><p>{error}</p></div>}

      {!data ? (
        <div className="panel"><p className="nodata">Loading…</p></div>
      ) : (
        <>
          <div className="panel">
            <h2>What this list over-represents, stated plainly</h2>
            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', marginTop: 8, maxWidth: '74ch' }}>
              An ATS-seeded panel skews hard toward US/UK VC-backed tech — the providers this
              pipeline can reach without a key (Ashby, Greenhouse, Lever) are disproportionately
              used by that exact company shape. This is the wrong shape for a site covering
              Denmark, Italy and the Gulf, and is named here rather than left implicit. Per-country
              posting counts sit beside every figure on the panel itself for the same reason —
              6 companies means "6 companies," never a median.
            </p>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 12 }}>
              <thead>
                <tr style={{ textAlign: 'left', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
                  <th style={{ padding: '4px 10px' }}>Country</th>
                  <th style={{ padding: '4px 10px' }}>Postings</th>
                  <th style={{ padding: '4px 10px' }}>Expected pay-transparency density</th>
                </tr>
              </thead>
              <tbody>
                {countryRows.map(([cc, n]) => (
                  <tr key={cc}>
                    <td style={{ padding: '5px 10px', fontSize: 'var(--text-xs)' }}>
                      {cc !== 'unresolved' && <Flag cc={cc} size={12} />} {cc === 'unresolved' ? 'Unresolved location' : cc}
                    </td>
                    <td style={{ padding: '5px 10px', fontSize: 'var(--text-xs)' }}>{n.toLocaleString()}</td>
                    <td style={{ padding: '5px 10px', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
                      {DENSITY_NOTE[cc] ?? (cc === 'unresolved' ? 'The location text this posting published did not resolve to a country this pipeline recognises — kept, not dropped, and shown here rather than silently excluded.' : '—')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel" style={{ marginTop: 12 }}>
            <h2>Sources</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 8 }}>
              <thead>
                <tr style={{ textAlign: 'left', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
                  <th style={{ padding: '4px 10px' }}>Provider</th>
                  <th style={{ padding: '4px 10px' }}>Status</th>
                  <th style={{ padding: '4px 10px' }}>Postings</th>
                  <th style={{ padding: '4px 10px' }}>Ever carries a pay figure?</th>
                </tr>
              </thead>
              <tbody>
                {KNOWN_PROVIDERS.map((p) => {
                  const s = data.provider_summary[p]
                  return (
                    <tr key={p}>
                      <td style={{ padding: '5px 10px', fontSize: 'var(--text-xs)' }}>{PROVIDER_LABEL[p]}</td>
                      <td style={{ padding: '5px 10px', fontSize: 'var(--text-xs)' }}>
                        {s?.available ? <span className="chip chip-ok">built</span> : <span className="chip chip-quiet">not built this run</span>}
                      </td>
                      <td style={{ padding: '5px 10px', fontSize: 'var(--text-xs)' }}>{s?.postings_count?.toLocaleString() ?? '—'}</td>
                      <td style={{ padding: '5px 10px', fontSize: 'var(--text-xs)' }}>
                        {PROVIDER_HAS_COMPENSATION_FIELD[p] ? 'Yes — optional/variable per posting' : 'No — not observed in this pipeline\'s own harvest'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 10 }}>
              Probed but not built into a harvester this package (endpoint confirmed live, verdict
              recorded, no company list wired yet): Workday (compensation only reachable as
              free-text inside pay-transparency-state postings, not a structured field — verified
              live), SmartRecruiters and Workable (both confirmed live, neither ever carries
              compensation). Personio and Recruitee: endpoint format documented, no live customer
              subdomain confirmed within this session's own probe budget. Jobvite and JazzHR:
              confirmed NOT usable at scale (per-customer opt-in feeds, off by default; no
              guessable public endpoint). Full account: NEEDS-DECISION.md.
            </p>
          </div>

          <div className="panel" style={{ marginTop: 12 }}>
            <h2>Licence and attribution, per source</h2>
            <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 6, maxWidth: '74ch' }}>
              No source in this panel required a paid licence, a click-through ToS acceptance, or an
              account. Each provider's basis, restated from what its own harvester records at fetch
              time:
            </p>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 10 }}>
              <tbody>
                {KNOWN_PROVIDERS.map((p) => (
                  <tr key={p}>
                    <td style={{ padding: '5px 10px', fontSize: 'var(--text-xs)', whiteSpace: 'nowrap', verticalAlign: 'top' }}>{PROVIDER_LABEL[p]}</td>
                    <td style={{ padding: '5px 10px', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>{PROVIDER_LICENSE[p]}</td>
                  </tr>
                ))}
                <tr>
                  <td style={{ padding: '5px 10px', fontSize: 'var(--text-xs)', whiteSpace: 'nowrap', verticalAlign: 'top' }}>Seed-list candidates</td>
                  <td style={{ padding: '5px 10px', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>
                    Ashby/Greenhouse/Lever candidate tokens loaded from a third-party aggregator
                    (<a href="https://github.com/Feashliaa/job-board-aggregator" target="_blank" rel="noreferrer">github.com/Feashliaa/job-board-aggregator</a>,
                    MIT-licensed) as hints only — every token is re-probed against the real live
                    endpoint before it counts toward the company list above; none is trusted unverified.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="panel" style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 8 }}>
              <h2>Every ATS company ({companies.length.toLocaleString()})</h2>
              <select value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)}
                aria-label="Filter companies by provider"
                style={{ padding: '6px 8px', border: '1px solid var(--line)', background: 'var(--surface)',
                  borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)' }}>
                <option value="">All providers</option>
                {KNOWN_PROVIDERS.map((p) => <option key={p} value={p}>{PROVIDER_LABEL[p]}</option>)}
              </select>
            </div>
            <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 6, maxWidth: '74ch' }}>
              Ashby, Greenhouse, Lever and Teamtailor each publish a company/board token this pipeline
              can list one row per company for. USAJOBS and Hacker News don't work that way — a USAJOBS
              posting names a federal agency, not an ATS-hosted board, and an HN commenter's own company
              name is free text, not a verifiable token. Their own 4,240 postings (242 distinct named
              employers) are counted in the provider table above and filterable on the panel itself, just
              not listed row-by-row here alongside an ATS token.
            </p>
            <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', marginTop: 6, maxWidth: '74ch' }}>
              A token is not always a name. Ashby's and Lever's own public APIs never publish a
              company DISPLAY NAME at all (checked live, not assumed — see postings_common.py's own
              record-shape docstring) — every "company" shown for their rows, here and throughout this
              panel, is this pipeline reading the board TOKEN into a readable label (fmtCompany()), not
              a name the source itself published. Greenhouse, Teamtailor and USAJOBS all publish a real
              display name directly; those rows are the company's own name, unmodified.
            </p>
            <div style={{ maxHeight: 480, overflowY: 'auto', marginTop: 10 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)', position: 'sticky', top: 0, background: 'var(--surface)' }}>
                    <th style={{ padding: '4px 10px' }}>Company</th>
                    <th style={{ padding: '4px 10px' }}>ATS</th>
                    <th style={{ padding: '4px 10px' }}>Open postings this run</th>
                  </tr>
                </thead>
                <tbody>
                  {companies.map((c) => (
                    <tr key={`${c.provider}:${c.company_slug}`}>
                      <td style={{ padding: '4px 10px', fontSize: 'var(--text-xs)' }}>{fmtCompany(c.company, c.company_slug)}</td>
                      <td style={{ padding: '4px 10px', fontSize: 'var(--text-2xs)', color: 'var(--ink-3)' }}>{PROVIDER_LABEL[c.provider]}</td>
                      <td style={{ padding: '4px 10px', fontSize: 'var(--text-xs)' }}>{c.job_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
