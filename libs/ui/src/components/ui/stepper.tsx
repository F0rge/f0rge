'use client'

import { Button } from './button'
import { cn } from '../../lib/utils'
import { Minus, Plus } from 'lucide-react'

interface StepperProps {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  label: string
  tooltip?: string
  size?: 'default' | 'compact'
}

export function Stepper({
  value,
  onChange,
  min = 0,
  max: maxProp,
  label,
  tooltip,
  size = 'default',
}: StepperProps) {
  const max = maxProp ?? (size === 'compact' ? 99 : 10)

  const decrement = () => {
    if (value > min) onChange(value - 1)
  }
  const increment = () => {
    if (value < max) onChange(value + 1)
  }

  if (size === 'compact') {
    return (
      <div className="flex items-center gap-2 shrink-0">
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={decrement}
          disabled={value <= min}
          aria-label={`Decrease ${label}`}
          className="size-8 rounded-md"
        >
          <Minus className="size-4" />
        </Button>
        <span
          className="text-sm font-semibold tabular-nums w-6 text-center"
          aria-label={`${label}: ${value}`}
        >
          {value}
        </span>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={increment}
          disabled={value >= max}
          aria-label={`Increase ${label}`}
          className="size-8 rounded-md"
        >
          <Plus className="size-4" />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-1.5">
      <span
        className="text-xs font-medium text-muted-foreground text-center leading-tight"
        title={tooltip}
      >
        {label}
      </span>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={decrement}
          disabled={value <= min}
          aria-label={`Decrease ${label}`}
          className="size-11 rounded-lg"
        >
          <Minus className="size-4" />
        </Button>
        <span
          className={cn(
            'w-8 text-center text-lg font-semibold tabular-nums',
            value === 0 && 'text-muted-foreground',
          )}
          aria-label={`${label}: ${value}`}
        >
          {value}
        </span>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={increment}
          disabled={value >= max}
          aria-label={`Increase ${label}`}
          className="size-11 rounded-lg"
        >
          <Plus className="size-4" />
        </Button>
      </div>
      {tooltip && (
        <span className="text-xs text-muted-foreground/70 text-center max-w-[120px] leading-tight">
          {tooltip}
        </span>
      )}
    </div>
  )
}
