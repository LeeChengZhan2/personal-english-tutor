import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { Lightbulb, Play, Strikethrough } from 'lucide-react'
import { grammarLessonQuery } from '@/api/queries'
import { ChineseHint } from '@/components/domain/hints'
import { MasteryBar } from '@/components/domain/mastery-bar'
import { Page, PageHeader, PageSkeleton, RouteError, SectionHeader } from '@/components/domain/page'
import { ProofText } from '@/components/domain/proof-text'
import { Button } from '@/components/ui/button'
import { Quiz } from '@/features/grammar/quiz'

export const Route = createFileRoute('/_app/grammar/$patternKey')({
  loader: ({ context: { queryClient }, params }) => queryClient.ensureQueryData(grammarLessonQuery(params.patternKey)),
  pendingComponent: () => <PageSkeleton />,
  errorComponent: RouteError,
  component: LessonPage,
})

function LessonPage() {
  const { patternKey } = Route.useParams()
  const { data: l } = useSuspenseQuery(grammarLessonQuery(patternKey))

  return (
    <Page>
      <title>{`${l.title} · Personal English Tutor`}</title>
      <PageHeader
        back={{ to: '/grammar', label: 'Grammar' }}
        eyebrow={l.category_title}
        title={l.title}
        description={<span className="text-ink">{l.summary}</span>}
      />
      <div className="-mt-6 grid gap-5">
        <ChineseHint text={l.summary_zh} />
        <div className="flex flex-wrap items-center gap-3">
          <Button render={<Link to="/practice" search={{ mode: 'pattern', pattern: patternKey }} />} disabled={l.mistakes === 0}>
            <Play className="fill-current" aria-hidden /> Practise this
          </Button>
          <Button variant="outline" render={<Link to="/mistakes/$patternKey" params={{ patternKey }} />}>
            <Strikethrough aria-hidden /> Your mistakes ({l.mistakes})
          </Button>
          <span className="ml-auto grid w-64 gap-1.5 text-right">
            <MasteryBar mastery={l.mastery} />
            <span className="text-[13px] text-ink-2 tabular-nums">
              {l.mastery.mastered} mastered · {l.mastery.learning} learning · {l.mastery.new} new
            </span>
          </span>
        </div>
      </div>

      {l.your_habit && (
        <section className="grid gap-2 rounded-xl border border-pencil-line bg-pencil-soft p-5">
          <p className="type-label text-pencil">Why this lesson is for you</p>
          <p className="text-[17px]">{l.your_habit}</p>
        </section>
      )}

      <section className="grid gap-4">
        <SectionHeader title="The rules" />
        <ol className="grid gap-4">
          {l.rules.map((r, i) => (
            <li key={r.rule} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-3">
              <span className="grid size-8 place-items-center rounded-full bg-pencil font-bold text-pencil-ink" aria-hidden>
                {i + 1}
              </span>
              <div className="grid gap-1 pt-0.5">
                <p className="text-[17px] font-bold">{r.rule}</p>
                {r.example && <p className="text-ink-2 italic">{r.example}</p>}
              </div>
            </li>
          ))}
        </ol>
      </section>

      {l.examples.length > 0 && (
        <section className="grid gap-4">
          <SectionHeader title="More examples" />
          <ul className="grid gap-3">
            {l.examples.map((e) => (
              <li key={e.sentence} className="grid gap-0.5 border-l-2 border-pencil-line pl-4">
                <p className="text-[17px]">{e.sentence}</p>
                {e.note && <p className="text-sm text-ink-2">{e.note}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {l.from_you.length > 0 && (
        <section className="grid gap-3">
          <SectionHeader title="From your messages" action={<Link to="/mistakes/$patternKey" params={{ patternKey }}>All {l.mistakes}</Link>} />
          <ul className="grid">
            {l.from_you.map((e) => (
              <li key={e.sentence} className="border-b py-3 last:border-b-0">
                <ProofText as="p" className="text-[17px] leading-8" from={e.sentence} to={e.corrected} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {l.watch_out.length > 0 && (
        <section className="grid gap-4">
          <SectionHeader title="Watch out" />
          <ul className="grid gap-3">
            {l.watch_out.map((w) => (
              <li key={w.wrong} className="grid gap-1">
                <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[17px]">
                  <del className="x">{w.wrong}</del>
                  <span className="text-ink-3" aria-hidden>
                    →
                  </span>
                  <ins className="x">{w.right}</ins>
                </p>
                {w.why && <p className="text-sm text-ink-2">{w.why}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {l.quiz.length > 0 && (
        <section className="grid gap-4">
          <SectionHeader title="Quick check" />
          <Quiz questions={l.quiz} />
        </section>
      )}

      {l.tip && (
        <section className="flex gap-3 rounded-xl border bg-surface p-5 shadow-e1">
          <Lightbulb className="mt-0.5 size-5 shrink-0 text-amber" aria-hidden />
          <div className="grid gap-1">
            <p className="font-bold">{l.tip}</p>
            <ChineseHint text={l.tip_zh} />
          </div>
        </section>
      )}
    </Page>
  )
}
