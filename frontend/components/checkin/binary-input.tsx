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
    <div className="space-y-3">
      <label className="text-sm font-semibold leading-none">{label}</label>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onChange(true)}
          className={`min-h-[48px] flex-1 rounded-xl border px-3 py-2.5 text-sm font-medium transition-all ${
            value
              ? 'border-primary bg-primary text-primary-foreground shadow-sm'
              : 'border-border bg-background text-foreground hover:bg-muted'
          }`}
        >
          {trueLabel}
        </button>
        <button
          type="button"
          onClick={() => onChange(false)}
          className={`min-h-[48px] flex-1 rounded-xl border px-3 py-2.5 text-sm font-medium transition-all ${
            !value
              ? 'border-primary bg-primary text-primary-foreground shadow-sm'
              : 'border-border bg-background text-foreground hover:bg-muted'
          }`}
        >
          {falseLabel}
        </button>
      </div>
    </div>
  )
}
