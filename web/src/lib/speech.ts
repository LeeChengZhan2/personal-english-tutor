// Reading words aloud with the browser's own voices (the Web Speech API). Nothing goes to the server: the Windows
// voices work offline, and Edge also offers its natural voices (the ones Read Aloud uses), which need the internet.

const VOICE_KEY = 'tutor-voice'
const RATE = 0.9
const SLOW_RATE = 0.6
// Edge's clearest natural voices, best first. (The first US voice in its list, Ana, is a child's voice.)
const PREFERRED = ['Ava', 'Andrew', 'Emma', 'Brian', 'Jenny', 'Aria', 'Guy']

/** Whether this browser can read aloud. */
export function canSpeak(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window
}

/** Lower is better: natural voices, then other online ones (Chrome's), then Windows' own; US English, then British. */
function rank(voice: SpeechSynthesisVoice): number {
  const kind = voice.name.includes('(Natural)') ? 0 : voice.localService ? 2 : 1
  const lang = voice.lang.replace('_', '-').toLowerCase()
  const region = lang === 'en-us' ? 0 : lang === 'en-gb' ? 1 : 2
  const preferred = PREFERRED.findIndex((name) => new RegExp(`\\b${name}\\b`).test(voice.name))
  return kind * 100 + region * 10 + (preferred < 0 ? PREFERRED.length : preferred)
}

/** The English voices, best first. */
export function englishVoices(voices: readonly SpeechSynthesisVoice[]): SpeechSynthesisVoice[] {
  return voices.filter((v) => /^en(?:[-_]|$)/i.test(v.lang)).toSorted((a, b) => rank(a) - rank(b))
}

/** The voice to read with: the one chosen in Settings while this browser still has it, otherwise the best one. */
export function pickVoice(voices: readonly SpeechSynthesisVoice[], chosen: string): SpeechSynthesisVoice | undefined {
  const english = englishVoices(voices)
  return english.find((v) => v.voiceURI === chosen) ?? english[0]
}

/** "Microsoft Ava Online (Natural) - English (United States)" → "Ava (Natural) - English (United States)" */
export function voiceLabel(voice: SpeechSynthesisVoice): string {
  return voice.name.replace(/^Microsoft\s+/, '').replace(/\s+Online\b/, '')
}

/** The voice chosen in Settings (its voiceURI), saved in this browser only; "" means the best one. */
export function chosenVoice(): string {
  try {
    return localStorage.getItem(VOICE_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setChosenVoice(uri: string): void {
  try {
    if (uri) localStorage.setItem(VOICE_KEY, uri)
    else localStorage.removeItem(VOICE_KEY)
  } catch {
    // storage unavailable: the best voice is used
  }
}

// Held until it ends: Chrome can drop an utterance nothing refers to, and then never fires its `end`.
let current: SpeechSynthesisUtterance | null = null

/** Reads `text` aloud, stopping anything still being read. `onEnd` runs when it finishes, fails or is cut off. */
export function speak(
  text: string,
  voices: readonly SpeechSynthesisVoice[],
  { slow = false, voice = chosenVoice(), onEnd }: { slow?: boolean; voice?: string; onEnd?: () => void } = {},
): void {
  if (!canSpeak()) return
  const synth = window.speechSynthesis
  if (synth.speaking || synth.pending) synth.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  const picked = pickVoice(voices, voice)
  if (picked) utterance.voice = picked
  utterance.lang = picked?.lang ?? 'en-US'
  utterance.rate = slow ? SLOW_RATE : RATE
  const done = () => {
    if (current === utterance) current = null
    onEnd?.()
  }
  utterance.addEventListener('end', done)
  utterance.addEventListener('error', done)
  current = utterance
  synth.speak(utterance)
}
