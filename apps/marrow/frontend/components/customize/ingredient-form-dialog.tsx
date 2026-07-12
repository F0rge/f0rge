'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@f0rge/ui'
import { Button } from '@f0rge/ui'
import { Input } from '@f0rge/ui'
import { Label } from '@f0rge/ui'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@f0rge/ui'
import {
  useAddDietaryIngredient,
  useUpdateDietaryIngredient,
  useAddIngredientAlias,
  useRemoveIngredientAlias,
} from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import type {
  DietaryIngredient,
  FodmapLevel,
  IngredientCreatePayload,
  IngredientUpdatePayload,
} from '@/lib/api/types'
import { cn } from '@f0rge/ui'
import { CATEGORY_OPTIONS, FODMAP_AXES, FODMAP_LEVEL_OPTIONS, HISTAMINE_OPTIONS } from '@/lib/ingredients'

const NONE = '__none__'

type Option = { value: string; label: string }

const CATEGORY_SELECT_OPTIONS: Option[] = [{ value: NONE, label: 'Uncategorized' }, ...CATEGORY_OPTIONS]
const HISTAMINE_SELECT_OPTIONS: Option[] = [
  { value: NONE, label: 'Not set' },
  ...HISTAMINE_OPTIONS.map((n) => ({ value: String(n), label: String(n) })),
]
const FODMAP_SELECT_OPTIONS: Option[] = [
  { value: NONE, label: 'Not set' },
  ...FODMAP_LEVEL_OPTIONS,
]

