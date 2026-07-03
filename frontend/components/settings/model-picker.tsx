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
}

// Select-a-preset-or-type-a-custom-model-name control, shared verbatim by
// the AI Provider and Embedding Provider sections.
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
}: ModelPickerProps) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-muted-foreground">Model</label>
      {!useCustom && (
        <select
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
        >
          <option value="">— use current setting ({currentModel ?? 'default'}) —</option>
          {options.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      )}
      {useCustom && (
        <input
          type="text"
          placeholder={customPlaceholder}
          value={customModel}
          onChange={(e) => onCustomModelChange(e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
        />
      )}
      <label className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
        <input
          type="checkbox"
          checked={useCustom}
          onChange={(e) => onUseCustomChange(e.target.checked)}
          className="rounded"
        />
        Use custom model name
      </label>
    </div>
  )
}
