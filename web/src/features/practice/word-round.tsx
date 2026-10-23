import { ArrowRight, BookA, RotateCcw } from 'lucide-react'
import { useEffect, useReducer, useRef, useState } from 'react'
import { toast } from 'sonner'
import type { Schemas } from '@/api/client'
import { useAnswerWord, useFinishRound, useStartRound, type WordGroup } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Kbd } from '@/components/ui/kbd'
import { Skeleton } from '@/components/ui/skeleton'
import { useTapOnly } from '@/hooks/use-tap-only'
import { PracticeShell } from './practice-shell'
import { roundReducer, startRound } from './round'
import { RoundDone } from './round-done'
import { WordFeedback } from './word-feedback'
import { TYPE_FORM, WordQuestion } from './word-question'

const TITLES: Record<WordGroup | 'all', string> = { all: 'Word round', new: 'New words', fix: 'Typos & fixes' }

interface WordRoundProps {
  /** One of the Words page's lists; none = new words first, with a few typos & fixes. */
  group?: WordGroup
  onExit: () => void
  onAgain: () => void
}

/** A word round from start to end: asks the server for the words, then plays them. */
export function WordRound({ group, onExit, onAgain }: WordRoundProps) {
  const [tapOnly] = useTapOnly()
  const [clientId] = useState(() => crypto.randomUUID())
  const start = useStartRound()
  const asked = useRef(false)
  const title = TITLES[group ?? 'all']
  const begin = () => start.mutate({ mode: 'words', group: group ?? null, tap_only: tapOnly, client_id: clientId })
  useEffect(() => {
    if (asked.current) return
    asked.current = true
    begin()
  })

  if (start.data) {
    if (start.data.items.length === 0) return <NoWords title={title} group={group} onExit={onExit} />
    return <SavedRound round={start.data} title={title} onExit={onExit} onAgain={onAgain} />
  }
  if (start.isError) {
    return (
      <PracticeShell
        title={title}
        done={0}
        total={0}
        onEnd={onExit}
        footer={
          <>
            <Button variant="outline" onClick={onExit}>
              Back
            </Button>
            <Button onClick={begin}>
              <RotateCcw aria-hidden /> Try again
            </Button>
          </>
        }
      >
        <h1 className="type-h2">The round didn&rsquo;t start</h1>
        <p className="text-ink-2">{start.error.message}</p>
      </PracticeShell>
    )
  }
  return (
    <PracticeShell title={title} done={0} total={0} onEnd={onExit}>
      <div className="grid gap-4" aria-busy="true" aria-label="Getting your words">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-8 w-72 max-w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
    </PracticeShell>
  )
}

function SavedRound({ round, title, onExit, onAgain }: { round: Schemas['WordRound']; title: string; onExit: () => void; onAgain: () => void }) {
  const answer = useAnswerWord(round.id)
  const finish = useFinishRound(round.id)
  return (
    <RoundPlayer
      round={round}
      title={title}
      record={(itemId, given, seconds) => answer.mutateAsync({ item_id: itemId, answer: given, seconds })}
      finish={() => finish.mutateAsync()}
      onExit={onExit}
      onAgain={onAgain}
    />
  )
}

interface RoundPlayerProps {
  round: Schemas['WordRound']
  title: string
  /** Saves a scored answer; resolves with the word's new schedule. */
  record: (itemId: string, answer: string, seconds: number) => Promise<Schemas['AnswerOut']>
  /** Counts the round (called once, when there is at least one answer). */
  finish: () => Promise<Schemas['RoundScore']>
  onExit: () => void
  onAgain: () => void
}

/**
 * Plays a round: one question at a time, feedback after each answer, the score at the end. Keys: 1-4 choose,
 * Enter goes on, Esc ends the round (the answers so far are kept).
 */