function FieldSelect({
  id,
  value,
  onChange,
  options,
}: {
  id: string
  value: string
  onChange: (v: string) => void
  options: Option[]
}) {
  const label = options.find((o) => o.value === value)?.label ?? ''
  return (
    <Select
      value={value}
      onValueChange={(v) => {
        if (v !== null) onChange(v)
      }}
    >
      <SelectTrigger id={id} className="min-h-[44px] w-full">
        <SelectValue>{label}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

interface IngredientFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  ingredient?: DietaryIngredient | null
}

export function IngredientFormDialog({ open, onOpenChange, ingredient }: IngredientFormDialogProps) {
  const isEdit = !!ingredient

  const [name, setName] = useState(ingredient?.canonical_name ?? '')
  const [category, setCategory] = useState(ingredient?.category ?? NONE)
  const [histamine, setHistamine] = useState(
    ingredient?.histamine_score != null ? String(ingredient.histamine_score) : NONE,
  )
  const [fodmap, setFodmap] = useState<Record<string, string>>(() =>
    Object.fromEntries(FODMAP_AXES.map((a) => [a.field, (ingredient?.[a.field] as string | null) ?? NONE])),
  )
  const [gluten, setGluten] = useState(ingredient?.contains_gluten ?? false)
  const [dairy, setDairy] = useState(ingredient?.contains_dairy ?? false)
  const [newAlias, setNewAlias] = useState('')

  const addIngredient = useAddDietaryIngredient()
  const updateIngredient = useUpdateDietaryIngredient()
  const addAlias = useAddIngredientAlias()
  const removeAlias = useRemoveIngredientAlias()

  const toNull = (v: string) => (v === NONE ? null : v)
  const fodmapValue = (field: string) => toNull(fodmap[field]) as FodmapLevel | null

  async function handleSubmit() {
    if (!isEdit && !name.trim()) {
      toast.error('Name is required')
      return
    }

    const fields = {
      category: toNull(category),
      histamine_score: histamine === NONE ? null : Number(histamine),
      fodmap_oligos: fodmapValue('fodmap_oligos'),
      fodmap_fructose: fodmapValue('fodmap_fructose'),
      fodmap_polyols: fodmapValue('fodmap_polyols'),
      fodmap_lactose: fodmapValue('fodmap_lactose'),
      contains_gluten: gluten,
      contains_dairy: dairy,
    }

    try {
      if (isEdit) {
        const data: IngredientUpdatePayload = fields
        await updateIngredient.mutateAsync({ id: ingredient.id, data })
        toast.success('Ingredient updated')
      } else {
        const data: IngredientCreatePayload = { canonical_name: name.trim(), ...fields }
        await addIngredient.mutateAsync(data)
        toast.success('Ingredient added')
      }
      onOpenChange(false)
    } catch (err) {
      handleMutationError(err, isEdit ? 'Failed to update ingredient' : 'Failed to add ingredient')
    }
  }

  async function handleAddAlias() {
    if (!ingredient) return
    const alias = newAlias.trim()
    if (!alias) return
    try {
      await addAlias.mutateAsync({ id: ingredient.id, alias })
      setNewAlias('')
    } catch (err) {
      handleMutationError(err, 'Failed to add alias')
    }
  }

  async function handleRemoveAlias(aliasId: number) {
    try {
      await removeAlias.mutateAsync(aliasId)
    } catch (err) {
      handleMutationError(err, 'Failed to remove alias')
    }
  }

  const isPending = addIngredient.isPending || updateIngredient.isPending
  const aliases = ingredient?.aliases ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit ingredient' : 'Add ingredient'}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? 'Update dietary classifications and aliases. The name cannot be changed.'
              : 'Add an ingredient with its FODMAP, histamine, gluten and dairy classifications.'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="ing-name">Name</Label>
            <Input
              id="ing-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. cheddar cheese"
              disabled={isEdit}
              className={cn(isEdit && 'opacity-70')}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ing-category">Category</Label>
              <FieldSelect
                id="ing-category"
                value={category}
                onChange={setCategory}
                options={CATEGORY_SELECT_OPTIONS}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ing-histamine">Histamine (0–3)</Label>
              <FieldSelect
                id="ing-histamine"
                value={histamine}
                onChange={setHistamine}
                options={HISTAMINE_SELECT_OPTIONS}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>FODMAP levels</Label>
            <div className="grid grid-cols-2 gap-3">
              {FODMAP_AXES.map((axis) => (
                <div key={axis.field} className="space-y-1">
                  <Label htmlFor={`ing-${axis.field}`} className="text-xs text-muted-foreground">
                    {axis.short}
                  </Label>
                  <FieldSelect
                    id={`ing-${axis.field}`}
                    value={fodmap[axis.field]}
                    onChange={(v) => setFodmap((prev) => ({ ...prev, [axis.field]: v }))}
                    options={FODMAP_SELECT_OPTIONS}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label className="flex min-h-[44px] items-center gap-2">
              <input
                type="checkbox"
                checked={gluten}
                onChange={(e) => setGluten(e.target.checked)}
                className="size-4 rounded border-border"
              />
              <span className="text-sm">Contains gluten</span>
            </label>
            <label className="flex min-h-[44px] items-center gap-2">
              <input
                type="checkbox"
                checked={dairy}
                onChange={(e) => setDairy(e.target.checked)}
                className="size-4 rounded border-border"
              />
              <span className="text-sm">Contains dairy</span>
            </label>
          </div>

          {isEdit && (
            <div className="space-y-2 border-t border-muted pt-4">
              <Label>Aliases</Label>
              <p className="text-xs text-muted-foreground">
                Alternate names that map to this ingredient when scoring meals.
              </p>
              {aliases.length > 0 ? (
                <ul className="flex flex-col gap-1.5">
                  {aliases.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center justify-between gap-2 rounded-md border border-muted px-3 py-1.5 text-sm"
                    >
                      <span className="truncate">{a.alias}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveAlias(a.id)}
                        disabled={removeAlias.isPending}
                        aria-label={`Remove alias ${a.alias}`}
                        className="flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
                      >
                        <X className="size-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground">No aliases yet.</p>
              )}
              <div className="flex items-center gap-2">
                <Input
                  value={newAlias}
                  onChange={(e) => setNewAlias(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      handleAddAlias()
                    }
                  }}
                  placeholder="Add an alias..."
                  className="min-h-[44px]"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleAddAlias}
                  disabled={!newAlias.trim() || addAlias.isPending}
                  className="min-h-[44px] shrink-0"
                >
                  Add
                </Button>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button onClick={handleSubmit} disabled={isPending} className="min-h-[44px]">
            {isPending ? 'Saving...' : isEdit ? 'Save' : 'Add ingredient'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
