import { useLocalFlag } from './use-local-flag'

/** Tap-only practice (Settings > This device): rounds never ask to type. On by default on a touch screen. */
export function useTapOnly(): [boolean, (value: boolean) => void] {
  const coarse = typeof window !== 'undefined' && Boolean(window.matchMedia?.('(pointer: coarse)').matches)
  return useLocalFlag('tutor-tap-only', coarse)
}
