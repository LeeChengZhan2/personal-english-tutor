import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { legacyProofString } from '@/test/legacy/legacy-diff'
import { repoPath } from '@/test/paths'
import { diffParts, hasChanges, needsLeadSpace, proofSegments, type Segment } from './diff'

/** The same string format as legacyProofString: [-deleted-] {+inserted+} */
function render(segments: Segment[] | null): string | null {
  if (!segments) return null
  let out = ''
  for (const s of segments) {
    if (s.kind === 'same') {
      out += s.text
      continue
    }
    if (s.del) out += `[-${s.del}-]`
    if (s.del && s.ins) out += ' '
    if (s.ins) out += `{+${s.ins}+}`
    if (s.space) out += ' '
  }
  return out
}

const proof = (a: string, b: string) => render(proofSegments(a, b))

describe('proofSegments', () => {
  it('leaves identical text unmarked', () => {
    expect(proof('All good here.', 'All good here.')).toBe('All good here.')
    expect(hasChanges(proofSegments('All good here.', 'All good here.')!)).toBe(false)
  })

  it('marks insertions, deletions and replacements', () => {
    expect(proof('I not satisfied', "I'm not satisfied")).toBe("[-I-] {+I'm+} not satisfied")
    expect(proof('Make sure the code been removed', 'Make sure the code has been removed')).toBe(
      'Make sure the code {+has+} been removed',
    )
    expect(proof('first gua', 'first')).toBe('first[-gua-]')
  })

  it('joins two changes separated by one space', () => {
    expect(proof('Why my table has one row?', 'Why does my table have one row?')).toBe(
      'Why {+does+} my table [-has-] {+have+} one row?',
    )
    expect(proof('should allowed booking', 'should be allowed bookings')).toBe(
      'should {+be+} allowed [-booking-] {+bookings+}',
    )
  })

  it('treats punctuation and curly apostrophes as tokens', () => {
    expect(proof('Dont change it', 'Don’t change it.')).toBe('[-Dont-] {+Don’t+} change it{+.+}')
  })

  it('keeps the space before a deleted word ("read eh." shows as "read ~~eh~~", not "readeh")', () => {
    const segments = proofSegments('Hard to read eh.', 'Hard to read.')!
    const at = segments.findIndex((s) => s.kind === 'change')
    expect(segments[at]).toMatchObject({ kind: 'change', del: 'eh', lead: true })
    expect(needsLeadSpace(segments, at)).toBe(true)
    expect(needsLeadSpace(proofSegments('I not satisfied', "I'm not satisfied")!, 0)).toBe(false)
  })

  it('returns null when there is nothing to compare or the texts are too long', () => {
    expect(proofSegments('', 'something')).toBeNull()
    expect(proofSegments('something', '')).toBeNull()
    const long = 'word '.repeat(700)
    expect(diffParts(long, long + 'more')).toBeNull()
  })
})

describe('parity with the original app', () => {
  const dir = repoPath('data', 'batches')
  const hasData = existsSync(dir) && readdirSync(dir).some((f) => f.endsWith('.json'))

  it.skipIf(!hasData)('gives the same marks for every finding and message in data/batches', () => {
    let pairs = 0
    for (const name of readdirSync(dir).filter((f) => f.endsWith('.json'))) {
      const batch = JSON.parse(readFileSync(path.join(dir, name), 'utf-8')) as {
        messages?: { text: string; fixed: string }[]
        findings?: { sentence: string; corrected: string }[]
      }
      const cases: [string, string][] = [
        ...(batch.findings ?? []).map((f): [string, string] => [f.sentence, f.corrected]),
        ...(batch.messages ?? []).map((m): [string, string] => [m.text, m.fixed]),
      ]
      for (const [a, b] of cases) {
        expect(proof(a, b), a.slice(0, 60)).toBe(legacyProofString(a, b))
        pairs++
      }
    }
    expect(pairs).toBeGreaterThan(0)
  })
})
