import type { Schemas } from '@/api/client'
import { SpeakButton } from '@/components/domain/speak-button'
import type { RoundState } from './round'

/** The end of a round: the score, a word on how it went, and the words to look at again. */
export function RoundDone({ title, results }: { title: string; results: RoundState['results'] }) {
  const right = results.filter((r) => r.correct).length
  const missed = results.filter((r) => !r.correct).map((r) => r.item.word)
  return (
    <div className="grid gap-8">
      <div className="grid gap-3">
        <p className="type-label text-ink-2">{title}</p>
        <h1 className="font-display text-[64px] leading-none font-extrabold tracking-tight tabular-nums">
          <span aria-hidden>
            {right}/{results.length}
          </span>
          <span className="sr-only">
            {right} of {results.length} right
          </span>
        </h1>
        <p className="type-lead max-w-[56ch]">{verdict(right, results.length)}</p>
      </div>
      {missed.length > 0 && (
        <section className="grid gap-3">
          <h2 className="type-h3">Look at these again</h2>
          <ul className="grid gap-3">
            {missed.map((w) => (
              <MissedWord key={w.id} word={w} />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function verdict(right: number, answered: number): string {
  if (answered > 0 && right === answered) return 'Every one right. These come back in a few days.'
  if (right >= 0.7 * answered) return 'Good round. The ones you missed come back in 10 minutes.'
  return 'Tough round. The ones you missed come back in 10 minutes, and that repetition is what makes them stick.'
}

function MissedWord({ word: w }: { word: Schemas['WordBrief'] }) {
  return (
    <li className="grid gap-1 rounded-xl border bg-surface px-5 py-4 shadow-e1">
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-lg font-bold">{w.word}</span>
        <SpeakButton text={w.word} label={w.word} inline />
        {w.pos && <span className="text-sm text-ink-2 italic">{w.pos}</span>}
      </p>
      <p className="text-ink-2">{w.meaning}</p>
    </li>
  )
}
