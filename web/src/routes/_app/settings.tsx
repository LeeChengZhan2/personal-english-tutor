import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { Monitor, Moon, Sun, Volume2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { Schemas } from '@/api/client'
import { bootstrapQuery, statusQuery, useSaveSettings } from '@/api/queries'
import { Page, PageHeader, PageSkeleton, RouteError } from '@/components/domain/page'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { AccountsCard } from '@/features/settings/accounts-card'
import { UpdateLessonsButton } from '@/features/update/update-button'
import { useTapOnly } from '@/hooks/use-tap-only'
import { useTheme } from '@/hooks/use-theme'
import { useVoices } from '@/hooks/use-voices'
import { fromNow } from '@/lib/format'
import { canSpeak, chosenVoice, englishVoices, setChosenVoice, speak, voiceLabel } from '@/lib/speech'
import type { Theme } from '@/lib/theme'

export const Route = createFileRoute('/_app/settings')({
  loader: ({ context: { queryClient } }) =>
    Promise.all([queryClient.ensureQueryData(bootstrapQuery()), queryClient.ensureQueryData(statusQuery())]),
  pendingComponent: () => <PageSkeleton />,
  errorComponent: RouteError,
  component: SettingsPage,
})

function SettingsPage() {
  const { data: boot } = useSuspenseQuery(bootstrapQuery())
  const { data: status } = useSuspenseQuery(statusQuery())
  return (
    <Page>
      <title>Settings · Personal English Tutor</title>
      <PageHeader title="Settings" description="Changes save as you make them." />
      <PracticeCard settings={boot.settings} />
      <DeviceCard />
      <AccountsCard />
      <LessonsCard pipeline={boot.pipeline} lessons={status.lessons} />
      <AboutCard status={status} url={boot.app_url} />
    </Page>
  )
}

function Card({ id, title, description, children }: { id?: string; title: string; description?: string; children: ReactNode }) {
  return (
    <section id={id} className="grid gap-1 rounded-xl border bg-surface px-6 py-5 shadow-e1 scroll-mt-6">
      <h2 className="type-h3">{title}</h2>
      {description && <p className="text-sm text-ink-2">{description}</p>}
      <div className="mt-2 grid divide-y">{children}</div>
    </section>
  )
}

function Row({ label, hint, children, htmlFor }: { label: ReactNode; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-3">
      <div className="grid gap-0.5">
        {htmlFor ? (
          <label htmlFor={htmlFor} className="font-bold">
            {label}
          </label>
        ) : (
          <span className="font-bold">{label}</span>
        )}
        {hint && <span className="text-sm text-ink-2">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function PracticeCard({ settings }: { settings: Schemas['PracticeSettings'] }) {
  const save = useSaveSettings()
  return (
    <Card title="Practice">
      <Row label={<>Chinese hints · <span lang="zh-Hans">中文提示</span></>} hint="Show a short Simplified Chinese hint next to rules and explanations. New words always show their Chinese meaning." htmlFor="zh">
        <Switch id="zh" checked={settings.zh} onCheckedChange={(zh: boolean) => save.mutate({ zh })} />
      </Row>
      <Row label="Cards per round" hint="Reviews are never limited.">
        <ToggleGroup
          variant="outline"
          value={[String(settings.round_size)]}
          onValueChange={(v: string[]) => v[0] && save.mutate({ round_size: Number(v[0]) as Schemas['PracticeSettings']['round_size'] })}
          aria-label="Cards per round"
        >
          {[5, 8, 12, 16].map((n) => (
            <ToggleGroupItem key={n} value={String(n)} className="h-10 min-w-11 tabular-nums">
              {n}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </Row>
      <Row label="New cards per day" hint="How many cards you haven't seen before can join your rounds each day.">
        <ToggleGroup
          variant="outline"
          value={[String(settings.new_per_day)]}
          onValueChange={(v: string[]) => v[0] && save.mutate({ new_per_day: Number(v[0]) as Schemas['PracticeSettings']['new_per_day'] })}
          aria-label="New cards per day"
        >
          {[6, 12, 20, 30].map((n) => (
            <ToggleGroupItem key={n} value={String(n)} className="h-10 min-w-11 tabular-nums">
              {n}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </Row>
    </Card>
  )
}

const THEMES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'system', label: 'Same as Windows', icon: Monitor },
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
]

function DeviceCard() {
  const { theme, setTheme } = useTheme()
  const [tapOnly, setTapOnly] = useTapOnly()
  return (
    <Card title="This device" description="Saved in this browser only.">
      <Row label="Theme">
        <ToggleGroup variant="outline" value={[theme]} onValueChange={(v: string[]) => v[0] && setTheme(v[0] as Theme)} aria-label="Theme">
          {THEMES.map((t) => (
            <ToggleGroupItem key={t.value} value={t.value} className="h-10 px-3">
              <t.icon aria-hidden /> {t.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </Row>
      <Row label="Tap-only practice" hint="No typing in rounds: good on a touch screen." htmlFor="tap-only">
        <Switch id="tap-only" checked={tapOnly} onCheckedChange={(v: boolean) => setTapOnly(v)} />
      </Row>
      <VoiceRow />
    </Card>
  )
}

const VOICE_SAMPLE = 'Could you explain the rationale behind this change?'

function VoiceRow() {
  const voices = useVoices()
  const [chosen, setChosen] = useState(chosenVoice)
  if (!canSpeak()) return <Row label="Voice" hint="This browser can’t read words aloud.">{null}</Row>
  const english = englishVoices(voices)
  const best = english[0]
  return (
    <Row
      label="Voice"
      hint="Reads your words aloud when you press a speaker button. Natural voices sound the most like a person, and need the internet."
      htmlFor="voice"
    >
      <div className="flex flex-wrap items-center gap-2">
        <select
          id="voice"
          value={chosen}
          onChange={(e) => {
            setChosen(e.target.value)
            setChosenVoice(e.target.value)
          }}
          className="h-10 w-[28rem] max-w-full rounded-lg border border-input bg-surface px-3 text-[15px] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <option value="">Automatic{best ? ` · ${voiceLabel(best)}` : ''}</option>
          {english.map((v) => (
            <option key={v.voiceURI} value={v.voiceURI}>
              {voiceLabel(v)}
            </option>
          ))}
        </select>
        <Button variant="outline" className="h-10" onClick={() => speak(VOICE_SAMPLE, voices, { voice: chosen })}>
          <Volume2 aria-hidden /> Listen
        </Button>
      </div>
    </Row>
  )
}

function LessonsCard({ pipeline, lessons }: { pipeline: Schemas['PipelineInfo']; lessons: Schemas['LessonsInfo'] }) {
  return (
    <Card title="Lessons" description="Made from your Claude Code conversations each time you press Update my lessons.">
      <Row label="Messages" hint={pipeline.waiting ? `${pipeline.waiting} read but not checked yet` : 'All checked'}>
        <span className="tabular-nums">{pipeline.captured} read</span>
      </Row>
      <Row label="Lessons" hint={pipeline.last_analysis_at ? `Last new lesson ${fromNow(pipeline.last_analysis_at)}` : 'None yet'}>
        <span className="tabular-nums">
          {lessons.cards} cards · {lessons.words} words
        </span>
      </Row>
      <Row label="New conversations" hint="Reads only what's new since the last update, then finds your mistakes.">
        <UpdateLessonsButton />
      </Row>
      {lessons.errors.length > 0 && <p className="py-3 text-sm text-mark">Some lesson files couldn&rsquo;t be read: {lessons.errors.join('; ')}</p>}
    </Card>
  )
}

function AboutCard({ status, url }: { status: Schemas['Status']; url: string }) {
  return (
    <Card title="About">
      <Row label="Version">
        <span className="tabular-nums">{status.version}</span>
      </Row>
      <Row label="Address">
        <span>{url}</span>
      </Row>
      <Row label="Your data" hint="Lessons, and your progress in tutor.db (backed up daily to data/backups).">
        <code className="max-w-full truncate rounded bg-sunk px-2 py-1 text-sm">{status.root}\data</code>
      </Row>
    </Card>
  )
}
