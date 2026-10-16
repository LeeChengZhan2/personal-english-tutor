import type { Schemas } from '@/api/client'
import { cn } from '@/lib/utils'

type Mastery = Pick<Schemas['Mastery'], 'total' | 'mastered' | 'learning'>

/** Mastered (green) and learning (light blue) out of the total, as one bar. */
export function MasteryBar({ mastery, className }: { mastery: Mastery; className?: string }) {
  const pct = (n: number) => (mastery.total ? (100 * n) / mastery.total : 0)
  return (
    <div
      role="img"
      aria-label={`${mastery.mastered} of ${mastery.total} mastered, ${mastery.learning} learning`}
      className={cn('flex h-2 w-full gap-[2px] overflow-hidden rounded-full bg-sunk', className)}
    >
      {mastery.mastered > 0 && <span className="h-full rounded-full bg-chart-3" style={{ width: `${pct(mastery.mastered)}%` }} />}
      {mastery.learning > 0 && <span className="h-full rounded-full bg-chart-2" style={{ width: `${pct(mastery.learning)}%` }} />}
    </div>
  )
}

export function MasteryLegend({ className }: { className?: string }) {
  return (
    <div className={cn('flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2', className)}>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-chart-3" aria-hidden /> Mastered
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-chart-2" aria-hidden /> Learning
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-sunk ring-1 ring-ink-3 ring-inset" aria-hidden /> New
      </span>
    </div>
  )
}
