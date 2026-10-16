import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { ChevronRight } from 'lucide-react'
import { patternsQuery, useSettings } from '@/api/queries'
import { MasteryBar, MasteryLegend } from '@/components/domain/mastery-bar'
import { EmptyState, Page, PageHeader, PageSkeleton, RouteError } from '@/components/domain/page'
import { fmtShort, plural } from '@/lib/format'

export const Route = createFileRoute('/_app/mistakes/')({
  loader: ({ context: { queryClient } }) => queryClient.ensureQueryData(patternsQuery()),
  pendingComponent: () => <PageSkeleton />,
  errorComponent: RouteError,
  component: MistakesPage,
})

function MistakesPage() {
  const { data } = useSuspenseQuery(patternsQuery())
  const { zh } = useSettings()
  return (
    <Page>
      <title>Mistakes · Personal English Tutor</title>
      <PageHeader title="Mistakes" description="The kinds of mistakes you make, most frequent first in each area." actions={<MasteryLegend />} />
      {data.categories.length === 0 ? (
        <EmptyState title="No mistakes yet">They appear here after your messages are checked.</EmptyState>
      ) : (
        data.categories.map((cat) => (
          <section key={cat.key} className="grid gap-1">
            <div className="flex items-baseline gap-3 border-b-2 border-ink pb-2">
              <h2 className="type-h2">{cat.title}</h2>
              {zh && cat.zh && (
                <span lang="zh-Hans" className="text-ink-2">
                  {cat.zh}
                </span>
              )}
            </div>
            <ul className="grid">
              {cat.patterns.map((p) => (
                <li key={p.key} className="border-b last:border-b-0">
                  <Link
                    to="/mistakes/$patternKey"
                    params={{ patternKey: p.key }}
                    className="group grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-5 gap-y-1 rounded-lg px-3 py-4 -mx-3 hover:bg-surface"
                  >
                    <span className="type-h3 group-hover:text-pencil">{p.title}</span>
                    <span className="row-span-2 flex items-center gap-3">
                      <span className="grid w-28 gap-1.5 text-right">
                        <MasteryBar mastery={p.mastery} />
                        <span className="text-[13px] text-ink-2 tabular-nums">
                          {p.mastery.mastered}/{p.mastery.total} mastered
                        </span>
                      </span>
                      <ChevronRight className="size-5 text-ink-3 group-hover:text-pencil" aria-hidden />
                    </span>
                    <span className="text-sm text-ink-2">
                      {plural(p.times, 'time')} in your messages{p.last ? ` · last ${fmtShort(p.last)}` : ''}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </Page>
  )
}
