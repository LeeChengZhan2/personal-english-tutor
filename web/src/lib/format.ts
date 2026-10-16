// Dates and counts in short, plain English ("Fri 16 Oct", "3 cards").

const dayFormat = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
const shortFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })
const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** A local calendar day ("2026-10-16") or an ISO timestamp, as a Date. */
export function toDate(value: string): Date {
  const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (day) return new Date(Number(day[1]), Number(day[2]) - 1, Number(day[3]))
  return new Date(value)
}

/** "Fri 16 Oct" */
export const fmtDay = (value: string | null | undefined): string => (value ? dayFormat.format(toDate(value)) : '')

/** "16 Oct" */
export const fmtShort = (value: string | null | undefined): string => (value ? shortFormat.format(toDate(value)) : '')

/** "2:05 pm" (in the reader's own clock style) */
export const fmtTime = (value: string | null | undefined): string => (value ? timeFormat.format(toDate(value)) : '')

/** "3 cards", "1 card", "2 fixes" */
export function plural(n: number, one: string, many?: string): string {
  return `${n} ${n === 1 ? one : (many ?? `${one}s`)}`
}

export function greeting(now = new Date()): string {
  const h = now.getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

/** "in 3 days", "2 hours ago", "now" */
export function fromNow(value: string | null | undefined, now = Date.now()): string {
  if (!value) return ''
  const diff = toDate(value).getTime() - now
  const abs = Math.abs(diff)
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['day', 86_400_000],
    ['hour', 3_600_000],
    ['minute', 60_000],
  ]
  for (const [unit, ms] of units) {
    if (abs >= ms) return relative.format(Math.round(diff / ms), unit)
  }
  return 'now'
}

/** One decimal place: 11.92 -> "11.9". */
export const fmt1 = (n: number | null | undefined): string => (n === null || n === undefined ? '–' : n.toFixed(1))

/** Whole percent, or an en dash when there is nothing to divide. */
export function percent(part: number, total: number): string {
  return total ? `${Math.round((100 * part) / total)}%` : '–'
}
