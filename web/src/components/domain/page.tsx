import { useQueryErrorResetBoundary } from '@tanstack/react-query'
import { Link, useRouter } from '@tanstack/react-router'
import { ChevronLeft, CloudOff, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  eyebrow?: ReactNode
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  back?: { to: string; label: string }
  className?: string
}

export function PageHeader({ eyebrow, title, description, actions, back, className }: PageHeaderProps) {
  return (
    <header className={cn('grid gap-3', className)}>
      {back && (
        <Link to={back.to} className="inline-flex w-fit items-center gap-1 text-sm font-bold text-pencil hover:underline">
          <ChevronLeft className="size-4" aria-hidden /> {back.label}
        </Link>
      )}
      {eyebrow && <p className="type-label text-ink-2">{eyebrow}</p>}
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="grid min-w-0 gap-2">
          <h1 className="type-h1">{title}</h1>
          {description && <p className="type-lead max-w-[62ch] text-ink-2">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}

export function SectionHeader({ title, action, className }: { title: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-baseline justify-between gap-4 border-b-2 border-ink pb-2', className)}>
      <h2 className="type-h2">{title}</h2>
      {action && <div className="text-sm font-bold text-pencil">{action}</div>}
    </div>
  )
}

/** The content column of a page: `reading` for lists of text, `wide` for dashboards. */
export function Page({ children, width = 'reading', className }: { children: ReactNode; width?: 'reading' | 'wide'; className?: string }) {
  return (
    <div className={cn('mx-auto grid w-full gap-10 px-5 py-8 md:px-10 md:py-10', width === 'wide' ? 'max-w-[1120px]' : 'max-w-[800px]', className)}>
      {children}
    </div>
  )
}

export function EmptyState({ title, children, actions, className }: { title: ReactNode; children?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <div className={cn('grid gap-3 rounded-xl border-2 border-dashed border-line p-6', className)}>
      <p className="type-h3">{title}</p>
      {children && <div className="max-w-[60ch] text-ink-2">{children}</div>}
      {actions && <div className="flex flex-wrap gap-2 pt-1">{actions}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const offline = error instanceof ApiError && error.offline
  const Icon = offline ? CloudOff : TriangleAlert
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div role="alert" className="grid gap-3 rounded-xl border border-mark/30 bg-mark-soft/50 p-6">
      <p className="flex items-center gap-2 type-h3">
        <Icon className="size-5 text-mark" aria-hidden />
        {offline ? "Can't reach the server" : "This page didn't load"}
      </p>
      <p className="text-ink-2">{offline ? 'Start the app again (start.cmd), then try again.' : message}</p>
      {onRetry && (
        <div>
          <Button variant="outline" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}
    </div>
  )
}

/** For a route's errorComponent: shows the error with a retry that reloads the route's data. */
export function RouteError({ error }: { error: unknown }) {
  const router = useRouter()
  const { reset } = useQueryErrorResetBoundary()
  return (
    <Page>
      <ErrorState
        error={error}
        onRetry={() => {
          reset()
          void router.invalidate()
        }}
      />
    </Page>
  )
}

/** Shown while a page's data loads (only if that takes more than a moment). */
export function PageSkeleton({ width = 'reading' }: { width?: 'reading' | 'wide' }) {
  return (
    <Page width={width}>
      <div className="grid gap-3" aria-busy="true" aria-label="Loading">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-5 w-1/2" />
      </div>
      <div className="grid gap-4">
        <Skeleton className="h-28 w-full rounded-xl" />
        <Skeleton className="h-28 w-full rounded-xl" />
        <Skeleton className="h-28 w-full rounded-xl" />
      </div>
    </Page>
  )
}
