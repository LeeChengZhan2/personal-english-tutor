import { Check } from 'lucide-react'
import type { Schemas } from '@/api/client'
import { useNow } from '@/hooks/use-now'
import { fromNow } from '@/lib/format'
import { cn } from '@/lib/utils'

type Severity = Schemas['CardRow']['severity']
type Status = Schemas['CardRow']['status']

const SEVERITY: Record<Exclude<Severity, 'error'>, { label: string; className: string }> = {
  unnatural: { label: 'Unnatural', className: 'bg-amber-soft text-amber' },
  style: { label: 'Style', className: 'bg-sunk text-ink-2' },
  typo: { label: 'Typo', className: 'bg-sunk text-ink-2' },
}

/** A small tag for anything that isn't a plain mistake ("Unnatural", "Style", "Typo"). */
export function SeverityBadge({ severity }: { severity: Severity }) {
  if (severity === 'error') return null
  const s = SEVERITY[severity]
  return <span className={cn('rounded-md px-2 py-0.5 text-[13px] font-bold', s.className)}>{s.label}</span>
}

/** A new word's CEFR level (B2, C1, C2): how advanced it is. */
export function LevelBadge({ level }: { level: string | null | undefined }) {
  if (!level) return null
  return (
    <span title={`CEFR level ${level}`} className="rounded-md bg-pencil-soft px-2 py-0.5 text-[13px] font-bold text-pencil">
      <span className="sr-only">Level </span>
      {level}
    </span>
  )
}

/** How well a card is known: five dots, filled as it moves towards mastered. */
export function StrengthDots({ strength, mastered = false }: { strength: number; mastered?: boolean }) {
  return (
    <span aria-hidden className="inline-flex items-center gap-[3px]">
      {Array.from({ length: 5 }, (_, i) => (
        <span
          key={i}
          className={cn(
            'size-[7px] rounded-full',
            i < strength ? (mastered ? 'bg-ok' : 'bg-pencil') : 'bg-transparent ring-1 ring-ink-3 ring-inset',
          )}
        />
      ))}
    </span>
  )
}

/** New / Learning (with strength and when it comes back) / Mastered. */
export function StatusBadge({ status, strength, dueAt }: { status: Status; strength: number; dueAt?: string | null }) {
  if (status === 'new') {
    return <span className="rounded-md border px-2 py-0.5 text-[13px] font-bold text-ink-2">New</span>
  }
  if (status === 'mastered') {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-ok-soft px-2 py-0.5 text-[13px] font-bold text-ok">
        <Check className="size-3.5" aria-hidden /> Mastered
      </span>
    )
  }
  return <LearningBadge strength={strength} dueAt={dueAt} />
}

function LearningBadge({ strength, dueAt }: { strength: number; dueAt?: string | null }) {
  const now = useNow()
  const due = dueAt ? new Date(dueAt).getTime() : 0
  const when = !dueAt || due <= now ? 'due now' : `back ${fromNow(dueAt, now)}`
  return (
    <span className="inline-flex items-center gap-2 text-[13px] font-bold text-ink-2">
      <StrengthDots strength={strength} />
      <span>
        <span className="sr-only">Learning, strength {strength} of 5, </span>
        {when}
      </span>
    </span>
  )
}
