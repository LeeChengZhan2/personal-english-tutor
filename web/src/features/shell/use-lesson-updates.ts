import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { CONTENT_KEYS, useBootstrap } from '@/api/queries'
import { plural } from '@/lib/format'

/** When the pipeline adds lessons (bootstrap's lessons_version changes), refresh the pages and say so. */
export function useLessonUpdates() {
  const { data } = useBootstrap()
  const client = useQueryClient()
  const navigate = useNavigate()
  const seen = useRef<{ version: string; cards: number } | null>(null)

  useEffect(() => {
    if (!data) return
    const previous = seen.current
    seen.current = { version: data.lessons_version, cards: data.counts.cards_total }
    if (!previous || previous.version === data.lessons_version) return
    for (const key of CONTENT_KEYS) void client.invalidateQueries({ queryKey: key })
    const added = data.counts.cards_total - previous.cards
    if (added > 0) {
      toast(`${plural(added, 'new card')} from your chats`, {
        action: { label: 'Start a round', onClick: () => void navigate({ to: '/practice', search: { mode: 'cards' } }) },
      })
    }
  }, [data, client, navigate])
}
