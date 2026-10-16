import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { ArrowRight, BookA, Check, CircleHelp, Play, SpellCheck, X } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Schemas } from '@/api/client'
import { bootstrapQuery, homeQuery } from '@/api/queries'
import { ChineseHint, HighlightText } from '@/components/domain/hints'
import { Page, PageSkeleton, RouteError, SectionHeader } from '@/components/domain/page'
import { ProofText } from '@/components/domain/proof-text'
import { Button } from '@/components/ui/button'
import { Sparkline } from '@/features/home/sparkline'
import { UpdateLessonsButton } from '@/features/update/update-button'
import { useLocalFlag } from '@/hooks/use-local-flag'
import { useNow } from '@/hooks/use-now'
import { fmt1, fmtDay, greeting, percent, plural } from '@/lib/format'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/_app/')({
  loader: ({ context: { queryClient } }) =>
    Promise.all([queryClient.ensureQueryData(homeQuery()), queryClient.ensureQueryData(bootstrapQuery())]),
  pendingComponent: () => <PageSkeleton width="wide" />,
  errorComponent: RouteError,
  component: HomePage,
})

function HomePage() {
  const { data: home } = useSuspenseQuery(homeQuery())
  const { data: boot } = useSuspenseQuery(bootstrapQuery())
  const [welcomeDone, setWelcomeDone] = useLocalFlag('tutor-welcome-dismissed')

  return (
    <Page width="wide">
      <title>Personal English Tutor</title>
      {!welcomeDone && !home.empty && <Welcome onDismiss={() => setWelcomeDone(true)} />}
      {home.empty ? (
        <FirstLessons accounts={boot.ai.accounts} />
      ) : (
        <>
          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-stretch">
            <Hero practice={home.practice} today={boot.today} />
            <ThisWeek writing={home.writing} />
          </section>
          <section className="grid gap-6 md:grid-cols-2">
            {home.focus && <FocusCard focus={home.focus} />}
            {home.word_of_the_day && <WordOfTheDay word={home.word_of_the_day} wordsDue={home.practice.words_due} />}
          </section>
          {home.latest_chat && <LatestChat chat={home.latest_chat} />}
          {boot.ai.available && <CheckBeforeYouSend />}
        </>
      )}
    </Page>
  )
}

function Hero({ practice, today }: { practice: Schemas['PracticeSummary']; today: Schemas['DayTotals'] }) {
  const now = new Date(useNow())
  const headline =
    practice.mode === 'review'
      ? `${plural(practice.cards_due, 'card')} to review`
      : practice.mode === 'new'
        ? `${plural(practice.new_cards, 'new card')} for today`
        : 'You’re up to date'
  const line =
    practice.mode === 'extra'
      ? 'Nothing is due. An extra round brings back cards you’re still learning.'
      : `A round is ${plural(practice.round_size, 'card')} · about ${practice.est_minutes} min`
  return (
    <div className="grid content-center gap-4 py-2">
      <p className="type-label text-ink-2">
        {greeting(now)} · {fmtDay(now.toISOString())}
      </p>
      <h1 className="type-display">{headline}</h1>
      <p className="type-lead text-ink-2">{line}</p>
      <div className="flex flex-wrap items-center gap-3 pt-1">
        <Button size="lg" render={<Link to="/practice" search={{ mode: 'cards' }} />}>
          <Play className="fill-current" aria-hidden /> {practice.mode === 'extra' ? 'Extra round' : 'Start a round'}
        </Button>
        <Button size="lg" variant="outline" render={<Link to="/practice" search={{ mode: 'words' }} />}>
          <BookA aria-hidden /> Word round{practice.words_due ? ` · ${practice.words_due} due` : ''}
        </Button>
      </div>
      {today.answered > 0 && (
        <p className="text-sm text-ink-2">
          Today: <b className="text-ink">{plural(today.answered, 'answer')}</b>, {percent(today.correct, today.answered)} right
        </p>
      )}
    </div>
  )
}

