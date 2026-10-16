import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useState, type ReactNode } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ReferenceLine, XAxis, YAxis } from 'recharts'
import type { Schemas } from '@/api/client'
import { progressQuery, useSettings } from '@/api/queries'
import { KpiTile } from '@/components/domain/bits'
import { MasteryBar, MasteryLegend } from '@/components/domain/mastery-bar'
import { Page, PageHeader, PageSkeleton, RouteError, SectionHeader } from '@/components/domain/page'
import { Button } from '@/components/ui/button'
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { fmt1, fmtDay, fmtShort, plural } from '@/lib/format'
import { Sparkline } from '@/features/home/sparkline'

export const Route = createFileRoute('/_app/progress')({
  loader: ({ context: { queryClient } }) => queryClient.ensureQueryData(progressQuery()),
  pendingComponent: () => <PageSkeleton width="wide" />,
  errorComponent: RouteError,
  component: ProgressPage,
})

function ProgressPage() {
  const { data } = useSuspenseQuery(progressQuery())
  const k = data.kpis
  const w = data.writing
  const delta = w.latest !== null && w.average_before !== null ? w.latest - w.average_before : null
  return (
    <Page width="wide">
      <title>Progress · Personal English Tutor</title>
      <PageHeader title="Progress" description="Practice is half of it. The real test is fewer mistakes in what you write." />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="grid content-start gap-1 rounded-xl border border-pencil-line bg-pencil-soft px-5 py-4 sm:col-span-2 lg:row-span-2">
          <span className="type-label text-pencil">Mistakes per 100 words, latest week</span>
          <span className="text-[56px] leading-none font-bold tracking-tight">{fmt1(w.latest)}</span>
          <span className="text-ink-2">
            {delta === null
              ? 'Appears after two weeks of messages.'
              : `${delta < 0 ? '↓' : delta > 0 ? '↑' : '='} ${fmt1(Math.abs(delta))} against your average of ${fmt1(w.average_before)}. Lower is better.`}
          </span>
          <Sparkline values={w.points.map((p) => p.per_100_words)} className="mt-auto h-12 w-full max-w-72 pt-3" label="Weekly trend" />
        </div>
        <KpiTile value={k.streak} label="day streak" />
        <KpiTile value={k.right_pct_7d === null ? '–' : `${k.right_pct_7d}%`} label="right, last 7 days" />
        <KpiTile value={`${k.cards_mastered}/${k.cards_total}`} label="cards mastered" />
        <KpiTile value={`${k.words_mastered}/${k.words_total}`} label="words mastered" />
      </section>

      <WritingChart writing={w} />
      <PracticeChart days={data.practice} totalAnswers={k.answers_total} rounds={k.rounds} />
      <MasteryByArea rows={data.mastery} />
      {data.repeated.length > 0 && <Repeated rows={data.repeated} />}
    </Page>
  )
}

function ChartSection({ title, caption, table, children }: { title: string; caption: ReactNode; table: ReactNode; children: ReactNode }) {
  const [asTable, setAsTable] = useState(false)
  return (
    <section className="grid gap-4">
      <SectionHeader
        title={title}
        action={
          <button type="button" className="hover:underline" onClick={() => setAsTable((v) => !v)} aria-pressed={asTable}>
            {asTable ? 'Show as chart' : 'Show as table'}
          </button>
        }
      />
      <p className="text-ink-2">{caption}</p>
      {asTable ? table : children}
    </section>
  )
}

const writingConfig = { per_100_words: { label: 'Mistakes per 100 words', color: 'var(--chart-1)' } } satisfies ChartConfig

