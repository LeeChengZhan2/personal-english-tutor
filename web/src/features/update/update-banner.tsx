import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleStop, RefreshCw } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import type { Schemas } from '@/api/client'
import { CONTENT_KEYS, keys, updateStatusQuery, useStopUpdate } from '@/api/queries'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { plural } from '@/lib/format'

const STAGES: Record<string, string> = {
  reading: 'Reading your conversations',
  analyzing: 'Finding mistakes',
  vocabulary: 'Collecting words to learn',
  done: 'Finishing',
}

/** While lessons are being updated: what's happening, how far along, and a Stop button. Also says how it ended. */
export function UpdateBanner() {
  const { data } = useQuery(updateStatusQuery())
  const stop = useStopUpdate()
  useUpdateOutcome(data)
  if (!data || data.state !== 'running') return null
  const stage = data.stage ?? 'reading'
  const pct = data.total ? Math.round((100 * data.done) / data.total) : 0
  const detail =
    stage === 'analyzing' && data.total > 1
      ? ` · part ${Math.min(data.done + 1, data.total)} of ${data.total}`
      : stage === 'vocabulary' && data.total > 1
        ? ` · ${data.done} of ${data.total}`
        : ''
  return (
    <div aria-live="polite" className="m-3 grid gap-2 rounded-xl border border-pencil-line bg-pencil-soft px-4 py-3 md:m-4">
      <div className="flex flex-wrap items-center gap-3">
        <RefreshCw className="size-4 animate-spin text-pencil" aria-hidden />
        <p className="font-bold">
          Updating your lessons: {STAGES[stage] ?? stage}
          <span className="font-normal text-ink-2">{detail}</span>
        </p>
        <Button variant="ghost" size="sm" className="ml-auto" disabled={stop.isPending} onClick={() => stop.mutate()}>
          <CircleStop aria-hidden /> Stop
        </Button>
      </div>
      <Progress value={stage === 'reading' ? null : pct} aria-label="Update progress" />
    </div>
  )
}

/** When an update ends: refresh the pages and say what happened. */
function useUpdateOutcome(status: Schemas['UpdateStatus'] | undefined) {
  const client = useQueryClient()
  const previous = useRef<string | null>(null)
  useEffect(() => {
    if (!status) return
    const was = previous.current
    previous.current = status.state
    if (was !== 'running' || status.state === 'running') return
    for (const key of [...CONTENT_KEYS, keys.bootstrap, keys.status]) void client.invalidateQueries({ queryKey: key })
    const r = status.result
    if (status.state === 'done') {
      if (r && (r.new_cards || r.new_words)) {
        toast.success(`Done: ${plural(r.new_cards, 'new card')} and ${plural(r.new_words, 'new word')} from ${plural(r.analyzed, 'message')}.`)
      } else {
        toast.success('Your lessons are up to date. No new mistakes were found.')
      }
    } else if (status.state === 'stopped') {
      toast('Update stopped. Everything finished before you stopped is kept.')
    } else if (status.state === 'failed') {
      toast.error(status.error?.message ?? 'The update stopped.', { duration: 10_000 })
    }
  }, [status, client])
}