function ThisWeek({ writing }: { writing: Schemas['WritingTrend'] }) {
  const values = writing.points.map((p) => p.per_100_words)
  const verdict =
    writing.verdict === 'fewer'
      ? 'Fewer than your average. Keep going.'
      : writing.verdict === 'more'
        ? 'More than your average. Your focus pattern is the quickest way down.'
        : writing.verdict === 'same'
          ? 'About your average.'
          : 'Shows up after two weeks of messages.'
  return (
    <Link
      to="/progress"
      className="group grid content-between gap-4 rounded-xl border bg-surface p-5 shadow-e1 transition-shadow hover:shadow-e2"
    >
      <div className="grid gap-1">
        <p className="type-label text-ink-2">Your writing, latest week</p>
        <p className="flex items-baseline gap-2">
          <span className="text-[44px] leading-none font-bold tracking-tight">{fmt1(writing.latest)}</span>
          <span className="text-sm text-ink-2">mistakes per 100 words</span>
        </p>
        <p className="text-sm text-ink-2">{verdict}</p>
      </div>
      <div className="flex items-end justify-between gap-3">
        <Sparkline values={values} className="h-9 w-32" label={`Weekly mistakes per 100 words: ${values.join(', ')}`} />
        <span className="text-sm font-bold text-pencil group-hover:underline">
          Progress <ArrowRight className="inline size-3.5" aria-hidden />
        </span>
      </div>
    </Link>
  )
}

function FocusCard({ focus }: { focus: Schemas['Focus'] }) {
  return (
    <section className="grid content-start gap-3 rounded-xl border border-pencil-line bg-pencil-soft p-6">
      <p className="type-label text-pencil">{focus.window === 'week' ? 'Your focus this week' : 'Your most common mistake'}</p>
      <h2 className="type-h2">{focus.title}</h2>
      {focus.rule && <p className="type-lead">{focus.rule}</p>}
      <ChineseHint text={focus.rule_zh} />
      {focus.example && (
        <div className="grid gap-1 rounded-lg bg-surface/70 px-4 py-3 text-[17px]">
          <span>
            <span className="text-ink-2">You wrote </span>
            <del className="x">{focus.example.wrong}</del>
          </span>
          <span>
            <span className="text-ink-2">Better: </span>
            <ins className="x">{focus.example.right}</ins>
          </span>
        </div>
      )}
      <div className="flex flex-wrap gap-2 pt-1">
        <Button render={<Link to="/practice" search={{ mode: 'pattern', pattern: focus.pattern }} />}>
          <Play className="fill-current" aria-hidden /> Practise this
        </Button>
        <Button variant="ghost" render={<Link to="/mistakes/$patternKey" params={{ patternKey: focus.pattern }} />}>
          See all examples
        </Button>
      </div>
    </section>
  )
}

function WordOfTheDay({ word, wordsDue }: { word: Schemas['WordBrief']; wordsDue: number }) {
  return (
    <section className="grid content-start gap-3 rounded-xl border bg-surface p-6 shadow-e1">
      <p className="type-label text-ink-2">Word of the day</p>
      <p className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-display text-[34px] leading-tight font-extrabold tracking-tight">{word.word}</span>
        {word.pos && <span className="text-ink-2 italic">{word.pos}</span>}
      </p>
      <p className="type-lead">{word.meaning}</p>
      <ChineseHint text={word.meaning_zh} />
      {word.example && <HighlightText className="text-ink-2" text={word.example} word={word.word} />}
      {word.wrote[0] && (
        <p className="text-sm text-ink-2">
          You wrote <del className="x">{word.wrote[0]}</del>
        </p>
      )}
      <div className="flex flex-wrap gap-2 pt-1">
        <Button variant="outline" render={<Link to="/practice" search={{ mode: 'words' }} />}>
          <BookA aria-hidden /> Word round{wordsDue ? ` · ${wordsDue} due` : ''}
        </Button>
        <Button variant="ghost" render={<Link to="/words" />}>
          All words
        </Button>
      </div>
    </section>
  )
}

