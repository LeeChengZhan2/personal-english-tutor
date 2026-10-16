import { useSettings } from '@/api/queries'
import { splitHighlight } from '@/lib/highlight'
import { cn } from '@/lib/utils'

/** A Simplified Chinese hint, shown only when Chinese hints are on (Settings). */
export function ChineseHint({ text, className }: { text: string | null | undefined; className?: string }) {
  const { zh } = useSettings()
  if (!zh || !text) return null
  return (
    <p lang="zh-Hans" className={cn('text-[15px] leading-6 text-ink-2', className)}>
      {text}
    </p>
  )
}

/** `text` with the first occurrence of `word` marked with a highlighter. */
export function HighlightText({ text, word, className }: { text: string; word: string; className?: string }) {
  const parts = splitHighlight(text, word)
  if (!parts) return <span className={className}>{text}</span>
  return (
    <span className={className}>
      {parts.before}
      <mark>{parts.match}</mark>
      {parts.after}
    </span>
  )
}
