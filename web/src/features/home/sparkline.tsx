/** A tiny trend line (no axes): the shape of the last weeks, the latest point marked. */
export function Sparkline({ values, className, label }: { values: number[]; className?: string; label: string }) {
  if (values.length < 2) return null
  const W = 120
  const H = 36
  const max = Math.max(...values, 1)
  const x = (i: number) => (i * (W - 6)) / (values.length - 1) + 3
  const y = (v: number) => H - 4 - ((H - 8) * v) / max
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const last = values.length - 1
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMinYMid meet" className={className} role="img" aria-label={label}>
      <path d={d} fill="none" stroke="var(--chart-1)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(last)} cy={y(values[last]!)} r="3.5" fill="var(--chart-1)" />
    </svg>
  )
}
