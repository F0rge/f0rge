'use client'

import { cn } from '@f0rge/ui'

// Maximum label length for a segmented control segment.
// Longest current label is 9 chars ("Very Poor" / "Very Good"), 3-char buffer
// for future labels. Beyond 12 chars the segment columns become too narrow at
// typical card widths (~340–420px) — use a different component instead.
export const MAX_SCALE_LABEL_LENGTH = 12

// Segmented controls cap at 5 options (raised from 4 for v4's 5-point core
// scales). Keep labels short — five columns at ~70px each on a 390px phone
// only work with short labels; six+ columns would not.
export const MAX_SCALE_OPTIONS = 5

interface ScaleOption {
  value: number | string
  label: string
}

interface ScaleInputProps {
  label: string
  options: ScaleOption[]
  value: number | string | null
  onChange: (value: number | string) => void
  description?: string
}

/**
 * Dev-only guard. Throws with a precise message so the caller can fix the data
 * rather than silently degrading the UI. No-ops in production.
 */
function assertValidScaleOptions(options: ScaleOption[]): void {
  if (process.env.NODE_ENV === 'production') return

  if (options.length > MAX_SCALE_OPTIONS) {
    throw new Error(
      `ScaleInput: received ${options.length} options but the maximum is ${MAX_SCALE_OPTIONS}. ` +
        `Use a different component for more options.`,
    )
  }

  for (const option of options) {
    if (option.label.length > MAX_SCALE_LABEL_LENGTH) {
      throw new Error(
        `ScaleInput: label "${option.label}" is ${option.label.length} chars, ` +
          `which exceeds MAX_SCALE_LABEL_LENGTH (${MAX_SCALE_LABEL_LENGTH}). ` +
          `Shorten the label or use a different component.`,
      )
    }
  }
}

export function ScaleInput({ label, options, value, onChange, description }: ScaleInputProps) {
  assertValidScaleOptions(options)

  const isProduction = process.env.NODE_ENV === 'production'
  const unset = value === null || value === ''

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <label className="text-sm font-semibold leading-none">{label}</label>
        {unset && (
          <span
            aria-hidden
            className="size-2 shrink-0 rounded-full bg-chart-1 motion-safe:animate-[em-needle_1.8s_ease-in-out_infinite]"
          />
        )}
      </div>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
      <div
        className={cn(
          'relative grid w-full rounded-full p-1 gap-0.5',
          unset ? 'bg-muted ring-1 ring-dashed ring-chart-1/70' : 'bg-border',
        )}
        style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
        role="radiogroup"
        aria-label={unset ? `${label}, not rated yet` : label}
      >
        {options.map((option) => {
          const isActive = !unset && value === option.value
          return (
            <button
              key={String(option.value)}
              type="button"
              role="radio"
              aria-checked={isActive}
              onClick={() => onChange(option.value)}
              className={cn(
                'relative z-20 inline-flex items-center justify-center',
                'min-h-[44px] rounded-full px-2.5',
                'text-sm font-medium',
                'transition-all duration-300 ease-[cubic-bezier(0.19,1,0.22,1)]',
                'active:scale-[0.97]',
                'focus-visible:outline-2 focus-visible:outline-foreground focus-visible:outline-offset-2',
                isProduction ? 'overflow-hidden text-ellipsis' : 'whitespace-nowrap',
                isActive
                  ? 'bg-primary text-primary-foreground font-semibold shadow-sm'
                  : 'bg-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              {option.label}
            </button>
          )
        })}
      </div>
      {unset && <p className="text-[11px] text-muted-foreground">Not rated — tap a level</p>}
    </div>
  )
}