function WritingChart({ writing }: { writing: Schemas['WritingTrend'] }) {
  if (writing.points.length < 2) {
    return (
      <section className="grid gap-3">
        <SectionHeader title="Your writing, by week" />
        <p className="text-ink-2">This chart appears after two weeks of messages. Lower is better.</p>
      </section>
    )
  }
  const data = writing.points.map((p) => ({ ...p, label: fmtShort(p.week_start) }))
  return (
    <ChartSection
      title="Your writing, by week"
      caption="Mistakes per 100 words you wrote to Claude Code. Lower is better."
      table={
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Week of</TableHead>
              <TableHead className="text-right">Per 100 words</TableHead>
              <TableHead className="text-right">Messages</TableHead>
              <TableHead className="text-right">Words</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {writing.points.map((p) => (
              <TableRow key={p.week_start}>
                <TableCell>{fmtDay(p.week_start)}</TableCell>
                <TableCell className="text-right tabular-nums">{p.per_100_words}</TableCell>
                <TableCell className="text-right tabular-nums">{p.messages}</TableCell>
                <TableCell className="text-right tabular-nums">{p.words}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      }
    >
      <ChartContainer config={writingConfig} className="aspect-auto h-64 w-full" role="img"
        aria-label={`Weekly mistakes per 100 words: ${writing.points.map((p) => p.per_100_words).join(', ')}`}>
        <AreaChart data={data} margin={{ top: 12, right: 16, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id="writingFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.18} />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
          <YAxis width={36} tickLine={false} axisLine={false} allowDecimals={false} domain={[0, 'auto']} />
          {writing.average_before !== null && (
            <ReferenceLine y={writing.average_before} stroke="var(--ink-3)" strokeDasharray="0"
              label={{ value: `your average ${fmt1(writing.average_before)}`, position: 'insideTopRight', fill: 'var(--ink-2)', fontSize: 12 }} />
          )}
          <ChartTooltip content={<ChartTooltipContent labelFormatter={(label) => `Week of ${String(label)}`} />} />
          <Area dataKey="per_100_words" type="monotone" stroke="var(--chart-1)" strokeWidth={2.5} fill="url(#writingFill)"
            dot={{ r: 4, fill: 'var(--surface)', stroke: 'var(--chart-1)', strokeWidth: 2 }} activeDot={{ r: 5 }} />
        </AreaChart>
      </ChartContainer>
    </ChartSection>
  )
}

const practiceConfig = {
  correct: { label: 'Right', color: 'var(--chart-1)' },
  missed: { label: 'Missed', color: 'var(--chart-2)' },
} satisfies ChartConfig

function PracticeChart({ days, totalAnswers, rounds }: { days: Schemas['DayPoint'][]; totalAnswers: number; rounds: number }) {
  const data = days.map((d) => ({ label: fmtShort(d.day), day: d.day, correct: d.correct, missed: d.answered - d.correct }))
  const any = days.some((d) => d.answered > 0)
  return (
    <ChartSection
      title="Practice, last 4 weeks"
      caption={`${plural(totalAnswers, 'answer')} in ${plural(rounds, 'round')} so far.`}
      table={
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Day</TableHead>
              <TableHead className="text-right">Answered</TableHead>
              <TableHead className="text-right">Right</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {days.filter((d) => d.answered > 0).map((d) => (
              <TableRow key={d.day}>
                <TableCell>{fmtDay(d.day)}</TableCell>
                <TableCell className="text-right tabular-nums">{d.answered}</TableCell>
                <TableCell className="text-right tabular-nums">{d.correct}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      }
    >
      {any ? (
        <ChartContainer config={practiceConfig} className="aspect-auto h-52 w-full" role="img" aria-label="Answers per day for the last 28 days">
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} interval={6} />
            <YAxis width={32} tickLine={false} axisLine={false} allowDecimals={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="correct" stackId="a" fill="var(--color-correct)" maxBarSize={24} />
            <Bar dataKey="missed" stackId="a" fill="var(--color-missed)" radius={[4, 4, 0, 0]} maxBarSize={24} />
          </BarChart>
        </ChartContainer>
      ) : (
        <p className="text-ink-2">Your practice shows up here, one bar per day.</p>
      )}
    </ChartSection>
  )
}

function MasteryByArea({ rows }: { rows: Schemas['CategoryMastery'][] }) {
  const { zh } = useSettings()
  return (
    <section className="grid gap-4">
      <SectionHeader title="Mastery by area" action={<MasteryLegend className="font-normal" />} />
      <ul className="grid gap-3">
        {rows.map((r) => (
          <li key={r.key} className="grid grid-cols-[minmax(0,170px)_minmax(0,1fr)_auto] items-center gap-4">
            <span className="truncate">
              {r.title}
              {zh && r.zh && (
                <span lang="zh-Hans" className="ml-2 text-ink-2">
                  {r.zh}
                </span>
              )}
            </span>
            <MasteryBar mastery={r} className="h-3" />
            <span className="text-sm text-ink-2 tabular-nums">
              {r.mastered}/{r.total}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Repeated({ rows }: { rows: Schemas['RepeatRow'][] }) {
  return (
    <section className="grid gap-4">
      <SectionHeader title="Mistakes you repeat" />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>You wrote</TableHead>
            <TableHead>Better</TableHead>
            <TableHead className="text-right">Times</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.card_id}>
              <TableCell className="whitespace-normal">
                <del className="x">{r.wrong}</del>
              </TableCell>
              <TableCell className="whitespace-normal">
                <ins className="x">{r.right}</ins>
              </TableCell>
              <TableCell className="text-right tabular-nums">{r.times}</TableCell>
              <TableCell>
                <Button variant="link" size="sm" className="h-auto p-0" render={<Link to="/mistakes/$patternKey" params={{ patternKey: r.pattern }} />}>
                  {r.status === 'new' ? 'New' : r.status === 'mastered' ? 'Mastered' : 'Learning'}
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  )
}
