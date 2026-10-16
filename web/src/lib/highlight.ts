export interface Highlight {
  before: string
  match: string
  after: string
}

/** `text` split around the first case-insensitive occurrence of `word` (for marking a word in its example). */
export function splitHighlight(text: string, word: string): Highlight | null {
  if (!word) return null
  const at = text.toLowerCase().indexOf(word.toLowerCase())
  if (at < 0) return null
  return { before: text.slice(0, at), match: text.slice(at, at + word.length), after: text.slice(at + word.length) }
}
