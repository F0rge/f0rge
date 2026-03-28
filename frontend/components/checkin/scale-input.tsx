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
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium leading-none">{label}</label>
      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const isActive = value === option.value
          return (
            <button
              key={String(option.value)}
              type="button"
              onClick={() => onChange(option.value)}
              className={`min-h-[44px] min-w-[44px] flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'border-primary bg-primary text-primary-foreground'
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
