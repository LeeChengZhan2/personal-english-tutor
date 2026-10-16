import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { accountsQuery, updatePreviewQuery, useStartUpdate } from '@/api/queries'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { fromNow, plural } from '@/lib/format'

export function SetupFirstDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  return (
    <AlertDialog open={open} onOpenChange={(next: boolean) => !next && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Please configure your account first</AlertDialogTitle>
          <AlertDialogDescription>
            Add the Claude account you chat with in Claude Code. Your lessons are made from that account&rsquo;s
            conversations on this PC.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              onClose()
              void navigate({ to: '/settings', hash: 'accounts' })
            }}
          >
            Go to Settings
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function ConfirmUpdateDialog({ onClose }: { onClose: () => void }) {
  const { data } = useQuery(accountsQuery())
  const accounts = data?.accounts ?? []
  const [chosen, setChosen] = useState<string[]>(() => accounts.map((a) => a.id))
  const preview = useQuery({ ...updatePreviewQuery(chosen), enabled: chosen.length > 0 })
  const start = useStartUpdate()
  const names = accounts.filter((a) => chosen.includes(a.id)).map((a) => a.name)
  const changed = preview.data?.accounts.reduce((n, a) => n + a.changed, 0) ?? 0
  const waiting = preview.data?.waiting ?? 0
  const notReady = accounts.filter((a) => chosen.includes(a.id) && !a.ready)

  function toggle(id: string, on: boolean) {
    setChosen((list) => (on ? [...list, id] : list.filter((x) => x !== id)))
  }

  async function confirm() {
    try {
      await start.mutateAsync(chosen)
      onClose()
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : 'The update didn’t start. Try again.')
    }
  }

  return (
    <Dialog open onOpenChange={(next: boolean) => !next && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Update my lessons</DialogTitle>
          <DialogDescription>
            Are you sure you want to fetch {names.length ? <b className="text-ink">{names.join(' and ')}</b> : 'the chosen'}{' '}
            data and generate lessons based on it?
          </DialogDescription>
        </DialogHeader>

        {accounts.length > 1 && (
          <fieldset className="grid gap-2">
            <legend className="mb-1 text-sm font-bold">Accounts</legend>
            {accounts.map((a) => (
              <label key={a.id} className="flex items-center gap-3 rounded-lg border px-3 py-2.5 hover:bg-sunk/50">
                <Checkbox checked={chosen.includes(a.id)} onCheckedChange={(on: boolean) => toggle(a.id, on)} />
                <span className="grid">
                  <span className="font-bold">{a.name}</span>
                  <span className="text-sm text-ink-2">{a.email ?? (a.method === 'api-key' ? 'API key' : 'Claude Code sign-in')}</span>
                </span>
              </label>
            ))}
          </fieldset>
        )}

        <div className="grid gap-1 rounded-lg bg-sunk/60 px-4 py-3 text-sm">
          {preview.isPending && chosen.length > 0 ? (
            <span className="text-ink-2">Looking for new conversations…</span>
          ) : (
            <>
              <span>
                <b>{plural(changed, 'conversation')}</b> {changed === 1 ? 'has' : 'have'} new activity since{' '}
                {preview.data?.last_finished_at ? `your last update (${fromNow(preview.data.last_finished_at)})` : 'they were last read'}.
              </span>
              {waiting > 0 && <span className="text-ink-2">{plural(waiting, 'message')} from before {waiting === 1 ? 'is' : 'are'} also waiting.</span>}
            </>
          )}
          <span className="text-ink-2">
            Only new messages are checked. It uses your Claude usage (or API key) and can take a few minutes.
          </span>
        </div>
        {notReady.length > 0 && (
          <p className="text-sm text-mark">
            {notReady.map((a) => a.name).join(' and ')} can&rsquo;t reach Claude right now. Check {notReady.length === 1 ? 'it' : 'them'} in Settings.
          </p>
        )}

        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
          <Button disabled={!chosen.length || start.isPending} onClick={() => void confirm()}>
            <RefreshCw aria-hidden /> Fetch and generate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
