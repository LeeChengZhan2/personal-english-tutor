import { Check, RotateCcw, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { Schemas } from '@/api/client'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Question = Schemas['QuizQuestion']

/** A lesson's quick check: pick the words for each gap and see at once whether they're right, and why. */
export function Quiz({ questions }: { questions: Question[] }) {
  const [picked, setPicked] = useState<Record<number, string>>({})
  const answered = Object.keys(picked).length
  const right = questions.filter((q, i) => picked[i] === q.answer).length
  return (
    <div className="grid gap-4">
      <ol className="grid gap-4">
        {questions.map((q, i) => (
          <QuizQuestion
            key={q.sentence}
            n={i + 1}
            question={q}
            picked={picked[i]}
            onPick={(choice) => setPicked((p) => ({ ...p, [i]: choice }))}
          />
        ))}
      </ol>
      {answered === questions.length && (
        <div className="flex flex-wrap items-center gap-3">
          <p className="font-bold" aria-live="polite">
            {right} of {questions.length} right{right === questions.length ? '. Well done!' : '.'}
          </p>
          <Button variant="outline" size="sm" onClick={() => setPicked({})}>
            <RotateCcw aria-hidden /> Try again
          </Button>
        </div>
      )}
    </div>
  )
}

function QuizQuestion({ n, question: q, picked, onPick }: { n: number; question: Question; picked?: string; onPick: (choice: string) => void }) {
  const choices = useMemo(() => mixed([q.answer, ...q.options], q.sentence), [q])
  const [before, after] = q.sentence.split('___')
  const done = picked !== undefined
  return (
    <li className="grid gap-3 rounded-xl border bg-surface p-5 shadow-e1">
      <p className="text-[17px] leading-8">
        <span className="mr-2 font-bold text-ink-2">{n}.</span>
        {before}
        {done ? (
          <ins className="x">{q.answer}</ins>
        ) : (
          <span className="inline-block min-w-16 border-b-2 border-ink-3 align-baseline">
            <span className="sr-only">gap</span>&nbsp;
          </span>
        )}
        {after}
      </p>
      <div className="flex flex-wrap gap-2">
        {choices.map((choice) => {
          const isAnswer = choice === q.answer
          const chosen = choice === picked
          return (
            <button
              key={choice}
              type="button"
              disabled={done}
              onClick={() => onPick(choice)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-lg border bg-surface px-3 py-1.5 text-[15px] font-bold',
                !done && 'hover:border-pencil hover:text-pencil',
                done && isAnswer && 'border-ok bg-ok-soft text-ok',
                done && chosen && !isAnswer && 'border-mark bg-mark-soft text-mark',
                done && !isAnswer && !chosen && 'text-ink-2',
              )}
            >
              {done && isAnswer && <Check className="size-4" aria-hidden />}
              {done && chosen && !isAnswer && <X className="size-4" aria-hidden />}
              {choice}
            </button>
          )
        })}
      </div>
      {done && (
        <p className="text-[15px]" aria-live="polite">
          <span className={cn('font-bold', picked === q.answer ? 'text-ok' : 'text-mark')}>
            {picked === q.answer ? 'Right. ' : `Not quite: it’s “${q.answer}”. `}
          </span>
          <span className="text-ink-2">{q.why}</span>
        </p>
      )}
    </li>
  )
}

/** The choices in a fixed but mixed order, so the answer isn't always first. */
function mixed(choices: string[], seed: string): string[] {
  const score = (text: string) => {
    let h = 0
    for (const ch of seed + text) h = (Math.imul(h, 31) + ch.charCodeAt(0)) | 0
    return h
  }
  return choices.toSorted((a, b) => score(a) - score(b))
}
