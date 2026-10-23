import { createFileRoute, Link, useCanGoBack, useNavigate, useRouter } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { z } from 'zod'
import type { WordGroup } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { WordRound } from '@/features/practice/word-round'

const searchSchema = z.object({
  mode: z.enum(['cards', 'words', 'pattern', 'rewrite', 'generated']).catch('cards'),
  pattern: z.string().optional(),
  group: z.enum(['new', 'fix']).optional(),
  message: z.string().optional(),
})

// Full-screen practice (outside the sidebar layout). Word rounds are here; the card rounds arrive in the next milestone.
export const Route = createFileRoute('/practice')({
  validateSearch: searchSchema,
  component: PracticePage,
})

function PracticePage() {
  const { mode, group } = Route.useSearch()
  return mode === 'words' ? <WordRoundPage group={group} /> : <PracticePlaceholder />
}

function WordRoundPage({ group }: { group?: WordGroup }) {
  const [round, setRound] = useState(0)
  const router = useRouter()
  const canGoBack = useCanGoBack()
  const navigate = useNavigate()
  const exit = () => (canGoBack ? router.history.back() : void navigate({ to: '/words', search: group ? { group } : {} }))
  return <WordRound key={round} group={group} onExit={exit} onAgain={() => setRound((n) => n + 1)} />
}

function PracticePlaceholder() {
  return (
    <main className="grid min-h-svh place-items-center bg-paper px-6">
      <title>Practice · Personal English Tutor</title>
      <div className="grid max-w-md gap-4 text-center">
        <p className="type-label text-ink-2">Practice</p>
        <h1 className="type-h1">Rounds are being rebuilt</h1>
        <p className="text-ink-2">The new practice screen comes in the next step. Until then, keep practising in the old app.</p>
        <div>
          <Button variant="outline" render={<Link to="/" />}>
            <ArrowLeft aria-hidden /> Back to Home
          </Button>
        </div>
      </div>
    </main>
  )
}
