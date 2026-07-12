import { cn } from '@f0rge/ui'

interface MarrowMarkProps {
  className?: string
  /** Pixel size — minimum 16 per brand kit. */
  size?: number
}

/** Open membrane mark — mono, nucleus uses `--marrow-nucleus`. */
export function MarrowMark({ className, size = 24 }: MarrowMarkProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 100 100"
      role="img"
      aria-label="Marrow"
      width={size}
      height={size}
      className={cn('shrink-0', className)}
    >
      <path
        d="M84.38 39.47 C86.06 44.25 87 49.5 87 55 C87 72 69 86 47 86 C28 86 13 68 13 46 C13 29 31 15 54 15 C59.04 15 63.84 16.41 68.15 18.93"
        fill="none"
        stroke="currentColor"
        strokeWidth="10"
        strokeLinecap="round"
      />
      <circle cx="41" cy="58" r="12" fill="var(--marrow-nucleus)" />
    </svg>
  )
}
