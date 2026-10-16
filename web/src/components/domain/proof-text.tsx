import { Fragment, memo, useMemo } from 'react'
import { needsLeadSpace, proofSegments } from '@/lib/diff'
import { cn } from '@/lib/utils'

interface ProofTextProps {
  /** What the learner wrote. */
  from: string
  /** The corrected text. */
  to: string
  className?: string
  as?: 'span' | 'p' | 'div'
}

/** What the learner wrote, with deletions struck through in red and insertions in blue pencil.
 * When the texts are too long to compare, the original is shown as written (never the corrected text). */
export const ProofText = memo(function ProofText({ from, to, className, as: Tag = 'span' }: ProofTextProps) {
  const segments = useMemo(() => proofSegments(from, to), [from, to])
  if (!segments) return <Tag className={cn('[overflow-wrap:anywhere]', className)}>{from}</Tag>
  return (
    <Tag className={cn('[overflow-wrap:anywhere]', className)}>
      {segments.map((s, i) =>
        s.kind === 'same' ? (
          <Fragment key={i}>{s.text}</Fragment>
        ) : (
          <Fragment key={i}>
            {needsLeadSpace(segments, i) ? ' ' : null}
            {s.del && (
              <del className="x">
                <span className="sr-only">remove </span>
                {s.del}
              </del>
            )}
            {s.del && s.ins ? ' ' : null}
            {s.ins && (
              <ins className="x">
                <span className="sr-only">add </span>
                {s.ins}
              </ins>
            )}
            {s.space ? ' ' : null}
          </Fragment>
        ),
      )}
    </Tag>
  )
})
