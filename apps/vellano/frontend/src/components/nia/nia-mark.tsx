import { useId } from "react";

type NiaMarkProps = {
  size?: number;
  className?: string;
};

/** Nia brand mark — Smile N monogram (blue→purple gradient, soft glow). */
export function NiaMark({ size = 20, className = "" }: NiaMarkProps) {
  const uid = useId().replace(/:/g, "");
  const gradientId = `vellano-nia-mark-gradient-${uid}`;
  const glowId = `vellano-nia-mark-glow-${uid}`;

  const stroke = {
    fill: "none",
    stroke: `url(#${gradientId})`,
    strokeWidth: 3.25,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    filter: `url(#${glowId})`,
  };

  return (
    <svg
      className={`vellano-nia-mark ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden
    >
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#4589ff" />
          <stop offset="100%" stopColor="#a56eff" />
        </linearGradient>
        <filter id={glowId} filterUnits="userSpaceOnUse" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.1" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {/* Left pillar */}
      <path d="M 6.25 4.75 L 6.25 19.25" {...stroke} />
      {/* Right pillar */}
      <path d="M 17.75 4.75 L 17.75 19.25" {...stroke} />
      {/* Upper diagonal stub */}
      <path d="M 7.9 4.75 L 12.25 10.25" {...stroke} />
      {/* Smile — lower diagonal of the N */}
      <path d="M 7.9 12.75 C 10.25 17.25, 13.75 18.25, 16.1 19.25" {...stroke} />
      <circle cx="10" cy="11.25" r="1.2" fill={`url(#${gradientId})`} filter={`url(#${glowId})`} />
      <circle cx="14" cy="11.25" r="1.2" fill={`url(#${gradientId})`} filter={`url(#${glowId})`} />
    </svg>
  );
}
