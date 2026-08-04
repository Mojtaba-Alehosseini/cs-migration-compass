/* CSV / JSON export.
 *
 * Every table and chart offers this, because a site that asks to be trusted
 * should let people take the numbers away and check them. Nulls export as empty
 * cells, never as 0. */

function save(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function escapeCell(v: unknown): string {
  if (v == null) return ''
  const s = String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function downloadCsv(filename: string, rows: Record<string, unknown>[]) {
  if (rows.length === 0) return
  const headers = Array.from(new Set(rows.flatMap((r) => Object.keys(r))))
  const lines = [
    headers.join(','),
    ...rows.map((r) => headers.map((h) => escapeCell(r[h])).join(',')),
  ]
  const preamble = [
    '# CS Migration Compass export',
    `# generated ${new Date().toISOString().slice(0, 10)}`,
    '# Empty cells mean no data — never zero. Sources: see the Data & methods page.',
  ].join('\n')
  save(filename, new Blob([`${preamble}\n${lines.join('\n')}\n`], { type: 'text/csv;charset=utf-8' }))
}

export function downloadJson(filename: string, payload: unknown) {
  const wrapped = {
    generated_at: new Date().toISOString(),
    note: 'null means no data — never zero. Every figure traces to a source; see the Data & methods page.',
    payload,
  }
  save(filename, new Blob([JSON.stringify(wrapped, null, 2)], { type: 'application/json' }))
}
