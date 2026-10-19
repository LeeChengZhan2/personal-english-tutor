import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { BookA } from 'lucide-react'
import { z } from 'zod'
import type { Schemas } from '@/api/client'
import { wordsQuery, type WordGroup } from '@/api/queries'
import { LevelBadge, StatusBadge } from '@/components/domain/badges'
import { Pager } from '@/components/domain/bits'
import { ChineseHint, HighlightText } from '@/components/domain/hints'
import { EmptyState, Page, PageHeader, PageSkeleton, RouteError } from '@/components/domain/page'
import { WordSource } from '@/components/domain/word-source'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { UpdateLessonsButton } from '@/features/update/update-button'

const GROUPS: Record<WordGroup, { title: string; blurb: string; empty: string; emptyText: string }> = {
  new: {
    title: 'New words',
    blurb: 'Words you haven’t used yet, picked from your own messages. Each one says something you wrote more clearly or more professionally.',
    empty: 'No new words yet',
    emptyText: 'Update your lessons, and Claude reads your messages for words you haven’t used yet that say what you meant better.',
  },
  fix: {
    title: 'Typos & fixes',
    blurb: 'Words you already know but typed or used wrong: spelling slips, wrong word forms and small fixes.',
    empty: 'Nothing to fix yet',
    emptyText: 'Words you mistype or use in the wrong form show up here after your messages are checked.',
  },
}

export const Route = createFileRoute('/_app/words')({
  validateSearch: z.object({
    group: z.enum(['new', 'fix']).catch('new').optional(),
    page: z.number().int().min(1).catch(1).optional(),
  }),
  loaderDeps: ({ search }) => ({ group: search.group ?? 'new', page: search.page ?? 1 }),
  loader: ({ context: { queryClient }, deps }) => queryClient.ensureQueryData(wordsQuery(deps.group, deps.page)),
  pendingComponent: () => <PageSkeleton width="wide" />,
  errorComponent: RouteError,
  component: WordsPage,
})

function WordsPage() {
  const { group = 'new', page = 1 } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const { data } = useSuspenseQuery(wordsQuery(group, page))
  const info = GROUPS[group]

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
          <Tabs value={group} onValueChange={(value) => void navigate({ search: { group: value as WordGroup, page: 1 } })}>
            <TabsList className="h-11">
              {data.groups.map((g) => (
                <TabsTrigger key={g.group} value={g.group} className="px-4 text-[15px]">
                  {GROUPS[g.group].title} <span className="text-ink-2 tabular-nums">{g.count}</span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <p className="max-w-[75ch] text-ink-2">{info.blurb}</p>
            {data.total_in_group > 0 && (
              <Link to="/practice" search={{ mode: 'words', group }} className="text-sm font-bold text-pencil hover:underline">
                Practise these →
              </Link>
            )}
          </div>
          {data.total_in_group === 0 ? (
            <EmptyState title={info.empty} actions={<UpdateLessonsButton variant="default" />}>
              {info.emptyText}
            </EmptyState>
          ) : (
            <>
              <ul className="grid gap-4 lg:grid-cols-2">
                {data.words.map((w) => (
                  <WordCard key={w.id} word={w} />
                ))}
              </ul>
              <Pager page={data.page} pages={data.pages} onChange={(next) => void navigate({ search: { group, page: next } })} />
            </>
          )}
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
        <LevelBadge level={w.level} />
        {w.times > 1 && <span className="text-sm font-bold text-ink-2">×{w.times}</span>}
        <span className="ml-auto">
          <StatusBadge status={w.status} strength={w.strength} dueAt={w.due_at} />
        </span>
      </div>
      <p>{w.meaning}</p>
      <ChineseHint text={w.meaning_zh} always={w.kind === 'new'} />
      <WordSource word={w} />
      {w.example && <HighlightText className="text-[15px] text-ink-2 italic" text={w.example} word={w.word} />}
    </li>
  )
}
