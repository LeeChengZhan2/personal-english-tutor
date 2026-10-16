// How typed answers are compared. Same rules as the Python side (coach/store.py: squash, norm, answer_key);
// both are checked against tests/fixtures/text_vectors.json.

const straightQuotes = (t: string) => t.replace(/[’‘]/g, "'").replace(/[“”]/g, '"')

/** Whitespace-insensitive, case-sensitive. */
export const squash = (t: string | null | undefined): string => String(t ?? '').replace(/\s+/g, ' ').trim()

/** Loose form for words: quotes, spacing, case and punctuation at the ends don't matter. */
export const norm = (t: string | null | undefined): string =>
  squash(straightQuotes(String(t ?? '')))
    .replace(/^[.!?,;:]+|[.!?,;:]+$/g, '')
    .trim()
    .toLowerCase()

/** A typed sentence: spacing, curly quotes and a final .!? don't matter; capital letters do. */
export const answerKey = (t: string | null | undefined): string =>
  squash(straightQuotes(String(t ?? '')))
    .replace(/[.!?]+$/g, '')
    .trim()

/** The learner typed the expected correction. */
export const isExactFix = (answer: string, corrected: string): boolean => answerKey(answer) === answerKey(corrected)

/** The learner sent the sentence back without changing it. */
export const isUnchanged = (answer: string, original: string): boolean => answerKey(answer) === answerKey(original)

/** Two words are the same word (typing exercises). */
export const wordMatches = (typed: string, expected: string): boolean => norm(typed) === norm(expected)
