import { describe, it, expect } from 'vitest'
import { parseBreakdown, withBreakdown, total, problem, DEFAULT_ROWS } from '../breakdown'

const SCHEMA = `Return ONLY this JSON:
{
  "scores": {CV_NAMES_HERE: 0-100},
  "best_cv": "CV_NAME",
  "breakdown": {"language": 0-50, "skills": 0-10, "experience": 0-10},
  "summary": "x",
  "keyword_coverage_pct": 0-100
}`

describe('parseBreakdown', () => {
  it('reads each category and its maximum', () => {
    expect(parseBreakdown(SCHEMA)).toEqual([{ key: 'language', max: 50 }, { key: 'skills', max: 10 }, { key: 'experience', max: 10 }])
  })
  it('ignores the other 0-N ranges in the schema', () => {
    expect(parseBreakdown(SCHEMA).map((r) => r.key)).not.toContain('keyword_coverage_pct')
  })
  it('is empty without a breakdown line', () => {
    expect(parseBreakdown('{"scores": {}}')).toEqual([])
    expect(parseBreakdown(null)).toEqual([])
  })
})

describe('withBreakdown', () => {
  it('replaces only the breakdown line and keeps the comma and the rest', () => {
    const out = withBreakdown(SCHEMA, [{ key: 'role', max: 40 }, { key: 'skills', max: 60 }])
    expect(out).toContain('  "breakdown": {"role": 0-40, "skills": 0-60},\n  "summary": "x"')
    const rest = (t) => t.split('\n').filter((l) => !l.includes('"breakdown"'))
    expect(rest(out)).toEqual(rest(SCHEMA))
  })
  it('round-trips', () => {
    const rows = [{ key: 'a', max: 1 }, { key: 'b', max: 99 }]
    expect(parseBreakdown(withBreakdown(SCHEMA, rows))).toEqual(rows)
  })
  it('adds the line after best_cv when the schema has none', () => {
    const bare = '{\n  "scores": {CV_NAMES_HERE: 0-100},\n  "best_cv": "CV_NAME",\n  "summary": "x"\n}'
    expect(parseBreakdown(withBreakdown(bare, DEFAULT_ROWS))).toEqual(DEFAULT_ROWS)
  })
})

describe('problem and total', () => {
  it('sums the maxima', () => expect(total(DEFAULT_ROWS)).toBe(100))
  it('accepts a good set', () => expect(problem(DEFAULT_ROWS)).toBe(''))
  it.each([
    [[], /at least one/],
    [[{ key: 'Skills', max: 10 }], /not a valid name/],
    [[{ key: '', max: 10 }], /not a valid name/],
    [[{ key: 'a', max: 10 }, { key: 'a', max: 5 }], /twice/],
    [[{ key: 'a', max: 0 }], /maximum/],
    [[{ key: 'a', max: 2.5 }], /maximum/],
  ])('rejects %j', (rows, why) => expect(problem(rows)).toMatch(why))
})
