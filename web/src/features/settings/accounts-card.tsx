import { useQuery } from '@tanstack/react-query'
import { CircleCheck, CircleX, KeyRound, Pencil, Plus, ShieldCheck, Trash2, UserRound } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ApiError, type Schemas } from '@/api/client'
import { accountsQuery, useAddAccount, useCheckAccount, useEditAccount, useRemoveAccount } from '@/api/queries'
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
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

type Account = Schemas['AccountOut']
type Method = Account['method']

export function AccountsCard() {
  const { data } = useQuery(accountsQuery())
  const [editing, setEditing] = useState<Account | 'new' | null>(null)
  const [removing, setRemoving] = useState<Account | null>(null)
  const accounts = data?.accounts ?? []
  return (
    <section id="accounts" className="grid gap-1 rounded-xl border bg-surface px-6 py-5 shadow-e1 scroll-mt-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <h2 className="type-h3">Accounts</h2>
          <p className="max-w-[60ch] text-sm text-ink-2">
            Your lessons are made from these accounts&rsquo; Claude Code conversations on this PC. If one account hits
            its usage limit, the next one is used.
          </p>
        </div>
        <Button onClick={() => setEditing('new')}>
          <Plus aria-hidden /> Add account
        </Button>
      </div>
      {accounts.length === 0 ? (
        <div className="mt-3 grid gap-1 rounded-lg border-2 border-dashed px-4 py-4">
          <p className="font-bold">No account yet</p>
          <p className="text-sm text-ink-2">
            Add the Claude account you use with Claude Code. If you use two accounts, add both.
          </p>
        </div>
      ) : (
        <ul className="mt-2 grid divide-y">
          {accounts.map((a, i) => (
            <AccountRow key={a.id} account={a} first={i === 0} onEdit={() => setEditing(a)} onRemove={() => setRemoving(a)} />
          ))}
        </ul>
      )}
      {editing && (
        <AccountDialog
          account={editing === 'new' ? null : editing}
          defaultFolder={data?.default_folder ?? '~/.claude'}
          claudeInstalled={data?.claude_installed ?? false}
          onClose={() => setEditing(null)}
        />
      )}
      <RemoveDialog account={removing} onClose={() => setRemoving(null)} />
    </section>
  )
}

