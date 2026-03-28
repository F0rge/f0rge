'use client'

interface BinaryInputProps {
  label: string
  value: boolean
  onChange: (value: boolean) => void
  trueLabel: string
  falseLabel: string
}

export function BinaryInput({ label, value, onChange, trueLabel, falseLabel }: BinaryInputProps) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium leading-none">{label}</label>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onChange(true)}
          className={`min-h-[44px] flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
            value
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-border bg-background text-foreground hover:bg-muted'
          }`}
        >
          {trueLabel}
        </button>
        <button
          type="button"
          onClick={() => onChange(false)}
          className={`min-h-[44px] flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
            !value
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-border bg-background text-foreground hover:bg-muted'
          }`}
        >
          {falseLabel}
        </button>
      </div>
    </div>
  )
}
