import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Schemas } from '@/api/client'
import { bootstrapQuery } from '@/api/queries'
import { RoundPlayer } from './word-round'

function word(over: Partial<Schemas['WordBrief']>): Schemas['WordBrief'] {
  return {
    id: 'w', kind: 'new', word: 'w', pos: 'adjective', meaning: '', meaning_zh: '有时', example: '', wrote: [], times: 1,
    last: null, level: 'B2', rewrite: '', status: 'new', strength: 0, due_at: null, ...over,
  }
}

const MEANING: Schemas['WordItem'] = {
  item_id: 'w1',
  exercise: 'meaning',
  gap: null,
  options: ['happening only sometimes', 'no longer needed', 'the reasons behind a decision'],
  answer: 'happening only sometimes',
  word: word({ id: 'w1', word: 'intermittent', meaning: 'happening only sometimes', example: 'We see intermittent failures.',
    wrote: ['sometimes can, sometimes cannot'], rewrite: 'The login error is intermittent.' }),
}

const TYPING: Schemas['WordItem'] = {
  item_id: 'w2',
  exercise: 'type',
  gap: { before: 'Please ', match: 'clarify', after: ' the steps.', source: 'example' },
  options: [],
  answer: 'clarify',
  word: word({ id: 'w2', word: 'clarify', pos: 'verb', meaning: 'to make something clear', example: 'Please clarify the steps.' }),
}

function play(items: Schemas['WordItem'][]) {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } })
  client.setQueryData(bootstrapQuery().queryKey, { settings: { zh: false, round_size: 8, new_per_day: 12 } } as Schemas['Bootstrap'])
  const record = vi.fn<(itemId: string, answer: string, seconds: number) => Promise<Schemas['AnswerOut']>>(async (itemId, answer) => ({
    item_id: itemId, correct: answer !== 'no longer needed', answer: '', status: 'learning', strength: 1,
    due_at: new Date(Date.now() + 600_000).toISOString(),
  }))
  const finish = vi.fn<() => Promise<Schemas['RoundScore']>>(async () => ({ answered: 2, correct: 1, words_due: 3 }))
  const onExit = vi.fn<() => void>()
  const view = render(
    <QueryClientProvider client={client}>
      <RoundPlayer round={{ id: 'r1', group: null, items }} title="Word round" record={record} finish={finish} onExit={onExit} onAgain={() => {}} />
    </QueryClientProvider>,
  )
  return { record, finish, onExit, view, user: userEvent.setup() }
}

beforeEach(() => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
})

describe('RoundPlayer', () => {
  it('plays a round: a choice by key, a typed word, the missed word once more, then the score', async () => {
    const { record, finish, user } = play([MEANING, TYPING])
    expect(screen.getByRole('heading', { name: 'What does it mean?' })).toBeInTheDocument()

    await user.keyboard('2') // "no longer needed"
    expect(screen.getByText('Not quite')).toBeInTheDocument()
    expect(record).toHaveBeenCalledWith('w1', 'no longer needed', expect.any(Number))
    expect(screen.getByText('有时')).toBeInTheDocument() // a new word's Chinese meaning is always shown
    expect(await screen.findByText(/back in 10 minutes/)).toBeInTheDocument()

    await user.keyboard('{Enter}') // the Next button has the focus
    expect(screen.getByRole('heading', { name: 'Type the missing word.' })).toBeInTheDocument()
    expect(screen.getByText('Starts with “c” · 7 letters')).toBeInTheDocument()
    await user.keyboard(' Clarify{Enter}') // the box has the focus
    expect(screen.getByText('Right')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Next/ }))
    expect(screen.getByText('Once more')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /happening only sometimes/ }))
    expect(screen.getByText(/isn’t scored/)).toBeInTheDocument()
    expect(record).toHaveBeenCalledTimes(2) // the extra try isn't sent

    await user.click(screen.getByRole('button', { name: /Finish/ }))
    expect(screen.getByRole('heading', { name: '1 of 2 right' })).toBeInTheDocument()
    expect(screen.getByText('Look at these again')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Another round · 3 due/ })).toBeInTheDocument()
    expect(finish).toHaveBeenCalledTimes(1)
  })

  it('gives up on a word to type with Show me', async () => {
    const { record, user } = play([TYPING])
    await user.click(screen.getByRole('button', { name: 'Show me' }))
    expect(screen.getByText('Not quite')).toBeInTheDocument()
    expect(record).toHaveBeenCalledWith('w2', '', expect.any(Number))
    expect(screen.getByRole('textbox', { name: 'Your answer' })).toHaveAttribute('readonly')
  })

  it('ends with Esc, keeping the answers so far; a round with no answers is not counted', async () => {
    const answered = play([MEANING, TYPING])
    await answered.user.keyboard('1')
    await answered.user.keyboard('{Escape}')
    expect(answered.finish).toHaveBeenCalledTimes(1)
    expect(answered.onExit).toHaveBeenCalledTimes(1)
    answered.view.unmount()

    const untouched = play([MEANING])
    await untouched.user.keyboard('{Escape}')
    untouched.view.unmount()
    expect(untouched.onExit).toHaveBeenCalledTimes(1)
    expect(untouched.finish).not.toHaveBeenCalled()
  })
})
