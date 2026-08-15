'use client'

import { useEffect } from 'react'
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
import { Button, cn } from '@f0rge/ui'
import { Checkbox, Select, TextInput, useForm } from '@f0rge/ui/forms'
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

function initialFodmap(ingredient?: DietaryIngredient | null) {
  return Object.fromEntries(
    FODMAP_AXES.map((a) => [a.field, (ingredient?.[a.field] as string | null) ?? NONE]),
  ) as Record<string, string>
}

function initialValues(ingredient?: DietaryIngredient | null) {
  const fodmap = initialFodmap(ingredient)
  return {
    name: ingredient?.canonical_name ?? '',
    category: ingredient?.category ?? NONE,
    histamine: ingredient?.histamine_score != null ? String(ingredient.histamine_score) : NONE,
    fodmap_oligos: fodmap.fodmap_oligos,
    fodmap_fructose: fodmap.fodmap_fructose,
    fodmap_polyols: fodmap.fodmap_polyols,
    fodmap_lactose: fodmap.fodmap_lactose,
    gluten: ingredient?.contains_gluten ?? false,
    dairy: ingredient?.contains_dairy ?? false,
    newAlias: '',
  }
}

interface IngredientFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  ingredient?: DietaryIngredient | null
}

export function IngredientFormDialog({ open, onOpenChange, ingredient }: IngredientFormDialogProps) {
  const isEdit = !!ingredient

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: initialValues(ingredient),
    validate: {
      name: (value) => {
        if (isEdit) return null
        return value.trim() ? null : 'Name is required'
      },
    },
  })

  useEffect(() => {
    if (!open) return
    form.setValues(initialValues(ingredient))
    // form object identity changes after setValues in Mantine 8
  }, [open, ingredient])

  const addIngredient = useAddDietaryIngredient()
  const updateIngredient = useUpdateDietaryIngredient()
  const addAlias = useAddIngredientAlias()
  const removeAlias = useRemoveIngredientAlias()

  const toNull = (v: string) => (v === NONE ? null : v)
  const fodmapValue = (field: string, values: ReturnType<typeof form.getValues>) =>
    toNull(values[field as keyof typeof values] as string) as FodmapLevel | null

  const handleSubmit = form.onSubmit(async (values) => {
    const fields = {
      category: toNull(values.category),
      histamine_score: values.histamine === NONE ? null : Number(values.histamine),
      fodmap_oligos: fodmapValue('fodmap_oligos', values),
      fodmap_fructose: fodmapValue('fodmap_fructose', values),
      fodmap_polyols: fodmapValue('fodmap_polyols', values),
      fodmap_lactose: fodmapValue('fodmap_lactose', values),
      contains_gluten: values.gluten,
      contains_dairy: values.dairy,
    }

    try {
      if (isEdit) {
        const data: IngredientUpdatePayload = fields
        await updateIngredient.mutateAsync({ id: ingredient.id, data })
        toast.success('Ingredient updated')
      } else {
        const data: IngredientCreatePayload = { canonical_name: values.name.trim(), ...fields }
        await addIngredient.mutateAsync(data)
        toast.success('Ingredient added')
      }
      onOpenChange(false)
    } catch (err) {
      handleMutationError(err, isEdit ? 'Failed to update ingredient' : 'Failed to add ingredient')
    }
  })

  async function handleAddAlias() {
    if (!ingredient) return
    const alias = form.getValues().newAlias.trim()
    if (!alias) return
    try {
      await addAlias.mutateAsync({ id: ingredient.id, alias })
      form.setFieldValue('newAlias', '')
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

        <form onSubmit={handleSubmit} className="space-y-4">
          <TextInput
            key={form.key('name')}
            label="Name"
            placeholder="e.g. cheddar cheese"
            disabled={isEdit}
            className={cn(isEdit && 'opacity-70')}
            {...form.getInputProps('name')}
          />

          <div className="grid grid-cols-2 gap-3">
            <Select
              key={form.key('category')}
              label="Category"
              data={CATEGORY_SELECT_OPTIONS}
              {...form.getInputProps('category')}
            />
            <Select
              key={form.key('histamine')}
              label="Histamine (0–3)"
              data={HISTAMINE_SELECT_OPTIONS}
              {...form.getInputProps('histamine')}
            />
          </div>

          <div className="space-y-1.5">
            <p className="text-sm font-medium leading-none">FODMAP levels</p>
            <div className="grid grid-cols-2 gap-3">
              {FODMAP_AXES.map((axis) => (
                <Select
                  key={form.key(axis.field)}
                  label={axis.short}
                  data={FODMAP_SELECT_OPTIONS}
                  {...form.getInputProps(axis.field)}
                />
              ))}
            </div>
          </div>

          <Checkbox
            label="Contains gluten"
            checked={form.getValues().gluten}
            onChange={(event) => form.setFieldValue('gluten', event.currentTarget.checked)}
          />
          <Checkbox
            label="Contains dairy"
            checked={form.getValues().dairy}
            onChange={(event) => form.setFieldValue('dairy', event.currentTarget.checked)}
          />

          {isEdit && (
            <div className="space-y-2 border-t border-muted pt-4">
              <p className="text-sm font-medium leading-none">Aliases</p>
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
                <TextInput
                  key={form.key('newAlias')}
                  placeholder="Add an alias..."
                  className="min-h-[44px] flex-1"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      handleAddAlias()
                    }
                  }}
                  {...form.getInputProps('newAlias')}
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleAddAlias}
                  disabled={!form.getValues().newAlias.trim() || addAlias.isPending}
                  className="min-h-[44px] shrink-0"
                >
                  Add
                </Button>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button type="submit" disabled={isPending} className="min-h-[44px]">
              {isPending ? 'Saving...' : isEdit ? 'Save' : 'Add ingredient'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
