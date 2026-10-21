import { Volume2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useVoices } from '@/hooks/use-voices'
import { canSpeak, speak } from '@/lib/speech'
import { cn } from '@/lib/utils'

const AGAIN_MS = 5000 // a second press within this time reads it slowly

/**
 * Reads `text` aloud with the browser's voice; pressed again soon after, it reads it slowly. `inline` makes it small,
 * for the end of a sentence (pass it as HighlightText's `end`). Hidden when the browser can't speak.
 */
export function SpeakButton({ text, label, inline = false, className }: { text: string; label: string; inline?: boolean; className?: string }) {
  const voices = useVoices()
  const [playing, setPlaying] = useState(false)
  const last = useRef({ at: 0, slow: true, play: 0 })
  if (!canSpeak() || !text) return null

  function play() {
    const now = Date.now()
    const slow = now - last.current.at < AGAIN_MS && !last.current.slow
    const id = last.current.play + 1
    last.current = { at: now, slow, play: id }
    setPlaying(true)
    // a press cuts off the one before, so only the latest one's end switches the button off
    speak(text, voices, { slow, onEnd: () => last.current.play === id && setPlaying(false) })
  }

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size={inline ? 'icon-xs' : 'icon-sm'}
            aria-label={`Listen to ${label}`}
            onClick={play}
            className={cn(playing ? 'text-pencil' : 'text-ink-2 hover:text-pencil', inline && '-my-1.5 ml-1 align-middle', className)}
          >
            <Volume2 className={cn(inline ? 'size-4' : 'size-5', playing && 'animate-pulse')} aria-hidden />
          </Button>
        }
      />
      <TooltipContent>Listen · press again to hear it slowly</TooltipContent>
    </Tooltip>
  )
}
