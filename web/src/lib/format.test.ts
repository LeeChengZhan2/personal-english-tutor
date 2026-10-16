import { describe, expect, it } from 'vitest'
import { fmtDay, fmtShort, fromNow, greeting, percent, plural, toDate } from './format'

describe('format', () => {
  it('reads calendar days as local dates', () => {
    const d = toDate('2026-10-16')
    expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 9, 16])
    expect(fmtDay('2026-10-16')).toBe('Fri 16 Oct')
    expect(fmtShort('2026-10-16')).toBe('16 Oct')
    expect(fmtDay(null)).toBe('')
  })

  it('counts in plain words', () => {
    expect(plural(1, 'card')).toBe('1 card')
    expect(plural(3, 'card')).toBe('3 cards')
    expect(plural(2, 'fix', 'fixes')).toBe('2 fixes')
    expect(percent(7, 8)).toBe('88%')
    expect(percent(0, 0)).toBe('–')
  })

  it('says when things happen', () => {
    const now = new Date(2026, 9, 16, 9).getTime()
    expect(fromNow(new Date(now + 3 * 86_400_000).toISOString(), now)).toBe('in 3 days')
    expect(fromNow(new Date(now - 2 * 3_600_000).toISOString(), now)).toBe('2 hours ago')
    expect(greeting(new Date(2026, 9, 16, 9))).toBe('Good morning')
    expect(greeting(new Date(2026, 9, 16, 15))).toBe('Good afternoon')
  })
})
