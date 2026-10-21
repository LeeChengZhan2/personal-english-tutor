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

/** A run of a sentence: plain text, or the marked word. */
export interface Piece {
  text: string
  mark: boolean
}

/** `text` as plain and marked pieces, with the first occurrence of `word` marked. */
export function highlightPieces(text: string, word: string): Piece[] {
  const parts = splitHighlight(text, word)
  if (!parts) return [{ text, mark: false }]
  const pieces = [
    { text: parts.before, mark: false },
    { text: parts.match, mark: true },
    { text: parts.after, mark: false },
  ]
  return pieces.filter((p) => p.text)
}

/**
 * `pieces` cut before the last word, so that word can stay on one line with a button after it. A marked phrase is
 * never cut: "a <regression>?" → ["a "] and ["<regression>", "?"].
 */
export function splitLastWord(pieces: Piece[]): [Piece[], Piece[]] {
  for (let i = pieces.length - 1; i >= 0; i -= 1) {
    const piece = pieces[i]!
    const text = i === pieces.length - 1 ? piece.text.trimEnd() : piece.text
    const at = piece.mark ? -1 : text.lastIndexOf(' ')
    if (at >= 0) {
      const head = { text: piece.text.slice(0, at + 1), mark: false }
      const tail = { text: piece.text.slice(at + 1), mark: false }
      return [
        [...pieces.slice(0, i), head],
        [tail, ...pieces.slice(i + 1)].filter((p) => p.text),
      ]
    }
  }
  return [[], pieces]
}
