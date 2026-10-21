import { describe, expect, it } from 'vitest'
import { highlightPieces, splitHighlight, splitLastWord } from './highlight'

describe('splitHighlight', () => {
  it('splits around the first case-insensitive match', () => {
    expect(splitHighlight('The Response is slow. A response.', 'response')).toEqual({
      before: 'The ',
      match: 'Response',
      after: ' is slow. A response.',
    })
  })

  it('returns null without a match or a word', () => {
    expect(splitHighlight('Nothing here', 'missing')).toBeNull()
    expect(splitHighlight('Nothing here', '')).toBeNull()
  })
})

const plain = (text: string) => ({ text, mark: false })
const marked = (text: string) => ({ text, mark: true })

describe('highlightPieces', () => {
  it('marks the first match only', () => {
    expect(highlightPieces('The Response is slow. A response.', 'response')).toEqual([
      plain('The '),
      marked('Response'),
      plain(' is slow. A response.'),
    ])
  })

  it('drops empty pieces, and keeps text without a match whole', () => {
    expect(highlightPieces('Redundant code', 'redundant')).toEqual([marked('Redundant'), plain(' code')])
    expect(highlightPieces('Nothing here', 'missing')).toEqual([plain('Nothing here')])
  })
})

describe('splitLastWord', () => {
  it('cuts before the last word', () => {
    expect(splitLastWord(highlightPieces('The job runs in the interim, then stops.', 'in the interim'))).toEqual([
      [plain('The job runs '), marked('in the interim'), plain(', then ')],
      [plain('stops.')],
    ])
  })

  it('keeps a marked word with what follows it', () => {
    expect(splitLastWord(highlightPieces('Why has this become a regression?', 'regression'))).toEqual([
      [plain('Why has this become a ')],
      [marked('regression'), plain('?')],
    ])
  })

  it('never cuts a marked phrase', () => {
    expect(splitLastWord(highlightPieces('List them in chronological order', 'in chronological order'))).toEqual([
      [plain('List them ')],
      [marked('in chronological order')],
    ])
  })

  it('keeps a single word whole', () => {
    expect(splitLastWord([plain('Done.')])).toEqual([[], [plain('Done.')]])
  })
})
