import { Check, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { Schemas } from '@/api/client'
import { LevelBadge } from '@/components/domain/badges'
import { ChineseHint, HighlightText } from '@/components/domain/hints'
import { SpeakButton } from '@/components/domain/speak-button'
import { Input } from '@/components/ui/input'
import { canSpeak } from '@/lib/speech'
import { cn } from '@/lib/utils'
import { typeHint, type Given, type Turn, type WordItem } from './round'

/** The form of a typing question, so the Check button in the footer can submit it. */
export const TYPE_FORM = 'type-answer'

const LIST_LABEL: Record<Schemas['WordBrief']['kind'], string> = {
  new: 'New word',
  spelling: 'Spelling',
  know: 'Word to know',
  clearer: 'Say it clearer',
}

/** The question on screen: what to do, the word or the sentence with a gap, and the choices or a box to type in. */
export function WordQuestion({ turn, given, onAnswer }: { turn: Turn; given: Given | null; onAnswer: (answer: string) => void }) {
  const { item, retry } = turn
  const w = item.word
  return (
    <div className="grid gap-6">
      <div className="grid gap-2">
        <p className="flex flex-wrap items-center gap-2">
          <span className="type-label text-pencil">{LIST_LABEL[w.kind]}</span>
          <LevelBadge level={w.level} />
          {retry && <span className="rounded-md bg-amber-soft px-2 py-0.5 text-[13px] font-bold text-amber">Once more</span>}
        </p>
        <h1 className="type-h2">{prompt(item)}</h1>
      </div>
      {item.exercise === 'meaning' ? <ShownWord word={w} /> : <Sentence item={item} filled={given !== null} />}
      <Hints item={item} />
      {item.exercise === 'type' ? (
        <TypeBox given={given} onAnswer={onAnswer} />
      ) : (
        <Choices options={item.options} answer={item.answer} given={given} onPick={onAnswer} />
      )}
    </div>
  )
}

function prompt({ exercise, gap, word }: WordItem): string {
  if (exercise === 'meaning') return 'What does it mean?'
  if (exercise === 'type') return gap ? 'Type the missing word.' : 'Type the word.'
  if (word.kind === 'spelling') return 'Which spelling is right?'
  if (!gap) return 'Which word means this?'
  return gap.source === 'rewrite' || word.kind === 'clearer' ? 'Which word says it better?' : 'Which word fits?'
}

/** A meaning question: the word itself, and an example that uses it. */
function ShownWord({ word: w }: { word: Schemas['WordBrief'] }) {
  return (
    <div className="grid gap-3">
      <p className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-display text-[40px] leading-tight font-extrabold tracking-tight [overflow-wrap:anywhere]">{w.word}</span>
        <SpeakButton text={w.word} label={w.word} className="-ml-2 self-center" />
        {w.pos && <span className="text-ink-2 italic">{w.pos}</span>}
      </p>
      {w.example && <HighlightText className="type-lead text-ink-2" text={w.example} word={w.word} />}
    </div>
  )
}

/** The sentence with the word taken out; once answered, the word is put back. */
function Sentence({ item, filled }: { item: WordItem; filled: boolean }) {
  const { gap } = item
  if (!gap) return null
  return (
    <p className="type-sentence">
      {gap.before}
      {filled ? (
        <ins className="x">{gap.match}</ins>
      ) : (
        <span className="mx-0.5 inline-block w-28 border-b-2 border-ink-3 align-baseline">
          <span className="sr-only">blank</span>&nbsp;
        </span>
      )}
      {gap.after}
    </p>
  )
}

/** What helps to answer: what the learner wrote instead, the meaning, how a typed word starts, how it sounds. */
function Hints({ item }: { item: WordItem }) {
  const { exercise, gap, word: w } = item
  const insteadOf = exercise !== 'meaning' && (gap?.source === 'rewrite' || w.kind === 'clearer') ? w.wrote[0] : undefined
  const meaning = exercise === 'type' || (exercise === 'choose' && (w.kind === 'spelling' || !gap))
  const listen = exercise !== 'meaning' && w.kind === 'spelling' && canSpeak() // hearing it doesn't give away the spelling
  if (!insteadOf && !meaning && !listen) return null
  return (
    <div className="grid gap-1.5 text-[17px]">
      {insteadOf && (
        <p className="text-ink-2">
          Instead of <q>{insteadOf}</q>
        </p>
      )}
      {meaning && (
        <p>
          <span className="font-bold text-ink-2">Meaning: </span>
          {w.meaning}
        </p>
      )}
      {exercise === 'type' && <ChineseHint text={w.meaning_zh} />}
      {exercise === 'type' && <p className="text-ink-2">{typeHint(w.word)}</p>}
      {listen && (
        <p className="flex items-center gap-1 text-ink-2">
          <SpeakButton text={w.word} label="the word" className="-ml-2" /> Listen to the word
        </p>
      )}
    </div>
  )
}

/** The choices, numbered for the keyboard; once answered, the right one is green and a wrong pick red. */
function Choices({ options, answer, given, onPick }: { options: string[]; answer: string; given: Given | null; onPick: (choice: string) => void }) {
  return (
    <div className="grid gap-3">
      {options.map((option, i) => {
        const right = given !== null && option === answer
        const picked = given?.answer === option
        return (
          <button
            key={option}
            type="button"
            disabled={given !== null}
            onClick={() => onPick(option)}
            className={cn(
              'flex min-h-14 items-center gap-4 rounded-xl border bg-surface px-4 py-3 text-left text-[17px] leading-6 shadow-e1 transition-colors',
              given === null && 'hover:border-pencil hover:bg-pencil-soft',
              right && 'border-ok bg-ok-soft',
              picked && !right && 'border-mark bg-mark-soft',
              given !== null && !right && !picked && 'text-ink-2',
            )}
          >
            <span
              aria-hidden
              className={cn(
                'grid size-7 shrink-0 place-items-center rounded-md border bg-paper text-sm font-bold text-ink-2 tabular-nums',
                right && 'border-ok text-ok',
                picked && !right && 'border-mark text-mark',
              )}
            >
              {i + 1}
            </span>
            <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{option}</span>
            {right && <Check className="size-5 shrink-0 text-ok" aria-hidden />}
            {picked && !right && <X className="size-5 shrink-0 text-mark" aria-hidden />}
            {right && <span className="sr-only">(the right answer)</span>}
            {picked && !right && <span className="sr-only">(your answer)</span>}
          </button>
        )
      })}
    </div>
  )
}

/** The box to type the word in, ready for typing. Enter or the Check button submits it; an empty box isn't sent. */
function TypeBox({ given, onAnswer }: { given: Given | null; onAnswer: (answer: string) => void }) {
  const [text, setText] = useState('')
  const box = useRef<HTMLInputElement>(null)
  useEffect(() => {
    box.current?.focus()
  }, [])
  function submit(e: FormEvent) {
    e.preventDefault()
    if (given === null && text.trim()) onAnswer(text)
  }
  return (
    <form id={TYPE_FORM} onSubmit={submit}>
      <label htmlFor="typed-word" className="sr-only">
        Your answer
      </label>
      <Input
        ref={box}
        id="typed-word"
        value={given ? given.answer : text}
        onChange={(e) => setText(e.target.value)}
        readOnly={given !== null}
        aria-invalid={given !== null && !given.correct}
        autoComplete="off"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        placeholder="Type here"
        className="h-14 rounded-xl bg-surface px-4 text-[20px] md:text-[20px] dark:bg-surface"
      />
    </form>
  )
}
