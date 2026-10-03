'use client'

import {
  Field,
  FieldDescription,
  FieldTitle,
  ToggleGroup,
  ToggleGroupItem,
} from '@f0rge/ui'

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

const bristolItemClass =
  'min-h-[44px] w-full justify-center text-sm font-semibold data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:shadow-sm'

export function BristolInput({ value, onChange }: BristolInputProps) {
  const active = BRISTOL_TYPES.find((b) => b.value === value)

  return (
    <Field className="gap-2">
      <FieldTitle className="text-xs font-medium text-muted-foreground">
        Bristol stool type
      </FieldTitle>
      <ToggleGroup
        spacing={0}
        variant="outline"
        value={value != null ? [String(value)] : []}
        onValueChange={(next) => {
          const picked = next[0]
          if (picked == null) return
          onChange(Number(picked))
        }}
        aria-label="Bristol stool type"
        className="grid w-full grid-cols-4 gap-2 sm:grid-cols-7 sm:gap-1.5"
      >
        {BRISTOL_TYPES.map((b) => (
          <ToggleGroupItem
            key={b.value}
            value={String(b.value)}
            aria-label={`Bristol type ${b.value}: ${b.hint}`}
            className={bristolItemClass}
          >
            {b.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <FieldDescription className="text-xs">
        {active ? `Type ${active.value}: ${active.hint}` : '1 = hard pellets, 4 = ideal, 7 = liquid'}
      </FieldDescription>
    </Field>
  )
}
