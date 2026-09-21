import { useId } from "react";

type NiaMarkProps = {
  size?: number;
  className?: string;
};

/**
 * Nia brand mark — geometric N in a Carbon squircle (IBM blue→purple).
 * Solid fills only so the glyph stays readable at header (20px) and dock (22px).
 */
export function NiaMark({ size = 20, className = "" }: NiaMarkProps) {
  const uid = useId().replace(/:/g, "");
  const gradientId = `firstout-nia-mark-gradient-${uid}`;

  return (
    <svg
      className={`firstout-nia-mark ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden
    >
      <defs>
        <linearGradient id={gradientId} x1="8%" y1="0%" x2="92%" y2="100%">
          <stop offset="0%" stopColor="#4589ff" />
          <stop offset="100%" stopColor="#8a3ffc" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="22" height="22" rx="6" fill={`url(#${gradientId})`} />
      <path
        d="M7.25 17.5V6.5h2.45l4.55 7.35V6.5h2.5v11h-2.45L9.75 10.15V17.5H7.25z"
        fill="#f4f4f4"
      />
      <circle cx="18.15" cy="5.85" r="1.65" fill="#ffffff" />
    </svg>
  );
}
