type NiaMarkProps = {
  size?: number;
  className?: string;
};

/** Nia brand mark — thin blue→purple gradient with soft glow. */
export function NiaMark({ size = 20, className = "" }: NiaMarkProps) {
  return (
    <svg
      className={`vellano-nia-mark ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden
    >
      <defs>
        <linearGradient id="vellano-nia-mark-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#4589ff" />
          <stop offset="100%" stopColor="#a56eff" />
        </linearGradient>
        <filter id="vellano-nia-mark-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="url(#vellano-nia-mark-gradient)"
        strokeWidth="1.5"
        filter="url(#vellano-nia-mark-glow)"
      />
      <path
        d="M8 14.5c1.2-3 2.4-4.5 4-4.5s2.8 1.5 4 4.5"
        fill="none"
        stroke="url(#vellano-nia-mark-gradient)"
        strokeWidth="1.5"
        strokeLinecap="round"
        filter="url(#vellano-nia-mark-glow)"
      />
      <circle cx="9.5" cy="10" r="1" fill="url(#vellano-nia-mark-gradient)" />
      <circle cx="14.5" cy="10" r="1" fill="url(#vellano-nia-mark-gradient)" />
    </svg>
  );
}
