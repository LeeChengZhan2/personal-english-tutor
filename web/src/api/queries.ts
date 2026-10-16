import { infiniteQueryOptions, queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, unwrap, type Schemas } from './client'

export type WordKind = Schemas['WordBrief']['kind']
export type MessageFilter = 'mistakes' | 'all'

export const keys = {
  bootstrap: ['bootstrap'] as const,
  home: ['home'] as const,
  patterns: ['patterns'] as const,
  pattern: (key: string, page: number) => ['patterns', key, { page }] as const,
  words: (kind: WordKind, page: number) => ['words', { kind, page }] as const,
  messages: (filter: MessageFilter) => ['messages', { filter }] as const,
  message: (id: string) => ['message', id] as const,
  progress: ['progress'] as const,
  status: ['status'] as const,
}

/** Queries that show lesson content: refreshed when new lessons arrive or after practice. */
export const CONTENT_KEYS = [keys.home, keys.patterns, ['words'], ['messages'], ['message'], keys.progress] as const

export const bootstrapQuery = () =>
  queryOptions({
    queryKey: keys.bootstrap,
    queryFn: ({ signal }) => unwrap(api.GET('/api/bootstrap', { signal })),
    refetchInterval: 60_000,
  })

export const homeQuery = () =>
  queryOptions({ queryKey: keys.home, queryFn: ({ signal }) => unwrap(api.GET('/api/home', { signal })) })

export const patternsQuery = () =>
  queryOptions({ queryKey: keys.patterns, queryFn: ({ signal }) => unwrap(api.GET('/api/patterns', { signal })) })

export const patternQuery = (key: string, page: number) =>
  queryOptions({
    queryKey: keys.pattern(key, page),
    queryFn: ({ signal }) =>
      unwrap(api.GET('/api/patterns/{key}', { params: { path: { key }, query: { page, page_size: 20 } }, signal })),
  })

export const wordsQuery = (kind: WordKind, page: number) =>
  queryOptions({
    queryKey: keys.words(kind, page),
    queryFn: ({ signal }) => unwrap(api.GET('/api/words', { params: { query: { kind, page, page_size: 24 } }, signal })),
  })

export const messagesQuery = (filter: MessageFilter) =>
  infiniteQueryOptions({
    queryKey: keys.messages(filter),
    queryFn: ({ pageParam, signal }) =>
      unwrap(api.GET('/api/messages', { params: { query: { filter, limit: 30, cursor: pageParam ?? undefined } }, signal })),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  })

export const messageQuery = (id: string) =>
  queryOptions({
    queryKey: keys.message(id),
    queryFn: ({ signal }) => unwrap(api.GET('/api/messages/{message_id}', { params: { path: { message_id: id } }, signal })),
  })

export const progressQuery = () =>
  queryOptions({ queryKey: keys.progress, queryFn: ({ signal }) => unwrap(api.GET('/api/progress', { signal })) })

export const statusQuery = () =>
  queryOptions({ queryKey: keys.status, queryFn: ({ signal }) => unwrap(api.GET('/api/status', { signal })) })

// ---------- accounts and "Update my lessons" ----------

export const accountKeys = {
  all: ['accounts'] as const,
  update: ['update'] as const,
  preview: (ids: string[]) => ['update', 'preview', ids] as const,
}

export const accountsQuery = () =>
  queryOptions({ queryKey: accountKeys.all, queryFn: ({ signal }) => unwrap(api.GET('/api/accounts', { signal })) })

export const updateStatusQuery = () =>
  queryOptions({
    queryKey: accountKeys.update,
    queryFn: ({ signal }) => unwrap(api.GET('/api/update', { signal })),
    refetchInterval: (query) => (query.state.data?.state === 'running' ? 1500 : 60_000),
  })

export const updatePreviewQuery = (ids: string[]) =>
  queryOptions({
    queryKey: accountKeys.preview(ids),
    queryFn: ({ signal }) => unwrap(api.GET('/api/update/preview', { params: { query: { account_ids: ids } }, signal })),
    staleTime: 0,
  })

function useAccountsChanged() {
  const client = useQueryClient()
  return () => {
    void client.invalidateQueries({ queryKey: accountKeys.all })
    void client.invalidateQueries({ queryKey: keys.bootstrap })
    void client.invalidateQueries({ queryKey: keys.status })
  }
}

export function useAddAccount() {
  const changed = useAccountsChanged()
  return useMutation({
    mutationFn: (body: Schemas['AccountIn']) => unwrap(api.POST('/api/accounts', { body })),
    onSuccess: changed,
  })
}

export function useEditAccount() {
  const changed = useAccountsChanged()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas['AccountUpdate'] }) =>
      unwrap(api.PUT('/api/accounts/{account_id}', { params: { path: { account_id: id } }, body })),
    onSuccess: changed,
  })
}

export function useRemoveAccount() {
  const changed = useAccountsChanged()
  return useMutation({
    mutationFn: async (id: string) => {
      const { response } = await api.DELETE('/api/accounts/{account_id}', { params: { path: { account_id: id } } })
      if (!response.ok) throw new Error("That account wasn't removed. Try again.")
    },
    onSuccess: changed,
  })
}

export function useCheckAccount() {
  return useMutation({
    mutationFn: (id: string) => unwrap(api.POST('/api/accounts/{account_id}/check', { params: { path: { account_id: id } } })),
  })
}

export function useStartUpdate() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (accountIds: string[]) => unwrap(api.POST('/api/update', { body: { account_ids: accountIds } })),
    onSuccess: (status) => client.setQueryData(updateStatusQuery().queryKey, status),
  })
}

export function useStopUpdate() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/update/stop')),
    onSuccess: (status) => client.setQueryData(updateStatusQuery().queryKey, status),
  })
}

/** The opening data (counts, settings, AI and pipeline status), kept fresh by polling. */
export function useBootstrap() {
  return useQuery(bootstrapQuery())
}

/** Practice settings stored on the server (Chinese hints, round size, new cards per day). */
export function useSettings(): Schemas['PracticeSettings'] {
  return useBootstrap().data?.settings ?? { zh: false, round_size: 8, new_per_day: 12 }
}

export function useSaveSettings() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (update: Schemas['SettingsUpdate']) => unwrap(api.PUT('/api/settings', { body: update })),
    onMutate: async (update) => {
      const key = bootstrapQuery().queryKey // typed: getQueryData returns Bootstrap
      await client.cancelQueries({ queryKey: key })
      const before = client.getQueryData(key)
      if (before) {
        const settings = { ...before.settings }
        for (const [k, v] of Object.entries(update)) if (v !== null && v !== undefined) Object.assign(settings, { [k]: v })
        client.setQueryData(key, { ...before, settings })
      }
      return { before }
    },
    onError: (_error, _update, context) => {
      if (context?.before) client.setQueryData(bootstrapQuery().queryKey, context.before)
      toast.error("That setting wasn't saved. Try again.")
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.bootstrap })
      void client.invalidateQueries({ queryKey: keys.home })
    },
  })
}
