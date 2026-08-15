import { Checkbox, Select, TextInput } from '@f0rge/ui/forms'

interface ModelOption {
  value: string
  label: string
}

interface ModelPickerProps {
  options: readonly ModelOption[]
  currentModel: string | null | undefined
  model: string
  onModelChange: (value: string) => void
  customModel: string
  onCustomModelChange: (value: string) => void
  useCustom: boolean
  onUseCustomChange: (value: boolean) => void
  customPlaceholder: string
  label?: string
}

export function ModelPicker({
  options,
  currentModel,
  model,
  onModelChange,
  customModel,
  onCustomModelChange,
  useCustom,
  onUseCustomChange,
  customPlaceholder,
  label = 'Model',
}: ModelPickerProps) {
  const selectData = [
    { value: '', label: `— use current setting (${currentModel ?? 'default'}) —` },
    ...options.map((m) => ({ value: m.value, label: m.label })),
  ]

  return (
    <div className="space-y-1">
      {!useCustom ? (
        <Select
          label={label}
          data={selectData}
          value={model}
          onChange={(value) => onModelChange(value ?? '')}
        />
      ) : (
        <TextInput
          label={label}
          placeholder={customPlaceholder}
          value={customModel}
          onChange={(event) => onCustomModelChange(event.currentTarget.value)}
        />
      )}
      <Checkbox
        label="Use custom model name"
        checked={useCustom}
        onChange={(event) => onUseCustomChange(event.currentTarget.checked)}
        className="mt-1"
      />
    </div>
  )
}
