'use client'

import { Field, FieldTitle, ToggleGroup, ToggleGroupItem } from '@f0rge/ui'

interface BinaryInputProps {
  label: string
  value: boolean
  onChange: (value: boolean) => void
  trueLabel: string
  falseLabel: string
}

const binaryItemClass =
  'min-h-[48px] flex-1 justify-center rounded-xl text-sm font-medium data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:shadow-sm'

export function BinaryInput({ label, value, onChange, trueLabel, falseLabel }: BinaryInputProps) {
  return (
    <Field className="gap-3">
      <FieldTitle className="text-sm font-semibold">{label}</FieldTitle>
      <ToggleGroup
        spacing={2}
        variant="outline"
        value={[value ? 'true' : 'false']}
        onValueChange={(next) => {
          const picked = next[0]
          if (picked === 'true') onChange(true)
          if (picked === 'false') onChange(false)
        }}
        aria-label={label}
        className="flex w-full gap-2"
      >
        <ToggleGroupItem value="true" className={binaryItemClass}>
          {trueLabel}
        </ToggleGroupItem>
        <ToggleGroupItem value="false" className={binaryItemClass}>
          {falseLabel}
        </ToggleGroupItem>
      </ToggleGroup>
    </Field>
  )
}
