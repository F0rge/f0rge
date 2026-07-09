import type { DietaryIngredient, FodmapLevel } from '@/lib/api/types'

/** The 16 backend categories (app/schemas/dietary_ingredient.py) with display labels. */
export const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: 'beverages', label: 'Beverages' },
  { value: 'condiments', label: 'Condiments' },
  { value: 'dairy', label: 'Dairy' },
  { value: 'eggs', label: 'Eggs' },
  { value: 'fermented', label: 'Fermented' },
  { value: 'fish', label: 'Fish' },
  { value: 'fruit', label: 'Fruit' },
  { value: 'grains', label: 'Grains' },
  { value: 'legumes', label: 'Legumes' },
  { value: 'meat', label: 'Meat' },
  { value: 'nuts_seeds', label: 'Nuts & seeds' },
  { value: 'oils_fats', label: 'Oils & fats' },
  { value: 'seafood', label: 'Seafood' },
  { value: 'spices', label: 'Spices' },
  { value: 'sweets', label: 'Sweets' },
  { value: 'vegetables', label: 'Vegetables' },
]

export function categoryLabel(value: string | null): string {
  if (!value) return 'Uncategorized'
  return CATEGORY_OPTIONS.find((c) => c.value === value)?.label ?? value
}

export const FODMAP_LEVEL_OPTIONS: { value: FodmapLevel; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'high', label: 'High' },
]

export const HISTAMINE_OPTIONS = [0, 1, 2, 3] as const

/** The four FODMAP axes: form field key + short label for the row summary. */
export const FODMAP_AXES: { field: keyof DietaryIngredient; short: string; label: string }[] = [
  { field: 'fodmap_oligos', short: 'Oligos', label: 'Oligos (GOS/fructans)' },
  { field: 'fodmap_fructose', short: 'Fructose', label: 'Excess fructose' },
  { field: 'fodmap_polyols', short: 'Polyols', label: 'Polyols' },
  { field: 'fodmap_lactose', short: 'Lactose', label: 'Lactose' },
]

/** FODMAP axes at "high" level — for the compact row summary badge. */
export function highFodmapAxes(ing: DietaryIngredient): string[] {
  return FODMAP_AXES.filter((a) => ing[a.field] === 'high').map((a) => a.short)
}
