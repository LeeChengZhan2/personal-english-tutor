import { useSyncExternalStore } from 'react'
import { canSpeak } from '@/lib/speech'

// The browser loads its voices after the page (Edge and Chrome then fire `voiceschanged`), so every component
// shares one list, kept current by one listener.
let voices: SpeechSynthesisVoice[] = []
const listeners = new Set<() => void>()

function load(): void {
  voices = window.speechSynthesis.getVoices()
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  if (!canSpeak()) return () => {}
  const synth = window.speechSynthesis
  if (!listeners.size) {
    synth.addEventListener('voiceschanged', load)
    load()
  }
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
    if (!listeners.size) synth.removeEventListener('voiceschanged', load)
  }
}

const snapshot = () => voices

/** The browser's voices for reading aloud: empty until they load, or when the browser can't speak. */
export function useVoices(): SpeechSynthesisVoice[] {
  return useSyncExternalStore(subscribe, snapshot, snapshot)
}
