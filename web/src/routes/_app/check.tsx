import { createFileRoute } from '@tanstack/react-router'
import { SpellCheck } from 'lucide-react'
import { Page, PageHeader } from '@/components/domain/page'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

// Check writing (Claude checks a message before you send it) arrives with the AI features.
export const Route = createFileRoute('/_app/check')({
  component: CheckPage,
})

function CheckPage() {
  return (
    <Page width="wide">
      <title>Check writing · Personal English Tutor</title>
      <PageHeader title="Check writing" description="Check a message before you send it, and copy a natural version." />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="grid content-start gap-3">
          <label htmlFor="draft" className="font-bold">
            Your message
          </label>
          <Textarea id="draft" disabled placeholder="Coming in the next step." className="min-h-56 text-[17px]" />
          <div>
            <Button disabled>
              <SpellCheck aria-hidden /> Check my English
            </Button>
          </div>
        </div>
        <div className="grid content-start gap-2 rounded-xl border-2 border-dashed border-line p-6 text-ink-2">
          <p className="type-h3 text-ink">Coming soon</p>
          <p>Paste a message and press Check. You&rsquo;ll see each fix, why, and a natural version to copy.</p>
        </div>
      </div>
    </Page>
  )
}
