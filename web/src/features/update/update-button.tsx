import { RefreshCw } from 'lucide-react'
import type { ComponentProps } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useUpdateFlow } from './use-update-flow'

type ButtonProps = Pick<ComponentProps<typeof Button>, 'variant' | 'size' | 'className'>

/** A button that runs the "Update my lessons" flow. */
export function UpdateLessonsButton({ variant = 'outline', size, className, label = 'Update my lessons' }: ButtonProps & { label?: string }) {
  const flow = useUpdateFlow()
  return (
    <>
      <Button variant={variant} size={size} className={className} disabled={flow.busy} onClick={flow.open}>
        <RefreshCw className={cn(flow.running && 'animate-spin')} aria-hidden /> {flow.running ? 'Updating…' : label}
      </Button>
      {flow.dialogs}
    </>
  )
}
