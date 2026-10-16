import { use } from 'react'
import { ThemeContext, type ThemeState } from '@/lib/theme'

export function useTheme(): ThemeState {
  const state = use(ThemeContext)
  if (!state) throw new Error('useTheme must be used inside <ThemeProvider>')
  return state
}
