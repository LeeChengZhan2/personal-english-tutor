import { vi } from 'vitest'

/** A voice as the browser lists it (Windows' own voices are local; Edge's natural voices are online). */
export function voice(name: string, lang = 'en-US', localService = true): SpeechSynthesisVoice {
  return { name, lang, localService, voiceURI: name, default: false }
}

export class FakeUtterance extends EventTarget {
  text: string
  voice: SpeechSynthesisVoice | null = null
  lang = ''
  rate = 1

  constructor(text: string) {
    super()
    this.text = text
  }

  /** The browser finishing it ("end"), or cutting it off for the next one ("error"). */
  finish(type: 'end' | 'error' = 'end'): void {
    this.dispatchEvent(new Event(type))
  }
}

/** Puts a fake speechSynthesis on the window (jsdom has none). `spoken` collects every utterance read aloud. */
export function fakeSpeech(voices: SpeechSynthesisVoice[] = []) {
  const spoken: FakeUtterance[] = []
  const synth = {
    speaking: false,
    pending: false,
    getVoices: () => voices,
    speak: vi.fn<(utterance: FakeUtterance) => void>((utterance) => void spoken.push(utterance)),
    cancel: vi.fn<() => void>(),
    addEventListener: vi.fn<(type: string, listener: () => void) => void>(),
    removeEventListener: vi.fn<(type: string, listener: () => void) => void>(),
  }
  vi.stubGlobal('speechSynthesis', synth)
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  return { synth, spoken }
}
