import { createFileRoute } from '@tanstack/react-router'
import { Monitor, Moon, Sun } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Kbd } from '@/components/ui/kbd'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useTheme } from '@/hooks/use-theme'
import type { Theme } from '@/lib/theme'

// A visual check of the design system in both themes (not linked from the app's navigation).
export const Route = createFileRoute('/tokens')({
  component: TokensPage,
})

const SWATCHES = [
  'desk', 'paper', 'surface', 'sunk', 'line', 'ink', 'ink-2', 'ink-3', 'pencil', 'pencil-hover', 'pencil-soft',
  'pencil-line', 'mark', 'mark-soft', 'ok', 'ok-soft', 'amber', 'amber-soft', 'highlight',
] as const

const THEMES: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: 'system', label: 'System', Icon: Monitor },
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
]

function TokensPage() {
  const { theme, setTheme } = useTheme()
  return (
    <main className="mx-auto grid max-w-5xl gap-10 px-6 py-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="grid gap-2">
          <p className="type-label text-ink-2">Design tokens</p>
          <h1 className="type-h1">A copy editor&rsquo;s desk</h1>
        </div>
        <fieldset className="flex gap-2">
          <legend className="sr-only">Theme</legend>
          {THEMES.map(({ value, label, Icon }) => (
            <Button key={value} variant={theme === value ? 'default' : 'outline'} onClick={() => setTheme(value)}>
              <Icon aria-hidden /> {label}
            </Button>
          ))}
        </fieldset>
      </header>

      <section className="grid gap-3">
        <h2 className="type-h2">Colour</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          {SWATCHES.map((name) => (
            <div key={name} className="grid gap-1.5">
              <div className="h-14 rounded-lg border shadow-e1" style={{ background: `var(--${name})` }} />
              <code className="text-sm text-ink-2">{name}</code>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-3">
        <h2 className="type-h2">Type</h2>
        <p className="type-display">12 cards to review</p>
        <p className="type-h1">Page title</p>
        <p className="type-h2">Section title</p>
        <p className="type-h3">Sub-section</p>
        <p className="type-lead text-ink-2">A lead line: one sentence that says what the page is for.</p>
        <p>Body text at 16px. The quick brown fox jumps over the lazy dog. 0123456789 Il1 O0</p>
        <p className="type-label text-ink-2">Label · eyebrow</p>
        <p className="type-sentence">
          Why <del className="x">my table has</del> <ins className="x">does my table have</ins> one row?
        </p>
        <p>
          The <mark>response</mark> is slow. 中文提示：<span lang="zh-Hans">这是一个中文提示。</span>
        </p>
      </section>

      <section className="grid gap-4">
        <h2 className="type-h2">Controls</h2>
        <div className="flex flex-wrap items-center gap-3">
          <Button>Start a round</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="link">Link</Button>
          <Badge>New</Badge>
          <Badge variant="secondary">Learning</Badge>
          <Badge variant="outline">Typo</Badge>
          <Badge variant="destructive">Mistake</Badge>
          <span className="text-sm text-ink-2">
            Press <Kbd>1</Kbd>–<Kbd>4</Kbd> or <Kbd>Enter</Kbd>
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input placeholder="Type the word" aria-label="Sample input" />
          <label className="flex items-center gap-3">
            <Switch defaultChecked aria-label="Chinese hints" /> Chinese hints · 中文提示
          </label>
          <Textarea placeholder="Your message" aria-label="Sample textarea" className="sm:col-span-2" />
        </div>
        <Tabs defaultValue="new">
          <TabsList>
            <TabsTrigger value="new">New words</TabsTrigger>
            <TabsTrigger value="fix">Typos & fixes</TabsTrigger>
          </TabsList>
          <TabsContent value="new" className="pt-3 text-ink-2">Words you haven’t used yet.</TabsContent>
          <TabsContent value="fix" className="pt-3 text-ink-2">Words you typed or used wrong.</TabsContent>
        </Tabs>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="type-h3">Do-support in questions</CardTitle>
            <CardDescription>Questions with why need does/do before the subject.</CardDescription>
          </CardHeader>
          <CardContent className="text-base">
            <del className="x">Why my table has</del> <ins className="x">Why does my table have</ins>
          </CardContent>
        </Card>
        <div className="grid content-start gap-2 rounded-xl border border-pencil-line bg-pencil-soft p-5">
          <p className="type-label text-pencil">Your focus this week</p>
          <p className="type-h3">a / an / the</p>
          <p className="text-ink-2">Use a / an for one thing you haven&rsquo;t mentioned yet.</p>
        </div>
      </section>
    </main>
  )
}