function AccountRow({ account: a, first, onEdit, onRemove }: { account: Account; first: boolean; onEdit: () => void; onRemove: () => void }) {
  const check = useCheckAccount()
  const result = check.data
  return (
    <li className="grid gap-2 py-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {a.method === 'api-key' ? <KeyRound className="size-4 text-ink-3" aria-hidden /> : <UserRound className="size-4 text-ink-3" aria-hidden />}
        <span className="font-bold">{a.name}</span>
        <span className="rounded-md bg-sunk px-2 py-0.5 text-[13px] font-bold text-ink-2">
          {a.method === 'api-key' ? 'API key' : 'Claude Code sign-in'}
        </span>
        {a.limited_until ? (
          <span className="text-sm font-bold text-amber">Limit reached · resets {a.limited_until}</span>
        ) : a.ready ? (
          <span className="inline-flex items-center gap-1 text-sm font-bold text-ok">
            <CircleCheck className="size-4" aria-hidden /> Ready{first ? ' · used first' : ' · backup'}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-sm font-bold text-mark">
            <CircleX className="size-4" aria-hidden /> {a.method === 'api-key' ? 'No key saved' : 'Not signed in'}
          </span>
        )}
      </div>
      <div className="grid gap-0.5 text-sm text-ink-2">
        {a.method === 'api-key' ? <span>Key {a.api_key_hint}</span> : <span>{a.email ?? 'Not signed in to Claude Code'}</span>}
        <span className="[overflow-wrap:anywhere]">
          {a.conversation_files} conversation file{a.conversation_files === 1 ? '' : 's'} in{' '}
          {a.default_folder ? "Claude Code's normal folder" : a.folder_path}
        </span>
      </div>
      {result && (
        <p className={result.ok ? 'text-sm text-ok' : 'text-sm text-mark'} role="status">
          {result.message}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" disabled={check.isPending} onClick={() => check.mutate(a.id)}>
          <ShieldCheck aria-hidden /> {check.isPending ? 'Checking…' : 'Check'}
        </Button>
        <Button variant="ghost" size="sm" onClick={onEdit}>
          <Pencil aria-hidden /> Edit
        </Button>
        <Button variant="ghost" size="sm" className="text-mark hover:text-mark" onClick={onRemove}>
          <Trash2 aria-hidden /> Remove
        </Button>
      </div>
    </li>
  )
}

function AccountDialog({ account, defaultFolder, claudeInstalled, onClose }: { account: Account | null; defaultFolder: string; claudeInstalled: boolean; onClose: () => void }) {
  const add = useAddAccount()
  const edit = useEditAccount()
  const [name, setName] = useState(account?.name ?? '')
  const [method, setMethod] = useState<Method>(account?.method ?? (claudeInstalled ? 'claude-code' : 'api-key'))
  const [apiKey, setApiKey] = useState('')
  const [folderMode, setFolderMode] = useState<'default' | 'other'>(account && !account.default_folder ? 'other' : 'default')
  const [folder, setFolder] = useState(account && !account.default_folder ? account.folder : '')
  const [error, setError] = useState<string | null>(null)
  const saving = add.isPending || edit.isPending

  async function save() {
    setError(null)
    const chosenFolder = folderMode === 'default' ? '' : folder.trim()
    if (folderMode === 'other' && !chosenFolder) {
      setError('Type the folder, or choose Claude Code’s normal folder.')
      return
    }
    try {
      if (account) {
        await edit.mutateAsync({ id: account.id, body: { name: name.trim(), method, folder: chosenFolder, api_key: apiKey.trim() || null } })
        toast.success('Account saved')
      } else {
        await add.mutateAsync({ name: name.trim(), method, folder: chosenFolder, api_key: apiKey.trim() })
        toast.success('Account added')
      }
      onClose()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'That didn’t save. Try again.')
    }
  }

  return (
    <Dialog open onOpenChange={(next: boolean) => !next && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{account ? `Edit ${account.name}` : 'Add an account'}</DialogTitle>
          <DialogDescription>Where this account&rsquo;s conversations are, and how the app may call Claude with it.</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-5"
          onSubmit={(e) => {
            e.preventDefault()
            void save()
          }}
        >
          <div className="grid gap-1.5">
            <label htmlFor="account-name" className="text-sm font-bold">
              Name
            </label>
            <Input id="account-name" required maxLength={40} placeholder="For example: Work, Personal" value={name}
              onChange={(e) => setName(e.target.value)} className="h-11" />
          </div>

          <fieldset className="grid gap-2">
            <legend className="mb-1 text-sm font-bold">How to call Claude</legend>
            <RadioGroup value={method} onValueChange={(v: string) => setMethod(v as Method)} className="grid gap-2">
              <label className="flex items-start gap-3 rounded-lg border px-3 py-2.5">
                <RadioGroupItem value="claude-code" className="mt-1" />
                <span className="grid">
                  <span className="font-bold">Claude Code sign-in</span>
                  <span className="text-sm text-ink-2">
                    Uses your Claude plan, no extra cost.{!claudeInstalled && ' Needs Claude Code installed on this PC.'}
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-3 rounded-lg border px-3 py-2.5">
                <RadioGroupItem value="api-key" className="mt-1" />
                <span className="grid">
                  <span className="font-bold">API key</span>
                  <span className="text-sm text-ink-2">From console.anthropic.com. Paid per use; works without Claude Code.</span>
                </span>
              </label>
            </RadioGroup>
          </fieldset>

          {method === 'api-key' && (
            <div className="grid gap-1.5">
              <label htmlFor="account-key" className="text-sm font-bold">
                API key
              </label>
              <Input id="account-key" type="password" autoComplete="off" spellCheck={false} className="h-11 font-mono"
                placeholder={account?.api_key_hint ? `Saved: ${account.api_key_hint} (leave empty to keep)` : 'sk-ant-…'}
                value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
              <p className="text-sm text-ink-2">Kept only on this PC, in data/accounts.json. It&rsquo;s never shown again.</p>
            </div>
          )}

          <fieldset className="grid gap-2">
            <legend className="mb-1 text-sm font-bold">Conversations folder</legend>
            <RadioGroup value={folderMode} onValueChange={(v: string) => setFolderMode(v as 'default' | 'other')} className="grid gap-2">
              <label className="flex items-start gap-3 rounded-lg border px-3 py-2.5">
                <RadioGroupItem value="default" className="mt-1" />
                <span className="grid min-w-0">
                  <span className="font-bold">Claude Code&rsquo;s normal folder</span>
                  <span className="text-sm text-ink-2 [overflow-wrap:anywhere]">{defaultFolder}</span>
                </span>
              </label>
              <label className="flex items-start gap-3 rounded-lg border px-3 py-2.5">
                <RadioGroupItem value="other" className="mt-1" />
                <span className="grid min-w-0 flex-1 gap-2">
                  <span className="font-bold">Another folder</span>
                  <span className="text-sm text-ink-2">If this account uses its own Claude Code folder (CLAUDE_CONFIG_DIR).</span>
                  {folderMode === 'other' && (
                    <Input aria-label="Folder" placeholder="C:\Users\you\.claude-work" value={folder}
                      onChange={(e) => setFolder(e.target.value)} className="h-10 font-mono" />
                  )}
                </span>
              </label>
            </RadioGroup>
          </fieldset>

          {error && <p className="text-sm text-mark" role="alert">{error}</p>}
          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>Cancel</DialogClose>
            <Button type="submit" disabled={saving || !name.trim()}>
              {saving ? 'Saving…' : account ? 'Save' : 'Add account'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function RemoveDialog({ account, onClose }: { account: Account | null; onClose: () => void }) {
  const remove = useRemoveAccount()
  return (
    <AlertDialog open={account !== null} onOpenChange={(next: boolean) => !next && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove {account?.name}?</AlertDialogTitle>
          <AlertDialogDescription>
            Your lessons and progress stay. The app just stops using this account{account?.method === 'api-key' && ' and forgets its API key'}.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => {
              if (!account) return
              remove.mutate(account.id, {
                onSuccess: () => toast.success('Account removed'),
                onError: () => toast.error("That account wasn't removed. Try again."),
              })
              onClose()
            }}
          >
            Remove
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
