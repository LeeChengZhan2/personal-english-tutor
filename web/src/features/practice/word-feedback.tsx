import { Check, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { Schemas } from '@/api/client'
import { LevelBadge, StatusBadge } from '@/components/domain/badges'
import { ChineseHint, HighlightText } from '@/components/domain/hints'
import { SpeakButton } from '@/components/domain/speak-button'
import { WordSource } from '@/components/domain/word-source'
import { cn } from '@/lib/utils'
import type { Given, Turn } from './round'

/**
 * After an answer: right or not, then the whole word (meaning, Chinese, where it comes from in your messages, an
 * example) and when it comes back. `saved` is the server's answer: the word's new schedule.
 */
export function WordFeedback({ turn, given, saved }: { turn: Turn; given: Given; saved?: Schemas['AnswerOut'] }) {
  const w = turn.item.word
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    // braces: Edge's scrollIntoView returns a promise, and an effect may only return a cleanup function
    ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [])
  return (
    <section
      ref={ref}
      role="status"
      aria-live="polite"
      className={cn(
        'grid scroll-mt-20 scroll-mb-24 gap-4 rounded-xl border p-5', // clear of the bars at the top and bottom
        given.correct ? 'border-ok/40 bg-ok-soft' : 'border-mark/40 bg-mark-soft',
      )}
    >
      <div className="grid gap-1">
        <p className={cn('flex items-center gap-2 text-lg font-bold', given.correct ? 'text-ok' : 'text-mark')}>
          {given.correct ? <Check className="size-5" aria-hidden /> : <X className="size-5" aria-hidden />}
          {given.correct ? 'Right' : 'Not quite'}
        </p>
        {!given.correct && turn.item.exercise === 'type' && given.answer.trim() && (
          <p>
            You typed <del className="x">{given.answer.trim()}</del>
          </p>
        )}
      </div>
      <div className="grid gap-2 rounded-lg bg-surface p-4 shadow-e1">
        <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-display text-[26px] leading-tight font-extrabold tracking-tight [overflow-wrap:anywhere]">{w.word}</span>
          <SpeakButton text={w.word} label={w.word} className="-ml-2 self-center" />
          {w.pos && <span className="text-sm text-ink-2 italic">{w.pos}</span>}
          <LevelBadge level={w.level} />
        </p>
        <p>{w.meaning}</p>
        <ChineseHint text={w.meaning_zh} always={w.kind === 'new'} />
        <WordSource word={w} max={1} />
        {w.example && (
          <HighlightText
            className="text-[15px] text-ink-2 italic"
            text={w.example}
            word={w.word}
            end={<SpeakButton text={w.example} label="the example" inline />}
          />
        )}
      </div>
      <div className="min-h-5 text-sm text-ink-2">
        {/* the line's room is kept while the server answers, so the box doesn't grow after it scrolled into view */}
        {turn.retry ? (
          <p>An extra try: it isn&rsquo;t scored, and the word keeps its place in your schedule.</p>
        ) : (
          saved && <StatusBadge status={saved.status} strength={saved.strength} dueAt={saved.due_at} />
        )}
      </div>
    </section>
  )
}
