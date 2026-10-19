import type { Schemas } from '@/api/client'
import { HighlightText } from './hints'

/**
 * Where a word comes from in your messages. A new word: the plainer words it replaces, and your sentence
 * rewritten with it. A typo or fix: what you typed, struck through.
 */
export function WordSource({ word: w, max = 3 }: { word: Schemas['WordBrief']; max?: number }) {
  const wrote = w.wrote.slice(0, max)
  if (w.kind !== 'new') {
    if (!wrote.length) return null
    return (
      <p className="text-sm text-ink-2">
        You wrote{' '}
        {wrote.map((x, i) => (
          <span key={x}>
            {i > 0 && ', '}
            <del className="x">{x}</del>
          </span>
        ))}
      </p>
    )
  }
  return (
    <>
      {wrote.length > 0 && <p className="text-sm text-ink-2">Instead of {wrote.map((x) => `“${x}”`).join(', ')}</p>}
      {w.rewrite && (
        <p className="text-[15px]">
          <span className="font-bold text-ink-2">Better: </span>
          <HighlightText text={w.rewrite} word={w.word} />
        </p>
      )}
    </>
  )
}
