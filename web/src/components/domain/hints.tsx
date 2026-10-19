import { useSettings } from '@/api/queries'
import { splitHighlight } from '@/lib/highlight'
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
