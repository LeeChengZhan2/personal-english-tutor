import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { GraduationCap, Play, Sparkles } from 'lucide-react'
import { z } from 'zod'
import { patternQuery, useBootstrap } from '@/api/queries'
import { SeverityBadge, StatusBadge } from '@/components/domain/badges'
import { Pager } from '@/components/domain/bits'
import { ChineseHint } from '@/components/domain/hints'
import { MasteryBar } from '@/components/domain/mastery-bar'
import { Page, PageHeader, PageSkeleton, RouteError, SectionHeader } from '@/components/domain/page'
import { ProofText } from '@/components/domain/proof-text'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { fmtShort, plural } from '@/lib/format'

export const Route = createFileRoute('/_app/mistakes/$patternKey')({
  validateSearch: z.object({ page: z.number().int().min(1).catch(1).optional() }),
  loaderDeps: ({ search }) => ({ page: search.page ?? 1 }),
  loader: ({ context: { queryClient }, params, deps }) => queryClient.ensureQueryData(patternQuery(params.patternKey, deps.page)),
  pendingComponent: () => <PageSkeleton />,
  errorComponent: RouteError,
  component: PatternPage,
})

function PatternPage() {
  const { patternKey } = Route.useParams()
  const { page = 1 } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const { data: p } = useSuspenseQuery(patternQuery(patternKey, page))
  const aiAvailable = useBootstrap().data?.ai.available ?? false

  return (
    <Page>
      <title>{`${p.title} · Personal English Tutor`}</title>
      <PageHeader
        back={{ to: '/mistakes', label: 'Mistakes' }}
        eyebrow={p.category_title}
        title={p.title}
        description={p.rule ? <span className="text-ink">{p.rule}</span> : undefined}
      />
      <div className="-mt-6 grid gap-5">
        <ChineseHint text={p.rule_zh} />
        <div className="flex flex-wrap items-center gap-3">
          <Button render={<Link to="/practice" search={{ mode: 'pattern', pattern: patternKey }} />} disabled={p.total === 0}>
            <Play className="fill-current" aria-hidden /> Practise this
          </Button>
          <Tooltip>
            <TooltipTrigger
              render={
                <Button variant="outline" disabled={!aiAvailable} render={aiAvailable ? <Link to="/practice" search={{ mode: 'generated', pattern: patternKey }} /> : undefined}>
                  <Sparkles aria-hidden /> New practice sentences
                </Button>
              }
            />
            <TooltipContent>{aiAvailable ? 'Claude writes 6 new sentences with this mistake' : 'Needs Claude (see Settings)'}</TooltipContent>
          </Tooltip>
          {p.lesson && (
            <Button variant="outline" render={<Link to="/grammar/$patternKey" params={{ patternKey }} />}>
              <GraduationCap aria-hidden /> Grammar lesson
            </Button>
          )}
          <span className="ml-auto grid w-64 gap-1.5 text-right">
            <MasteryBar mastery={p.mastery} />
            <span className="text-[13px] text-ink-2 tabular-nums">
              {p.mastery.mastered} mastered · {p.mastery.learning} learning · {p.mastery.new} new
            </span>
          </span>
        </div>
      </div>

      {p.more_examples.length > 0 && (
        <section className="grid gap-3">
          <SectionHeader title="The rule in action" />
          <ul className="grid gap-2">
            {p.more_examples.map((e) => (
              <li key={e.wrong} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[17px]">
                <del className="x">{e.wrong}</del>
                <span className="text-ink-3" aria-hidden>
                  →
                </span>
                <ins className="x">{e.right}</ins>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="grid gap-3">
        <SectionHeader title={`Your mistakes (${p.total})`} />
        <ul className="grid">
          {p.cards.map((c) => (
            <li key={c.id} className="grid gap-2 border-b py-5 last:border-b-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2">
                <SeverityBadge severity={c.severity} />
                {c.times > 1 && <span className="font-bold text-ink">{plural(c.times, 'time')}</span>}
                {c.last && <span>{fmtShort(c.last)}</span>}
                <span className="ml-auto">
                  <StatusBadge status={c.status} strength={c.strength} dueAt={c.due_at} />
                </span>
              </div>
              <ProofText as="p" className="text-[18px] leading-8" from={c.sentence} to={c.corrected} />
              {c.explain && <p className="text-ink-2">{c.explain}</p>}
              <ChineseHint text={c.explain_zh} />
            </li>
          ))}
        </ul>
        <Pager page={p.page} pages={p.pages} onChange={(next) => void navigate({ search: { page: next } })} />
      </section>
    </Page>
  )
}
