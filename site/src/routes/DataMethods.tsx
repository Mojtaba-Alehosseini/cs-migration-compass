/* Data & methods — the receipts page, generated from provenance.json.
 *
 * Nothing here is written by hand about a source: the table is whatever the
 * pipeline actually recorded, including the sources that failed. A page that
 * only listed successes would be the dishonest version. */

import { useEffect, useState } from 'react'
import { useData, loadProvenance } from '../data/store'
import { CONFIDENCE_MARK, asOfLabel, num } from '../data/format'
import { HOME_M2 } from '../data/compute'
import type { Provenance } from '../data/types'

const BASE = import.meta.env.BASE_URL

export function DataMethods() {
  const data = useData()
  const [prov, setProv] = useState<Provenance | null>(null)

  useEffect(() => { loadProvenance().then(setProv).catch(() => setProv(null)) }, [])

  const ok = prov?.entries.filter((e) => e.status === 'ok' || e.status === 'partial') ?? []
  const missing = prov?.entries.filter((e) => !['ok', 'partial'].includes(e.status)) ?? []

  return (
    <div className="wrap" style={{ paddingTop: 22 }}>
      <h1 style={{ fontSize: 'var(--text-xl)' }}>Where every number comes from</h1>
      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-2)', margin: '8px 0 12px', maxWidth: '70ch' }}>
        No number on this site is our opinion. Each one traces to a source you can open — this page is
        the receipts, generated from the pipeline’s own log rather than written by hand.
      </p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <span className="chip chip-ok">{CONFIDENCE_MARK.official} Official — governments, central banks, the UN</span>
        <span className="chip chip-note">{CONFIDENCE_MARK.index} Research — big yearly studies and indices</span>
        <span className="chip chip-quiet">{CONFIDENCE_MARK.crowd} Crowd — people reporting their own rents and salaries</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12 }}>
        {/* min-height reserves the space this async table will fill. Without it
            provenance.json lands late and shifts the whole page (CLS 0.38). */}
        <div className="panel" style={{ gridColumn: '1 / -1', minHeight: prov ? undefined : 640 }}>
          <h2>The sources</h2>
          <div className="sub">
            {ok.length} datasets fed the site on the last pipeline run
            {prov?.updated_at && ` (${asOfLabel(prov.updated_at.slice(0, 7))})`}.
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: 'var(--text-2xs)' }}>
              <thead>
                <tr>
                  {['Source', 'What we take from it', 'Coverage', 'Licence'].map((h) => (
                    <th key={h} style={{ textAlign: 'left', padding: '8px 10px', color: 'var(--ink-3)', fontWeight: 500 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ok.map((e) => (
                  <tr key={e.source_id}>
                    <td style={cell}>
                      <b>{e.name}</b>
                      {e.urls[0] && (
                        <a href={e.urls[0]} target="_blank" rel="noopener noreferrer"
                          style={{ display: 'block', color: 'var(--accent)', marginTop: 2 }}>open ↗</a>
                      )}
                    </td>
                    <td style={cell}>
                      {e.transforms[0]}
                      {e.notes && <span style={{ display: 'block', color: 'var(--ink-3)', marginTop: 3 }}>{e.notes}</span>}
                    </td>
                    <td style={cell}>{e.coverage ?? '—'}{e.rows != null && <span style={{ display: 'block', color: 'var(--ink-3)' }}>{num(e.rows)} rows</span>}</td>
                    <td style={{ ...cell, color: 'var(--ink-3)' }}>{e.license}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {missing.length > 0 && (
          <div className="panel" style={{ gridColumn: '1 / -1' }}>
            <h2>Sources we could not get</h2>
            <div className="sub">
              Listed for the same reason the others are: if a source is missing, the honest thing is to
              say so rather than quietly fill the gap.
            </div>
            {missing.map((e) => (
              <div key={e.source_id} style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--line)' }}>
                <span className="chip chip-risk">{e.status}</span>{' '}
                <b style={{ fontSize: 'var(--text-xs)' }}>{e.name}</b>
                <p style={{ fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', marginTop: 4 }}>{e.notes}</p>
              </div>
            ))}
          </div>
        )}

        <div className="panel">
          <h2>The one formula that matters</h2>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--ink-2)', lineHeight: 1.9, marginTop: 6 }}>
            <b>Years to a home</b> = the price of a {HOME_M2} m² flat outside the centre ÷ what you save
            in a year.
            <br /><br />
            <b>Savings</b> = salary after that country’s real tax, minus rent, minus living costs.
            <br /><br />
            Every piece is editable in Compare, and the whole thing recalculates as you change it.
          </p>
        </div>

        <div className="panel">
          <h2>Where we might be wrong</h2>
          <ul style={{ margin: '8px 0 0 16px', padding: 0, fontSize: 'var(--text-2xs)', color: 'var(--ink-2)', lineHeight: 1.7 }}>
            <li><b>US salaries lean low.</b> Official medians, not big-tech packages. The levels.fyi band shows the other side.</li>
            <li><b>Gulf salaries split in two.</b> Multinationals pay 2–4× the local market. Both bands are shown, never averaged.</li>
            <li><b>Crowd rents wobble in small cities.</b> Big cities are solid; Aarhus, Halifax and Tampere are thin, and marked so.</li>
            <li><b>Visa rules age fast.</b> Every visa figure carries its date and warns once it passes the freshness rule.</li>
            <li><b>Missing means missing.</b> Where we have no number you see “no data” and which figure is absent — never a guess.</li>
          </ul>
        </div>

        <div className="panel" style={{ gridColumn: '1 / -1' }}>
          <h2>Take the data</h2>
          <div className="sub">Everything the site uses, in the form the pipeline produced it.</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
            {[
              ['countries.json', `${data.countries.length} countries`],
              ['cities.json', `${data.cities.length} cities`],
              ['metrics.json', 'the data dictionary'],
              ['provenance.json', 'every source and transform'],
            ].map(([file, label]) => (
              <a key={file} className="pill" href={`${BASE}data/${file}`} download
                style={{ textDecoration: 'none' }}>
                ⤓ {file} <span style={{ color: 'var(--ink-3)' }}>· {label}</span>
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

const cell: React.CSSProperties = {
  padding: '9px 10px', borderTop: '1px solid var(--line)', verticalAlign: 'top',
}
