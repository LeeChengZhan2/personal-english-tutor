import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { accountsQuery, updateStatusQuery } from '@/api/queries'
import { ConfirmUpdateDialog, SetupFirstDialog } from './update-dialogs'

/** The "Update my lessons" flow: with no account, ask to configure one first; otherwise confirm which
 * accounts to fetch, then start. Render `dialogs` somewhere and call `open()` from any button. */
export function useUpdateFlow() {
  const client = useQueryClient()
  const status = useQuery(updateStatusQuery())
  const running = status.data?.state === 'running'
  const [dialog, setDialog] = useState<'none' | 'setup' | 'confirm'>('none')
  const [checking, setChecking] = useState(false)

  async function open() {
    if (running || checking) return
    setChecking(true)
    try {
      const { accounts } = await client.fetchQuery({ ...accountsQuery(), staleTime: 0 })
      setDialog(accounts.length ? 'confirm' : 'setup')
    } catch {
      toast.error("Couldn't load your accounts. Is the app still running?")
    } finally {
      setChecking(false)
    }
  }

  const dialogs = (
    <>
      <SetupFirstDialog open={dialog === 'setup'} onClose={() => setDialog('none')} />
      {dialog === 'confirm' && <ConfirmUpdateDialog onClose={() => setDialog('none')} />}
    </>
  )
  return { open: () => void open(), running, busy: running || checking, dialogs }
}
