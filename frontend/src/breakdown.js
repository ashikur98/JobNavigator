// The score breakdown a Full report is marked out of: the `"breakdown": {"skills": 0-20, ...}` line
// of the Full output schema. The Settings editor reads that line into rows and writes it back, so the
// schema stays the one source of truth (the scorer reads the same line to record each category's scale).

const LINE = /([ \t]*)"breakdown"\s*:\s*\{[^}]*\}(,?)/
const PAIR = /"(\w+)"\s*:\s*(?:\d+\s*-\s*)?(\d+)/g

export const DEFAULT_ROWS = [
  { key: 'skills', max: 20 }, { key: 'experience', max: 20 }, { key: 'domain', max: 20 },
  { key: 'role', max: 20 }, { key: 'requirements', max: 20 },
]

// [{key, max}] from a schema string; [] when it has no breakdown line.
export function parseBreakdown(schema) {
  const m = LINE.exec(String(schema || ''))
  if (!m) return []
  return [...m[0].matchAll(PAIR)].map(([, key, max]) => ({ key, max: Number(max) }))
}

// The schema with its breakdown line replaced (or added after "best_cv", or at the top level start).
export function withBreakdown(schema, rows) {
  const text = String(schema || '')
  const body = rows.map((r) => `"${r.key}": 0-${r.max}`).join(', ')
  const m = LINE.exec(text)
  if (m) return text.replace(LINE, `${m[1]}"breakdown": {${body}}${m[2]}`)
  const at = /("best_cv"\s*:\s*"[^"]*",?)/.exec(text)
  if (at) return text.replace(at[1], `${at[1]}\n  "breakdown": {${body}},`)
  return text
}

export const total = (rows) => rows.reduce((n, r) => n + (Number(r.max) || 0), 0)

// '' when the rows can be saved, else the reason they cannot.
export function problem(rows) {
  if (!rows.length) return 'Add at least one category'
  const seen = new Set()
  for (const r of rows) {
    if (!/^[a-z][a-z0-9_]*$/.test(r.key)) return `"${r.key || ''}" is not a valid name — use lowercase letters, digits and _`
    if (seen.has(r.key)) return `"${r.key}" appears twice`
    seen.add(r.key)
    if (!Number.isInteger(Number(r.max)) || Number(r.max) < 1) return `"${r.key}" needs a whole-number maximum of 1 or more`
  }
  return ''
}
