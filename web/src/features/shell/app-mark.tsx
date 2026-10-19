import { useId } from 'react'

/** The app's mark: a speech bubble with an "A" cut out of it, as in the favicon. */
export function AppMark({ className }: { className?: string }) {
  const mask = useId()
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <mask id={mask}>
        <rect width="24" height="24" fill="#fff" />
        <path d="M8 15 12 5.5 16 15M9.3 12h5.4" fill="none" stroke="#000" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </mask>
      <path
        mask={`url(#${mask})`}
        d="M6.5 2.5h11A4.5 4.5 0 0 1 22 7v7a4.5 4.5 0 0 1-4.5 4.5h-6l-4.3 3.2c-.7.5-1.2.2-1.2-.6v-2.7A4.5 4.5 0 0 1 2 14V7a4.5 4.5 0 0 1 4.5-4.5z"
      />
    </svg>
  )
}
