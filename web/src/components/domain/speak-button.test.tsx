import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fakeSpeech, voice } from '@/test/speech'
import { SpeakButton } from './speak-button'

const david = voice('Microsoft David - English (United States)')

afterEach(() => vi.unstubAllGlobals())

describe('SpeakButton', () => {
  it('is hidden when the browser cannot speak', () => {
    const { container } = render(<SpeakButton text="rationale" label="rationale" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('reads the word, then slowly when pressed again soon after', () => {
    const { spoken } = fakeSpeech([david])
    render(<SpeakButton text="rationale" label="rationale" />)
    const button = screen.getByRole('button', { name: 'Listen to rationale' })
    for (let i = 0; i < 3; i += 1) fireEvent.click(button)
    expect(spoken.map((u) => [u.text, u.voice, u.rate])).toEqual([
      ['rationale', david, 0.9],
      ['rationale', david, 0.6],
      ['rationale', david, 0.9],
    ])
  })

  it('reads at normal speed again after a pause', () => {
    const { spoken } = fakeSpeech([david])
    const now = vi.spyOn(Date, 'now').mockReturnValue(1_000_000)
    render(<SpeakButton text="rationale" label="rationale" />)
    const button = screen.getByRole('button', { name: 'Listen to rationale' })
    fireEvent.click(button)
    now.mockReturnValue(1_010_000)
    fireEvent.click(button)
    expect(spoken.map((u) => u.rate)).toEqual([0.9, 0.9])
  })

  it('shows it is playing until the speech ends', () => {
    const { spoken } = fakeSpeech([david])
    render(<SpeakButton text="rationale" label="rationale" />)
    const button = screen.getByRole('button', { name: 'Listen to rationale' })
    fireEvent.click(button)
    expect(button).toHaveClass('text-pencil')
    fireEvent.click(button) // cuts off the first one, which then reports its end: the button stays on
    act(() => spoken[0]?.finish('error'))
    expect(button).toHaveClass('text-pencil')
    act(() => spoken[1]?.finish())
    expect(button).not.toHaveClass('text-pencil')
  })
})
