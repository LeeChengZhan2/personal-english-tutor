import { ChevronLeft, ChevronRight, Copy } from 'lucide-react'
import type { ReactNode } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** A number with a label, e.g. "5 · day streak". */
export function KpiTile({ value, label, hint, className }: { value: ReactNode; label: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className={cn('grid content-start gap-1 rounded-xl border bg-surface px-5 py-4 shadow-e1', className)}>
      <span className="text-[32px] leading-9 font-bold tracking-tight">{value}</span>
      <span className="text-sm text-ink-2">{label}</span>
      {hint && <span className="text-sm text-ink-2">{hint}</span>}
    </div>
  )
}

export function CopyButton({ text, label = 'Copy', className }: { text: string; label?: string; className?: string }) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('Copied')
    } catch {
      toast.error("Couldn't copy. Select the text and press Ctrl+C.")
    }
  }
  return (
    <Button variant="ghost" size="sm" className={className} onClick={() => void copy()}>
      <Copy aria-hidden /> {label}
    </Button>
  )
}

/** Previous / next page controls for a paged list. */
export function Pager({ page, pages, onChange, className }: { page: number; pages: number; onChange: (page: number) => void; className?: string }) {
  if (pages <= 1) return null
  return (
    <nav aria-label="Pages" className={cn('flex items-center justify-between gap-3', className)}>
      <Button variant="outline" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        <ChevronLeft aria-hidden /> Previous
      </Button>
      <span className="text-sm text-ink-2 tabular-nums">
        Page {page} of {pages}
      </span>
      <Button variant="outline" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Next <ChevronRight aria-hidden />
      </Button>
    </nav>
  )
}
