import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { BookA } from 'lucide-react'
import { z } from 'zod'
import type { Schemas } from '@/api/client'
import { wordsQuery, type WordKind } from '@/api/queries'
import { StatusBadge } from '@/components/domain/badges'
import { Pager } from '@/components/domain/bits'
import { ChineseHint, HighlightText } from '@/components/domain/hints'
import { EmptyState, Page, PageHeader, PageSkeleton, RouteError } from '@/components/domain/page'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const KINDS: Record<WordKind, { title: string; blurb: string }> = {
  spelling: { title: 'Mistyped', blurb: 'Words you often type wrong. Typing them right a few times fixes the habit.' },
  know: { title: 'Words to know', blurb: 'Words you used in the wrong form, or needed but didn’t have.' },
  clearer: { title: 'Say it clearer', blurb: 'Words and phrases that make your point sharper than what you wrote.' },
}

export const Route = createFileRoute('/_app/words')({
  validateSearch: z.object({
    kind: z.enum(['spelling', 'know', 'clearer']).catch('spelling').optional(),
    page: z.number().int().min(1).catch(1).optional(),
  }),
  loaderDeps: ({ search }) => ({ kind: search.kind ?? 'spelling', page: search.page ?? 1 }),
  loader: ({ context: { queryClient }, deps }) => queryClient.ensureQueryData(wordsQuery(deps.kind, deps.page)),
  pendingComponent: () => <PageSkeleton width="wide" />,
  errorComponent: RouteError,
  component: WordsPage,
})

function WordsPage() {
  const { kind = 'spelling', page = 1 } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const { data } = useSuspenseQuery(wordsQuery(kind, page))

  return (
    <Page width="wide">
      <title>Words · Personal English Tutor</title>
      <PageHeader
        title="Words"
        description="Your own vocabulary, from the messages you wrote."
        actions={
          <>
            <span className="text-sm text-ink-2 tabular-nums">
              {data.mastered}/{data.total} mastered
            </span>
            <Button render={<Link to="/practice" search={{ mode: 'words' }} />}>
              <BookA aria-hidden /> Word round{data.due ? ` · ${data.due} due` : ''}
            </Button>
          </>
        }
      />
      {data.total === 0 ? (
        <EmptyState title="No words yet">Your word lists fill up as your messages are checked.</EmptyState>
      ) : (
        <div className="grid gap-6">
          <Tabs value={kind} onValueChange={(value) => void navigate({ search: { kind: value as WordKind, page: 1 } })}>
            <TabsList className="h-11">
              {data.kinds.map((k) => (
                <TabsTrigger key={k.kind} value={k.kind} className="px-4 text-[15px]">
                  {KINDS[k.kind].title} <span className="text-ink-2 tabular-nums">{k.count}</span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <p className="text-ink-2">{KINDS[kind].blurb}</p>
            <Link to="/practice" search={{ mode: 'words', kind }} className="text-sm font-bold text-pencil hover:underline">
              Practise these →
            </Link>
          </div>
          <ul className="grid gap-4 lg:grid-cols-2">
            {data.words.map((w) => (
              <WordCard key={w.id} word={w} />
            ))}
          </ul>
          <Pager page={data.page} pages={data.pages} onChange={(next) => void navigate({ search: { kind, page: next } })} />
        </div>
      )}
    </Page>
  )
}

function WordCard({ word: w }: { word: Schemas['WordBrief'] }) {
  return (
    <li className="grid content-start gap-2 rounded-xl border bg-surface p-5 shadow-e1">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-display text-[24px] leading-tight font-extrabold tracking-tight">{w.word}</span>
        {w.pos && <span className="text-sm text-ink-2 italic">{w.pos}</span>}
        {w.times > 1 && <span className="text-sm font-bold text-ink-2">×{w.times}</span>}
        <span className="ml-auto">
          <StatusBadge status={w.status} strength={w.strength} dueAt={w.due_at} />
        </span>
      </div>
      <p>{w.meaning}</p>
      <ChineseHint text={w.meaning_zh} />
      {w.wrote.length > 0 && (
        <p className="text-sm text-ink-2">
          You wrote{' '}
          {w.wrote.slice(0, 3).map((x, i) => (
            <span key={x}>
              {i > 0 && ', '}
              <del className="x">{x}</del>
            </span>
          ))}
        </p>
      )}
      {w.example && <HighlightText className="text-[15px] text-ink-2 italic" text={w.example} word={w.word} />}
    </li>
  )
}
