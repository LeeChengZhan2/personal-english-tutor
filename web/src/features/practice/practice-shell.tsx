import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'

interface PracticeShellProps {
  title: string
  /** Questions answered so far, of `total`; no bar when `total` is 0. */
  done: number
  total: number
  onEnd?: () => void
  /** The buttons at the bottom (Check, Next, ...). */
  footer?: ReactNode
  children: ReactNode
}

/** The full-screen practice page: a bar to end the round and see how far you are, the question, and the buttons. */
export function PracticeShell({ title, done, total, onEnd, footer, children }: PracticeShellProps) {
  return (
    <div className="grid min-h-svh grid-rows-[auto_minmax(0,1fr)_auto] bg-paper">
      <title>{`${title} · Personal English Tutor`}</title>
      <header className="sticky top-0 z-10 border-b bg-paper/90 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-[720px] items-center gap-3 px-3 sm:px-5">
          {onEnd && (
            <Button variant="ghost" size="icon" aria-label="End round" onClick={onEnd}>
              <X className="size-5" aria-hidden />
            </Button>
          )}
          {total > 0 ? (
            <>
              <Progress
                value={(100 * done) / total}
                aria-label="Round progress"
                className="flex-1 [&_[data-slot=progress-indicator]]:bg-pencil [&_[data-slot=progress-track]]:h-2 [&_[data-slot=progress-track]]:bg-sunk"
              />
              <span className="min-w-12 text-right text-sm font-bold text-ink-2 tabular-nums">
                {Math.min(done + 1, total)} / {total}
              </span>
            </>
          ) : (
            <span className="type-label text-ink-2">{title}</span>
          )}
        </div>
      </header>
      <main className="mx-auto grid w-full max-w-[720px] content-start gap-6 px-5 py-8 md:py-12">{children}</main>
      {footer && (
        <footer className="sticky bottom-0 border-t bg-surface/95 backdrop-blur">
          <div className="mx-auto flex min-h-[72px] w-full max-w-[720px] flex-wrap items-center justify-end gap-3 px-5 py-3">{footer}</div>
        </footer>
      )}
    </div>
  )
}
