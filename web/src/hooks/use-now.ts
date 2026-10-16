import { useEffect, useState } from 'react'

/** The current time, updated every `intervalMs` (default a minute), for "back in 3 days"-style labels. */
export function useNow(intervalMs = 60_000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}
