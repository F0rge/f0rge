'use client'

import {
  cn,
  Field,
  FieldDescription,
  FieldTitle,
  ToggleGroup,
  ToggleGroupItem,
} from '@f0rge/ui'

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

const segmentItemClass =
  'min-h-[44px] min-w-0 flex-1 justify-center px-1.5 text-center text-xs leading-tight whitespace-normal text-pretty sm:px-2.5 sm:text-sm sm:leading-normal sm:whitespace-nowrap data-[state=on]:bg-primary data-[state=on]:font-semibold data-[state=on]:text-primary-foreground data-[state=on]:shadow-sm'

export function ScaleInput({ label, options, value, onChange, description }: ScaleInputProps) {
  assertValidScaleOptions(options)

  const unset = value === null || value === ''
  const selected = unset ? [] : [String(value)]

  return (
    <Field className="gap-2">
      <div className="flex items-center gap-2">
        <FieldTitle className="text-sm font-semibold">{label}</FieldTitle>
        {unset && (
          <span
            aria-hidden
            className="size-2 shrink-0 rounded-full bg-chart-1 motion-safe:animate-[em-needle_1.8s_ease-in-out_infinite]"
          />
        )}
      </div>
      {description ? <FieldDescription>{description}</FieldDescription> : null}
      <ToggleGroup
        spacing={0}
        variant="outline"
        value={selected}
        onValueChange={(next) => {
          const picked = next[0]
          if (picked == null) return
          const match = options.find((o) => String(o.value) === picked)
          if (match) onChange(match.value)
        }}
        aria-label={unset ? `${label}, not rated yet` : label}
        className={cn(
          'grid w-full rounded-full p-1',
          unset ? 'bg-muted ring-1 ring-dashed ring-chart-1/70' : 'bg-border',
        )}
        style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
      >
        {options.map((option) => (
          <ToggleGroupItem
            key={String(option.value)}
            value={String(option.value)}
            className={cn(segmentItemClass, 'rounded-full border-0')}
          >
            {option.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      {unset ? (
        <FieldDescription className="text-[11px]">Not rated — tap a level</FieldDescription>
      ) : null}
    </Field>
  )
}
