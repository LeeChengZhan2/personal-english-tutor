import { describe, expect, it } from 'vitest'
import { isRight, roundReducer, startRound, typeHint, type WordItem } from './round'

function item(id: string, exercise: WordItem['exercise'], answer: string, options: string[] = []): WordItem {
  return {
    item_id: id,
    exercise,
    answer,
    options,
    gap: null,
    word: {
      id, kind: 'new', word: answer, pos: 'adjective', meaning: 'a meaning', meaning_zh: '', example: '', wrote: [],
      times: 1, last: null, level: 'B2', rewrite: '', status: 'new', strength: 0, due_at: null,
    },
  }
}

describe('isRight', () => {
  it('lets a typed word differ in case, spacing and end punctuation, but never be empty', () => {
    const phrase = item('a', 'type', 'narrow down')
    expect(isRight(phrase, '  Narrow   down. ')).toBe(true)
    expect(isRight(phrase, 'narrow')).toBe(false)
    expect(isRight(phrase, '')).toBe(false)
  })
})

describe('roundReducer', () => {
  it('asks a missed word once more at the end, with its choices moved, and scores only the first try', () => {
    let s = startRound([item('a', 'choose', 'intermittent', ['arbitrary', 'intermittent', 'redundant']), item('b', 'type', 'clarify')])
    s = roundReducer(s, { type: 'answer', answer: 'arbitrary' })
    expect(s.given).toEqual({ answer: 'arbitrary', correct: false })
    expect(s.turns.map((t) => [t.item.item_id, t.retry])).toEqual([['a', false], ['b', false], ['a', true]])
    expect(s.turns[2]?.item.options).toEqual(['intermittent', 'redundant', 'arbitrary'])
    expect(roundReducer(s, { type: 'answer', answer: 'intermittent' })).toBe(s) // one answer per question

    s = roundReducer(roundReducer(s, { type: 'next' }), { type: 'answer', answer: 'Clarify' })
    s = roundReducer(roundReducer(s, { type: 'next' }), { type: 'answer', answer: 'redundant' })
    expect(s.given?.correct).toBe(false)
    expect(s.turns).toHaveLength(3) // an extra try is never asked again
    expect(s.results.map((r) => [r.item.item_id, r.correct])).toEqual([['a', false], ['b', true]])
    expect(roundReducer(s, { type: 'next' }).at).toBe(3) // over
  })

  it('waits for an answer before going on', () => {
    const s = startRound([item('a', 'type', 'clarify')])
    expect(roundReducer(s, { type: 'next' })).toBe(s)
  })
})

describe('typeHint', () => {
  it('gives the first letter and length of a word, and the first letters of a phrase', () => {
    expect(typeHint('intermittent')).toBe('Starts with “i” · 12 letters')
    expect(typeHint('narrow down')).toBe('2 words: n… d…')
  })
})
