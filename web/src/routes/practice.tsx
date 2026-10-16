import { createFileRoute, Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { z } from 'zod'
import { Button } from '@/components/ui/button'

const searchSchema = z.object({
  mode: z.enum(['cards', 'words', 'pattern', 'rewrite', 'generated']).catch('cards'),
  pattern: z.string().optional(),
  kind: z.enum(['spelling', 'know', 'clearer']).optional(),
  message: z.string().optional(),
})

// Full-screen practice (outside the sidebar layout). The rounds themselves arrive in the next milestone.
export const Route = createFileRoute('/practice')({
  validateSearch: searchSchema,
  component: PracticePlaceholder,
})

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
