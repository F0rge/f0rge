'use client'

const BRISTOL_TYPES: { value: number; label: string; hint: string }[] = [
  { value: 1, label: '1', hint: 'Separate hard lumps' },
  { value: 2, label: '2', hint: 'Lumpy sausage' },
  { value: 3, label: '3', hint: 'Sausage with cracks' },
  { value: 4, label: '4', hint: 'Smooth sausage (ideal)' },
  { value: 5, label: '5', hint: 'Soft blobs' },
  { value: 6, label: '6', hint: 'Mushy / fluffy' },
  { value: 7, label: '7', hint: 'Liquid' },
]

interface BristolInputProps {
  value: number | null
  onChange: (value: number) => void
}

export function BristolInput({ value, onChange }: BristolInputProps) {
  const active = BRISTOL_TYPES.find((b) => b.value === value)

  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-muted-foreground">
        Bristol stool type
      </label>
      <div className="grid grid-cols-7 gap-1.5">
        {BRISTOL_TYPES.map((b) => {
          const isActive = value === b.value
          return (
            <button
              key={b.value}
              type="button"
              onClick={() => onChange(b.value)}
              className={`min-h-[44px] rounded-lg border text-sm font-semibold transition-all ${
                isActive
                  ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                  : 'border-border bg-background text-foreground hover:bg-muted'
              }`}
              aria-label={`Bristol type ${b.value}: ${b.hint}`}
            >
              {b.label}
            </button>
          )
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        {active ? `Type ${active.value}: ${active.hint}` : '1 = hard pellets, 4 = ideal, 7 = liquid'}
      </p>
    </div>
  )
}
