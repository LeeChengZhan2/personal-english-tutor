import { useCallback, useLayoutEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from 'react'
import {
  applyTheme,
  readTheme,
  subscribeSystemTheme,
  systemPrefersDark,
  ThemeContext,
  writeTheme,
  type ResolvedTheme,
  type Theme,
} from '@/lib/theme'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readTheme)
  const prefersDark = useSyncExternalStore(subscribeSystemTheme, systemPrefersDark, () => false)
  const resolved: ResolvedTheme = theme === 'system' ? (prefersDark ? 'dark' : 'light') : theme

  useLayoutEffect(() => applyTheme(resolved), [resolved])

  const setTheme = useCallback((next: Theme) => {
    writeTheme(next)
    setThemeState(next)
  }, [])

  const value = useMemo(() => ({ theme, resolved, setTheme }), [theme, resolved, setTheme])
  return <ThemeContext value={value}>{children}</ThemeContext>
}
