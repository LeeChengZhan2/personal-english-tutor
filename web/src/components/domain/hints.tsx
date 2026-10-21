import { Fragment, type ReactNode } from 'react'
import { useSettings } from '@/api/queries'
import { highlightPieces, type Piece, splitLastWord } from '@/lib/highlight'
import { cn } from '@/lib/utils'

/** A Simplified Chinese hint, shown only when Chinese hints are on (Settings), or `always` (a new word's meaning). */
export function ChineseHint({ text, always = false, className }: { text: string | null | undefined; always?: boolean; className?: string }) {
  const { zh } = useSettings()
  if ((!zh && !always) || !text) return null
  return (
    <p lang="zh-Hans" className={cn('text-[15px] leading-6 text-ink-2', className)}>
      {text}
    </p>
  )
}

/**
 * `text` with the first occurrence of `word` marked with a highlighter. `end` (a small button) stays on one line with
 * the last word: browsers would otherwise let it wrap onto a line of its own.
 */
export function HighlightText({ text, word, end, className }: { text: string; word: string; end?: ReactNode; className?: string }) {
  const pieces = highlightPieces(text, word)
  if (!end) {
    return (
      <span className={className}>
        <Pieces pieces={pieces} />
      </span>
    )
  }
  const [head, tail] = splitLastWord(pieces)
  return (
    <span className={className}>
      <Pieces pieces={head} />
      <span className="whitespace-nowrap">
        <Pieces pieces={tail} />
        {end}
      </span>
    </span>
  )
}

function Pieces({ pieces }: { pieces: Piece[] }) {
  return pieces.map((piece, i) => (piece.mark ? <mark key={i}>{piece.text}</mark> : <Fragment key={i}>{piece.text}</Fragment>))
}
