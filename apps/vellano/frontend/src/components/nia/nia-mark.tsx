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

  const fill = `url(#${gradientId})`;
  const stroke = {
    fill: "none",
    stroke: fill,
    strokeWidth: 3.25,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
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
        {/* userSpaceOnUse — objectBoundingBox collapses on zero-width vertical strokes */}
        <filter
          id={glowId}
          filterUnits="userSpaceOnUse"
          x="-3"
          y="-3"
          width="30"
          height="30"
        >
          <feGaussianBlur stdDeviation="1.1" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g filter={`url(#${glowId})`}>
        {/* Pillars — filled rects so stems stay visible under the glow filter */}
        <rect x="4.5" y="4.5" width="3.5" height="15" rx="1.75" fill={fill} />
        <rect x="16" y="4.5" width="3.5" height="15" rx="1.75" fill={fill} />
        {/* Upper diagonal stub */}
        <path d="M 7.9 5 L 12.25 10.25" {...stroke} />
        {/* Lower diagonal stub */}
        <path d="M 16.1 19 L 13.25 14.25" {...stroke} />
        {/* Smile — lower diagonal of the N */}
        <path d="M 7.9 12.75 C 10.25 17.25, 13.75 18.25, 16.1 19" {...stroke} />
        <circle cx="10" cy="11.25" r="1.2" fill={fill} />
        <circle cx="14" cy="11.25" r="1.2" fill={fill} />
      </g>
    </svg>
  );
}