export function RoundPlayer({ round, title, record, finish, onExit, onAgain }: RoundPlayerProps) {
  const [state, dispatch] = useReducer(roundReducer, round.items, startRound)
  const [saved, setSaved] = useState<Record<string, Schemas['AnswerOut']>>({})
  const [score, setScore] = useState<Schemas['RoundScore'] | null>(null)
  const shown = useRef({ at: -1, ms: 0 }) // when the question on screen appeared
  const finished = useRef(false)
  const goOn = useRef<HTMLButtonElement>(null) // Next, or Another round: focused when it appears, so Enter goes on
  const turn = state.turns[state.at]
  const given = state.given

  function finishOnce() {
    if (finished.current || state.results.length === 0) return
    finished.current = true
    finish().then(setScore, () => toast.error('This round wasn’t counted. Is the app’s server still running?'))
  }
  const finishLater = useRef(finishOnce)
  useEffect(() => {
    finishLater.current = finishOnce
  })
  useEffect(() => () => finishLater.current(), []) // leaving mid-round (the browser's Back) still counts it

  useEffect(() => {
    shown.current = { at: state.at, ms: performance.now() }
    window.scrollTo(0, 0)
  }, [state.at])
  useEffect(() => {
    if (!turn) finishOnce()
  })
  useEffect(() => {
    if (given || !turn) goOn.current?.focus()
  }, [given, turn])

  function answer(choice: string) {
    if (!turn || given) return
    const seconds = (performance.now() - shown.current.ms) / 1000
    dispatch({ type: 'answer', answer: choice })
    if (turn.retry) return
    const id = turn.item.item_id
    record(id, choice, seconds).then(
      (out) => setSaved((s) => ({ ...s, [id]: out })),
      () => toast.error('That answer wasn’t saved. Is the app’s server still running?'),
    )
  }

  function end() {
    finishOnce()
    onExit()
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return
      if (e.key === 'Escape') {
        e.preventDefault()
        end()
        return
      }
      const target = e.target instanceof HTMLElement ? e.target : null
      if (target?.closest('input, textarea')) return
      if (e.key === 'Enter' && target?.closest('button, a')) return // the focused button does its own thing
      if (!turn) return
      if (!given && turn.item.exercise !== 'type' && /^[1-9]$/.test(e.key)) {
        const option = turn.item.options[Number(e.key) - 1]
        if (option !== undefined) {
          e.preventDefault()
          answer(option)
        }
      } else if (given && e.key === 'Enter') {
        e.preventDefault()
        dispatch({ type: 'next' })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (!turn) {
    return (
      <PracticeShell
        title={title}
        done={state.turns.length}
        total={state.turns.length}
        onEnd={onExit}
        footer={
          <>
            <Button variant="outline" onClick={onExit}>
              Done
            </Button>
            <Button ref={goOn} onClick={onAgain}>
              <BookA aria-hidden /> Another round{score?.words_due ? ` · ${score.words_due} due` : ''}
            </Button>
          </>
        }
      >
        <RoundDone title={title} results={state.results} />
      </PracticeShell>
    )
  }

  const last = state.at === state.turns.length - 1
  const footer = given ? (
    <Button ref={goOn} size="lg" onClick={() => dispatch({ type: 'next' })}>
      {last ? 'Finish' : 'Next'} <ArrowRight aria-hidden />
    </Button>
  ) : turn.item.exercise === 'type' ? (
    <>
      <Button variant="ghost" size="lg" onClick={() => answer('')}>
        Show me
      </Button>
      <Button size="lg" type="submit" form={TYPE_FORM}>
        Check
      </Button>
    </>
  ) : (
    <p className="mr-auto text-sm text-ink-2">
      <span className="pointer-coarse:hidden">
        Press <Kbd>1</Kbd> to <Kbd>{turn.item.options.length}</Kbd>, or click an answer
      </span>
      <span className="pointer-fine:hidden">Tap an answer</span>
    </p>
  )

  return (
    <PracticeShell title={title} done={state.at} total={state.turns.length} onEnd={end} footer={footer}>
      <WordQuestion key={state.at} turn={turn} given={given} onAnswer={answer} />
      {given && <WordFeedback turn={turn} given={given} saved={saved[turn.item.item_id]} />}
    </PracticeShell>
  )
}

function NoWords({ title, group, onExit }: { title: string; group?: WordGroup; onExit: () => void }) {
  return (
    <PracticeShell title={title} done={0} total={0} onEnd={onExit} footer={<Button onClick={onExit}>Back</Button>}>
      <h1 className="type-h2">{group === 'new' ? 'No new words yet' : 'No words to practise yet'}</h1>
      <p className="max-w-[56ch] text-ink-2">
        Your word lists fill up when you update your lessons: Claude reads your messages for words you mistype and new
        words that say what you meant better.
      </p>
    </PracticeShell>
  )
}
