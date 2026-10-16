import { useCallback, useState } from 'react'

/** A yes/no remembered on this device (localStorage), e.g. "welcome card dismissed". */
export function useLocalFlag(key: string, initial = false): [boolean, (value: boolean) => void] {
  const [value, setValue] = useState<boolean>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw === null ? initial : raw === 'true'
    } catch {
      return initial
    }
  })
  const set = useCallback(
    (next: boolean) => {
      setValue(next)
      try {
        localStorage.setItem(key, String(next))
      } catch {
        // storage unavailable: remembered until reload
      }
    },
    [key],
  )
  return [value, set]
}