function LatestChat({ chat }: { chat: Schemas['LatestChat'] }) {
  return (
    <section className="grid gap-4">
      <SectionHeader title={`From your chats on ${fmtDay(chat.day)}`} action={<Link to="/messages">All messages</Link>} />
      <p className="text-ink-2">
        {plural(chat.messages, 'message')}, {plural(chat.cards, 'thing')} to learn
        {chat.top_patterns.length > 0 && ': '}
        {chat.top_patterns.map((p, i) => (
          <span key={p.pattern}>
            {i > 0 && ', '}
            <Link to="/mistakes/$patternKey" params={{ patternKey: p.pattern }} className="font-bold text-pencil hover:underline">
              {p.title}
            </Link>{' '}
            ({p.count})
          </span>
        ))}
      </p>
      {chat.sample && (
        <figure className="grid gap-2 rounded-xl border bg-surface p-5 shadow-e1">
          <figcaption className="type-label text-ink-2">You wrote</figcaption>
          <ProofText as="p" className="text-[17px] leading-7 line-clamp-6" from={chat.sample.text} to={chat.sample.fixed} />
        </figure>
      )}
    </section>
  )
}

function CheckBeforeYouSend() {
  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-surface px-6 py-5 shadow-e1">
      <div className="grid gap-1">
        <h2 className="type-h3">Check before you send</h2>
        <p className="text-ink-2">Paste a message for a colleague or a request to Claude. See each fix and a natural version.</p>
      </div>
      <Button variant="outline" render={<Link to="/check" />}>
        <SpellCheck aria-hidden /> Check writing
      </Button>
    </section>
  )
}

function Welcome({ onDismiss }: { onDismiss: () => void }) {
  return (
    <section className="relative grid gap-3 rounded-xl border border-pencil-line bg-pencil-soft p-6 pr-14">
      <h2 className="type-h3">New here?</h2>
      <p className="max-w-[64ch]">
        Every card here comes from a real mistake in the messages you type to Claude Code. Take two minutes to see how
        lessons are made and how a round works.
      </p>
      <div>
        <Button render={<Link to="/help" />}>
          <CircleHelp aria-hidden /> How it works
        </Button>
      </div>
      <Button variant="ghost" size="icon-sm" className="absolute top-3 right-3" aria-label="Hide this" onClick={onDismiss}>
        <X aria-hidden />
      </Button>
    </section>
  )
}

function FirstLessons({ accounts }: { accounts: Schemas['AccountInfo'][] }) {
  const hasAccount = accounts.length > 0
  return (
    <div className="grid gap-8">
      <div className="grid gap-3">
        <p className="type-label text-ink-2">Welcome</p>
        <h1 className="type-display">Your own English tutor</h1>
        <p className="type-lead max-w-[62ch] text-ink-2">
          It reads the messages you wrote to Claude Code, finds your English mistakes, and turns them into short
          practice rounds. Two steps to start:
        </p>
      </div>
      <ol className="grid gap-4">
        <SetupStep n={1} done={hasAccount} title="Add your Claude account"
          text={hasAccount ? `Added: ${accounts.map((a) => a.name).join(', ')}.` : 'The account you use with Claude Code. If you use two, add both.'}
          action={
            <Button variant={hasAccount ? 'outline' : 'default'} render={<Link to="/settings" hash="accounts" />}>
              {hasAccount ? 'Manage accounts' : 'Add account'}
            </Button>
          }
        />
        <SetupStep n={2} done={false} title="Generate your lessons"
          text="Reads your conversations on this PC and finds your mistakes. The first time can take a few minutes."
          action={<UpdateLessonsButton variant={hasAccount ? 'default' : 'outline'} label="Generate my lessons" />}
        />
      </ol>
    </div>
  )
}

function SetupStep({ n, done, title, text, action }: { n: number; done: boolean; title: string; text: string; action: ReactNode }) {
  return (
    <li className="flex flex-wrap items-center gap-4 rounded-xl border bg-surface p-5 shadow-e1">
      <span className={cn('grid size-10 shrink-0 place-items-center rounded-full font-display text-lg font-extrabold',
        done ? 'bg-ok-soft text-ok' : 'bg-pencil text-pencil-ink')} aria-hidden>
        {done ? <Check className="size-5" /> : n}
      </span>
      <div className="grid min-w-0 flex-1 gap-0.5">
        <h2 className="type-h3">{title}</h2>
        <p className="text-ink-2">{text}</p>
      </div>
      {action}
    </li>
  )
}
