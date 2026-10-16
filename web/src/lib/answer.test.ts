import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { repoPath } from '@/test/paths'
import { answerKey, isExactFix, isUnchanged, norm, squash, wordMatches } from './answer'

interface Vector {
  input: string
  squash: string
  norm: string
  answer_key: string
}

// Shared with the Python tests (tests/test_text.py), so both sides compare answers the same way.
const vectors = JSON.parse(readFileSync(repoPath('tests', 'fixtures', 'text_vectors.json'), 'utf-8')) as Vector[]

describe('answer normalisation', () => {
  it('matches the shared vectors', () => {
    expect(vectors.length).toBeGreaterThan(10)
    for (const v of vectors) {
      expect(squash(v.input), v.input).toBe(v.squash)
      expect(norm(v.input), v.input).toBe(v.norm)
      expect(answerKey(v.input), v.input).toBe(v.answer_key)
    }
  })

  it('accepts a fix that differs only in spacing, quotes or the final full stop', () => {
    expect(isExactFix('I don’t  know', "I don't know.")).toBe(true)
    expect(isExactFix('i do not know', "I don't know.")).toBe(false) // capital letters matter
  })

  it('spots an answer sent back unchanged', () => {
    expect(isUnchanged('Why my table has one row ', 'Why my table has one row?')).toBe(true)
    expect(isUnchanged('Why does my table have one row?', 'Why my table has one row?')).toBe(false)
  })

  it('compares typed words loosely', () => {
    expect(wordMatches(' Satisfied. ', 'satisfied')).toBe(true)
    expect(wordMatches('statisfied', 'satisfied')).toBe(false)
  })
})
