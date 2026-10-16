import { useSuspenseInfiniteQuery } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { ChevronDown, PencilLine } from 'lucide-react'
import { Fragment, useState } from 'react'
import { z } from 'zod'
import type { Schemas } from '@/api/client'
import { messagesQuery, type MessageFilter } from '@/api/queries'
import { CopyButton } from '@/components/domain/bits'
import { EmptyState, Page, PageHeader, PageSkeleton, RouteError } from '@/components/domain/page'
import { ProofText } from '@/components/domain/proof-text'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { tooLongToMark } from '@/lib/diff'
import { fmtDay, fmtTime, plural } from '@/lib/format'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/_app/messages')({
  validateSearch: z.object({ filter: z.enum(['mistakes', 'all']).catch('mistakes').optional() }),
  loaderDeps: ({ search }) => ({ filter: search.filter ?? 'mistakes' }),
  loader: ({ context: { queryClient }, deps }) => queryClient.ensureInfiniteQueryData(messagesQuery(deps.filter)),
  pendingComponent: () => <PageSkeleton />,
  errorComponent: RouteError,
  component: MessagesPage,
})

function MessagesPage() {
  const { filter = 'mistakes' } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useSuspenseInfiniteQuery(messagesQuery(filter))
  const messages = data.pages.flatMap((p) => p.messages)
  const counts = data.pages[0]?.counts ?? { mistakes: 0, all: 0 }

  return (
    <Page>
      <title>Messages · Personal English Tutor</title>
      <PageHeader
        title="Messages"
        description={
          <>
            What you typed to Claude Code, with fixes marked: <del className="x">removed</del> <ins className="x">added</ins>
          </>
        }
      />
      <ToggleGroup
        value={[filter]}
        onValueChange={(value: string[]) => {
          const next = value[0] as MessageFilter | undefined
          if (next) void navigate({ search: { filter: next } })
        }}
        variant="outline"
        className="w-fit"
        aria-label="Show"
      >
        <ToggleGroupItem value="mistakes" className="h-10 px-4">
          With mistakes <span className="text-ink-2 tabular-nums">{counts.mistakes}</span>
        </ToggleGroupItem>
        <ToggleGroupItem value="all" className="h-10 px-4">
          All <span className="text-ink-2 tabular-nums">{counts.all}</span>
        </ToggleGroupItem>
      </ToggleGroup>

      {messages.length === 0 ? (
        <EmptyState title="No messages yet">Messages you type to Claude Code show up here after they are checked.</EmptyState>
      ) : (
        <div className="grid gap-4">
          {messages.map((m, i) => {
            const header = i === 0 || messages[i - 1]?.day !== m.day ? fmtDay(m.day) : null
            return (
              <Fragment key={m.id}>
                {header && <h2 className="type-label sticky top-14 z-[1] bg-paper/95 pt-4 pb-1 text-ink-2 backdrop-blur md:top-0">{header}</h2>}
                <MessageCard message={m} />
              </Fragment>
            )
          })}
          {hasNextPage && (
            <Button variant="outline" className="justify-self-center" disabled={isFetchingNextPage} onClick={() => void fetchNextPage()}>
              {isFetchingNextPage ? 'Loading…' : 'Show more'}
            </Button>
          )}
        </div>
      )}
    </Page>
  )
}

function MessageCard({ message: m }: { message: Schemas['MessageRow'] }) {
  const [expanded, setExpanded] = useState(false)
  const long = m.text.length > 420
  const changed = Boolean(m.fixed) && m.fixed !== m.text
  const tooLong = changed && tooLongToMark(m.text, m.fixed)
  return (
    <article className="grid gap-3 rounded-xl border bg-surface p-5 shadow-e1 [content-visibility:auto] [contain-intrinsic-size:auto_160px]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2">
        <span className="rounded-md bg-sunk px-2 py-0.5 font-bold">{m.source === 'app' ? 'Check writing' : m.project}</span>
        <span>{fmtTime(m.ts)}</span>
        <span>{m.issues ? plural(m.issues, 'fix', 'fixes') : 'No mistakes'}</span>
      </div>
      <div className={cn('text-[17px] leading-7 whitespace-pre-wrap', long && !expanded && 'line-clamp-6')}>
        {changed ? <ProofText from={m.text} to={m.fixed} /> : m.text}
      </div>
      {tooLong && <p className="text-sm text-ink-2">This message is too long to mark up. The corrected version is below.</p>}
      {long && (
        <button type="button" className="w-fit text-sm font-bold text-pencil hover:underline" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Show less' : 'Show all'}
        </button>
      )}
      {(m.polished || tooLong) && (
        <Collapsible>
          <div className="flex flex-wrap items-center gap-2">
            <CollapsibleTrigger render={<Button variant="ghost" size="sm" className="group/c -ml-2" />}>
              <ChevronDown className="transition-transform group-data-[panel-open]/c:rotate-180" aria-hidden />
              How a fluent writer would say it
            </CollapsibleTrigger>
            {m.polished && (
              <Button variant="ghost" size="sm" render={<Link to="/practice" search={{ mode: 'rewrite', message: m.id }} />}>
                <PencilLine aria-hidden /> Practise rewriting it
              </Button>
            )}
          </div>
          <CollapsibleContent>
            <div className="mt-2 grid gap-2 rounded-lg bg-ok-soft px-4 py-3">
              <p className="whitespace-pre-wrap">{tooLong && !m.polished ? m.fixed : m.polished}</p>
              <CopyButton text={tooLong && !m.polished ? m.fixed : m.polished} label="Copy" className="justify-self-start -ml-2" />
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}
    </article>
  )
}
