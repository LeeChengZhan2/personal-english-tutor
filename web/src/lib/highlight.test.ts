import { describe, expect, it } from 'vitest'
import { splitHighlight } from './highlight'

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
