'use client';

interface SheetPreviewProps {
  leftMargin: number;
  topMargin: number;
  tagWidth: number;
  tagHeight: number;
  innerPadding: number;
  orientation: 'P' | 'L';
}

export default function SheetPreview({
  leftMargin,
  topMargin,
  tagWidth,
  tagHeight,
  innerPadding,
  orientation,
}: SheetPreviewProps) {
  const pageW = orientation === 'L' ? 297 : 210;
  const pageH = orientation === 'L' ? 210 : 297;

  // Guard against non-positive / NaN dimensions before building the grid.
  const w = Number.isFinite(tagWidth) && tagWidth > 0 ? tagWidth : 0;
  const h = Number.isFinite(tagHeight) && tagHeight > 0 ? tagHeight : 0;
  const lm = Number.isFinite(leftMargin) && leftMargin >= 0 ? leftMargin : 0;
  const tm = Number.isFinite(topMargin) && topMargin >= 0 ? topMargin : 0;
  // Match backend clamp: inner_padding capped so inner width stays positive.
  const pad = Math.max(0, Math.min(Number.isFinite(innerPadding) ? innerPadding : 0, (w - 0.1) / 2));

  // Mirror the backend grid: columns step by tagWidth while a full tag fits.
  const xs: number[] = [];
  if (w > 0) {
    for (let x = lm; x + w <= pageW - lm + 0.5; x += w) xs.push(x);
  }
  const ys: number[] = [];
  if (h > 0) {
    for (let y = tm; y + h <= pageH - tm + 0.5; y += h) ys.push(y);
  }

  const cols = xs.length;
  const rows = ys.length;
  const rowH = h / 3;

  return (
    <div>
      <div className="mx-auto max-h-[420px] w-full">
        <svg
          viewBox={`0 0 ${pageW} ${pageH}`}
          className="mx-auto h-auto max-h-[420px] w-full"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Page */}
          <rect
            x={0}
            y={0}
            width={pageW}
            height={pageH}
            fill="oklch(var(--card))"
            stroke="oklch(var(--border))"
            strokeWidth={0.6}
          />

          {/* Dashed margin guides */}
          {w > 0 && (
            <line
              x1={lm}
              y1={0}
              x2={lm}
              y2={pageH}
              stroke="oklch(var(--muted-foreground))"
              strokeWidth={0.4}
              strokeDasharray="3 3"
            />
          )}
          {h > 0 && (
            <line
              x1={0}
              y1={tm}
              x2={pageW}
              y2={tm}
              stroke="oklch(var(--muted-foreground))"
              strokeWidth={0.4}
              strokeDasharray="3 3"
            />
          )}

          {/* Tags */}
          {ys.map((y) =>
            xs.map((x) => {
              const innerX = x + pad;
              const innerW = w - 2 * pad;
              return (
                <g key={`${x}-${y}`}>
                  {/* Cell hint (full tagWidth footprint) */}
                  <rect
                    x={x}
                    y={y}
                    width={w}
                    height={h}
                    fill="none"
                    stroke="oklch(var(--border))"
                    strokeWidth={0.2}
                  />
                  {/* Printed box */}
                  <rect
                    x={innerX}
                    y={y}
                    width={innerW}
                    height={h}
                    fill="oklch(var(--muted))"
                    stroke="oklch(var(--foreground))"
                    strokeWidth={0.4}
                  />
                  {/* Placeholder lines: code / name / price */}
                  {[0.5, 1.5, 2.5].map((mult, li) => (
                    <line
                      key={li}
                      x1={innerX + 1}
                      y1={y + rowH * mult}
                      x2={innerX + innerW - 1}
                      y2={y + rowH * mult}
                      stroke="oklch(var(--muted-foreground))"
                      strokeWidth={0.4}
                    />
                  ))}
                </g>
              );
            })
          )}
        </svg>
      </div>
      <p className="mt-2 text-center text-xs text-muted-foreground">
        {cols} × {rows} = {cols * rows} tags per A4 page
      </p>
    </div>
  );
}
