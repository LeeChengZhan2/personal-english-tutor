import { createFileRoute, Link } from '@tanstack/react-router'
import { Play } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { Page, PageHeader, SectionHeader } from '@/components/domain/page'
import { Button } from '@/components/ui/button'
import { Kbd } from '@/components/ui/kbd'
import { useLocalFlag } from '@/hooks/use-local-flag'

export const Route = createFileRoute('/_app/help')({
  component: HelpPage,
})

const STEPS: [string, string][] = [
  ['You chat with Claude Code', 'Work as usual. Your tutor reads only the words you type: no code, files or pasted text.'],
  ['Mistakes are found', 'When you press Update my lessons, Claude checks your new messages and explains each mistake simply.'],
  ['They become cards', 'The same mistake made twice is one card, and it remembers how often you made it.'],
  ['You practise', 'Short rounds here. Cards you get right come back later and later until they stick.'],
]

const SCHEDULE = ['10 min', '1 day', '3 days', '7 days', '16 days', '35 days', '90 days']

function HelpPage() {
  const [, setWelcomeDone] = useLocalFlag('tutor-welcome-dismissed')
  useEffect(() => setWelcomeDone(true), [setWelcomeDone])
  return (
    <Page>
      <title>How it works · Personal English Tutor</title>
      <PageHeader title="How your tutor works" description="Practice made from the mistakes in your own messages." />

      <section className="grid gap-4">
        <SectionHeader title="Where lessons come from" />
        <ol className="grid gap-5">
          {STEPS.map(([title, text], i) => (
            <li key={title} className="grid grid-cols-[40px_minmax(0,1fr)] gap-x-4">
              <span className="grid size-10 place-items-center rounded-full bg-pencil font-display text-lg font-extrabold text-pencil-ink" aria-hidden>
                {i + 1}
              </span>
              <div className="grid gap-1 pt-1.5">
                <h3 className="type-h3">{title}</h3>
                <p className="text-ink-2">{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="grid gap-4">
        <SectionHeader title="A round" />
        <p>
          A round is a few cards, about two minutes. A new card starts easy and gets harder as you learn it:
        </p>
        <ul className="grid gap-3 sm:grid-cols-3">
          <Exercise title="Choose" text="Pick the right words for the gap." />
          <Exercise title="Find it" text="Tap the word that's wrong." />
          <Exercise title="Fix it" text="Type the sentence correctly. Claude checks answers that aren't an exact match." />
        </ul>
        <p className="text-ink-2">
          Word rounds practise your word lists: choose the spelling, choose the word for the gap, choose the meaning, and type the word.
        </p>
      </section>

      <section className="grid gap-4">
        <SectionHeader title="When cards come back" />
        <p>Right answers send a card further away; a wrong answer brings it back in 10 minutes.</p>
        <div className="flex flex-wrap items-center gap-2">
          {SCHEDULE.map((s, i) => (
            <span key={s} className="inline-flex items-center gap-2">
              <span className="rounded-full bg-pencil-soft px-3 py-1 text-sm font-bold text-pencil tabular-nums">{s}</span>
              {i < SCHEDULE.length - 1 && <span className="text-ink-3" aria-hidden>→</span>}
            </span>
          ))}
        </div>
        <p className="text-ink-2">A card is mastered once it comes back after 16 days.</p>
      </section>

      <section className="grid gap-4">
        <SectionHeader title="The marks" />
        <p className="text-[18px]">
          Why <del className="x">my table has</del> <ins className="x">does my table have</ins> one row?
        </p>
        <p className="text-ink-2">Red and struck out: remove it. Blue with a caret: add it.</p>
      </section>

      <section id="shortcuts" className="grid gap-4 scroll-mt-6">
        <SectionHeader title="Keyboard shortcuts" />
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[auto_minmax(0,1fr)]">
          <Shortcut keys={['1', '2', '3', '4']}>Choose an answer</Shortcut>
          <Shortcut keys={['←', '→', 'Enter']}>Move between words and tap one</Shortcut>
          <Shortcut keys={['Enter']}>Check your answer, then go to the next card</Shortcut>
          <Shortcut keys={['Shift', 'Enter']}>New line while typing</Shortcut>
          <Shortcut keys={['Esc']}>Stop a check, or end the round</Shortcut>
          <Shortcut keys={['Ctrl', 'B']}>Show or hide the sidebar</Shortcut>
        </dl>
      </section>

      <section className="grid gap-4">
        <SectionHeader title="Your Claude accounts" />
        <p>
          Add your accounts in Settings: each one is a Claude Code sign-in or an Anthropic API key. Update my lessons
          reads the conversations of the accounts you choose, and only what&rsquo;s new since the last update. If one
          account hits its usage limit, the next one is used.
        </p>
      </section>

      <section className="grid gap-4">
        <SectionHeader title="Your data" />
        <p>
          Everything stays on this PC in the <code className="rounded bg-sunk px-1">data</code> folder, which git
          ignores: your lessons, your accounts and your progress (backed up every day). Only the text you typed is sent
          to Claude to be checked, with emails, passwords and keys removed first.
        </p>
      </section>

      <div>
        <Button size="lg" render={<Link to="/practice" search={{ mode: 'cards' }} />}>
          <Play className="fill-current" aria-hidden /> Start practising
        </Button>
      </div>
    </Page>
  )
}

function Exercise({ title, text }: { title: string; text: string }) {
  return (
    <li className="grid content-start gap-1 rounded-xl border bg-surface p-4 shadow-e1">
      <span className="type-h3">{title}</span>
      <span className="text-ink-2">{text}</span>
    </li>
  )
}

function Shortcut({ keys, children }: { keys: string[]; children: ReactNode }) {
  return (
    <>
      <dt className="flex flex-wrap items-center gap-1">
        {keys.map((k, i) => (
          <span key={k} className="inline-flex items-center gap-1">
            {i > 0 && <span className="text-ink-3">{keys.length === 2 && keys[0] !== '1' ? '+' : ''}</span>}
            <Kbd>{k}</Kbd>
          </span>
        ))}
      </dt>
      <dd className="text-ink-2">{children}</dd>
    </>
  )
}
