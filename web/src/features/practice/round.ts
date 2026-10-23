// A word round as the screen plays it: the questions in order, the answer to the one on screen, and the score.
// A word answered wrong is asked once more at the end of the round; that extra try isn't scored or sent.

import type { Schemas } from '@/api/client'
import { norm } from '@/lib/answer'

export type WordItem = Schemas['WordItem']

export interface Turn {
  item: WordItem
  /** The extra try at the end of the round for a word answered wrong. */
  retry: boolean
}

export interface Given {
  /** The choice, or what was typed; '' = "Show me". */
  answer: string
  correct: boolean
}

export interface RoundState {
  turns: Turn[]
  /** The turn on screen; turns.length once the round is over. */
  at: number
  given: Given | null
  /** The scored answers, in order. */
  results: { item: WordItem; correct: boolean }[]
}

export type RoundAction = { type: 'answer'; answer: string } | { type: 'next' }

/** The right choice, or the word typed with any case, spacing and end punctuation (as the server checks it). */
export function isRight(item: WordItem, answer: string): boolean {
  const typed = norm(answer)
  return typed !== '' && typed === norm(item.answer)
}

export function startRound(items: WordItem[]): RoundState {
  return { turns: items.map((item) => ({ item, retry: false })), at: 0, given: null, results: [] }
}

export function roundReducer(state: RoundState, action: RoundAction): RoundState {
  const turn = state.turns[state.at]
  if (action.type === 'next') {
    return state.given ? { ...state, at: state.at + 1, given: null } : state
  }
  if (!turn || state.given) return state
  const correct = isRight(turn.item, action.answer)
  if (turn.retry) return { ...state, given: { answer: action.answer, correct } }
  return {
    ...state,
    given: { answer: action.answer, correct },
    results: [...state.results, { item: turn.item, correct }],
    turns: correct ? state.turns : [...state.turns, { item: retryItem(turn.item), retry: true }],
  }
}

/** The word asked again, with every choice moved up one place (so the same key isn't simply pressed again). */
function retryItem(item: WordItem): WordItem {
  const [first, ...rest] = item.options
  return first === undefined ? item : { ...item, options: [...rest, first] }
}

/** How a word to type starts: `Starts with “i” · 12 letters`, or for a phrase `2 words: n… d…`. */
export function typeHint(word: string): string {
  const parts = word.trim().split(/\s+/)
  if (parts.length > 1) return `${parts.length} words: ${parts.map((p) => `${p.charAt(0)}…`).join(' ')}`
  return `Starts with “${word.charAt(0)}” · ${word.length} letters`
}
