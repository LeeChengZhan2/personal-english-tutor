import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { ChevronRight } from 'lucide-react'
import { grammarQuery } from '@/api/queries'
import { MasteryBar, MasteryLegend } from '@/components/domain/mastery-bar'
import { EmptyState, Page, PageHeader, PageSkeleton, RouteError } from '@/components/domain/page'
import { UpdateLessonsButton } from '@/features/update/update-button'
import { fmtShort, plural } from '@/lib/format'

export const Route = createFileRoute('/_app/grammar/')({
  loader: ({ context: { queryClient } }) => queryClient.ensureQueryData(grammarQuery()),
  pendingComponent: () => <PageSkeleton />,
  errorComponent: RouteError,
  component: GrammarPage,
})

function GrammarPage() {
  const { data } = useSuspenseQuery(grammarQuery())
  const none = data.lessons.length === 0
  return (
    <Page>
      <title>Grammar · Personal English Tutor</title>
      <PageHeader
        title="Grammar"
        description="Short lessons on the grammar you get wrong most, chosen from your own messages. Start at the top."
        actions={none ? undefined : <MasteryLegend />}
      />
      {data.coming > 0 && (
        <EmptyState title={none ? 'No grammar lessons yet' : `${plural(data.coming, 'more lesson')} to write`} actions={<UpdateLessonsButton variant="default" />}>
          Update your lessons, and Claude writes a lesson for {none ? `each of your ${data.coming} most frequent grammar mistakes` : 'the grammar you now get wrong often'}.
        </EmptyState>
      )}
      {none && data.coming === 0 ? (
        <EmptyState title="No grammar lessons yet">A lesson appears once the same grammar mistake shows up a few times in your messages.</EmptyState>
      ) : (
        <ol className="grid">
          {data.lessons.map((l, i) => (
            <li key={l.pattern} className="border-b last:border-b-0">
              <Link
                to="/grammar/$patternKey"
                params={{ patternKey: l.pattern }}
                className="group -mx-3 grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 rounded-lg px-3 py-4 hover:bg-surface"
              >
                <span className="row-span-3 self-start font-display text-[22px] leading-7 font-extrabold text-ink-2 tabular-nums">{i + 1}</span>
                <span className="type-h3 group-hover:text-pencil">{l.title}</span>
                <span className="row-span-3 flex items-center gap-3">
                  <span className="grid w-28 gap-1.5 text-right">
                    <MasteryBar mastery={l.mastery} />
                    <span className="text-[13px] text-ink-2 tabular-nums">
                      {l.mastery.mastered}/{l.mastery.total} mastered
                    </span>
                  </span>
                  <ChevronRight className="size-5 text-ink-3 group-hover:text-pencil" aria-hidden />
                </span>
                <span className="text-ink-2">{l.summary}</span>
                <span className="text-sm text-ink-2">
                  {l.category_title} · {plural(l.mistakes, 'mistake')} in your messages{l.last ? ` · last ${fmtShort(l.last)}` : ''}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </Page>
  )
}
