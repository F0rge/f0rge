'use client'

interface ScaleOption {
  value: number | string
  label: string
}

interface ScaleInputProps {
  label: string
  options: ScaleOption[]
  value: number | string
  onChange: (value: number | string) => void
  description?: string
}

export function ScaleInput({ label, options, value, onChange, description }: ScaleInputProps) {
  // Use grid for 5+ options to prevent cramming
  const useGrid = options.length >= 5
  const containerClass = useGrid
    ? 'grid grid-cols-3 gap-2'
    : 'flex gap-2'

  return (
    <div className="space-y-3">
      <label className="text-sm font-semibold leading-none">{label}</label>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <div className={containerClass}>
        {options.map((option) => {
          const isActive = value === option.value
          return (
            <button
              key={String(option.value)}
              type="button"
              onClick={() => onChange(option.value)}
              className={`min-h-[48px] rounded-xl border px-3 py-2.5 text-sm font-medium transition-all ${
                useGrid ? '' : 'flex-1'
              } ${
                isActive
                  ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                  : 'border-border bg-background text-foreground hover:bg-muted'
              }`}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
