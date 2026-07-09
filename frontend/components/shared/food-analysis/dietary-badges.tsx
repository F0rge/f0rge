import type { PhotoIngredient } from '@/lib/api/types'

export interface DietaryBadge {
  label: string
  className: string
}

const HISTAMINE_COLORS: Record<number, string> = {
  0: 'bg-green-100 text-green-800',
  1: 'bg-yellow-100 text-yellow-800',
  2: 'bg-orange-100 text-orange-800',
  3: 'bg-red-100 text-red-800',
}

const FODMAP_HIGH = 'bg-orange-100 text-orange-800'
const FODMAP_MOD = 'bg-amber-100 text-amber-800'
const CONFIRMED_FREE = 'bg-green-100 text-green-800'

/** Per-meal "confirmed free" flags — suppress the corresponding risk badge and
 * swap in a green ✓ pill. Mirrors the backend scoring gate so the UI never
 * shows a red flag the user has already confirmed away. */
export interface DietaryConfirmOpts {
  glutenFreeConfirmed?: boolean
  lactoseFreeConfirmed?: boolean
}

/**
 * Single source of truth for per-ingredient dietary badges (histamine,
 * gluten, dairy, FODMAP). Shared by `DietaryBadges` (per-ingredient row) and
 * the food-card meal summary (aggregate pill). Do not duplicate this map —
 * see issue for meal-card-detail-sheet.
 */
export function buildIngredientBadges(
  ingredient: PhotoIngredient,
  opts?: DietaryConfirmOpts,
): DietaryBadge[] {
  const glutenFreeConfirmed = opts?.glutenFreeConfirmed ?? false
  const lactoseFreeConfirmed = opts?.lactoseFreeConfirmed ?? false
  const badges: DietaryBadge[] = []

  if (ingredient.histamine_score !== null) {
    badges.push({
      label: `H:${ingredient.histamine_score}`,
      className: HISTAMINE_COLORS[ingredient.histamine_score] ?? 'bg-gray-100 text-gray-600',
    })
  }

  // Gluten: confirmed-free swaps the red flag for a green ✓ on the offending
  // ingredient (per-meal toggle, so only ingredients that actually had gluten).
  if (ingredient.contains_gluten) {
    badges.push(
      glutenFreeConfirmed
        ? { label: 'GF ✓', className: CONFIRMED_FREE }
        : { label: 'Gluten', className: 'bg-red-100 text-red-800' },
    )
  }

  // Dairy is never suppressed — lactose-free confirmation only clears the
  // lactose (F:L) FODMAP flag below, not the dairy protein flag.
  if (ingredient.contains_dairy) {
    badges.push({ label: 'Dairy', className: 'bg-blue-100 text-blue-800' })
  }

  // FODMAP flags. For each category, `high` takes precedence over
  // `moderate`. High = orange badge; moderate = softer amber badge with a
  // `?` suffix so high vs moderate is also distinguishable in screenshots
  // and copied text. See issue #14.
  const fodmapCategories: Array<{ value: string | null; abbrev: string }> = [
    { value: ingredient.fodmap_oligos, abbrev: 'F:O' },
    { value: ingredient.fodmap_fructose, abbrev: 'F:Fr' },
    { value: ingredient.fodmap_polyols, abbrev: 'F:P' },
    { value: ingredient.fodmap_lactose, abbrev: 'F:L' },
  ]
  for (const { value, abbrev } of fodmapCategories) {
    if (value !== 'high' && value !== 'moderate') continue
    // Lactose-free confirmed: drop the F:L pill, swap in a green ✓.
    if (abbrev === 'F:L' && lactoseFreeConfirmed) {
      badges.push({ label: 'LF ✓', className: CONFIRMED_FREE })
    } else if (value === 'high') {
      badges.push({ label: abbrev, className: FODMAP_HIGH })
    } else {
      badges.push({ label: `${abbrev}?`, className: FODMAP_MOD })
    }
  }

  if (
    badges.length === 0 &&
    ingredient.histamine_score === null &&
    ingredient.contains_gluten === null &&
    ingredient.contains_dairy === null
  ) {
    badges.push({ label: '?', className: 'bg-gray-100 text-gray-500' })
  }

  return badges
}

export function DietaryBadges({
  ingredient,
  glutenFreeConfirmed = false,
  lactoseFreeConfirmed = false,
}: {
  ingredient: PhotoIngredient
  glutenFreeConfirmed?: boolean
  lactoseFreeConfirmed?: boolean
}) {
  const badges = buildIngredientBadges(ingredient, { glutenFreeConfirmed, lactoseFreeConfirmed })

  return (
    <span className="inline-flex flex-wrap gap-0.5">
      {badges.map((b, i) => (
        <span
          key={i}
          className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${b.className}`}
        >
          {b.label}
        </span>
      ))}
    </span>
  )
}

/**
 * Aggregate badges across every visible ingredient in a photo analysis, for
 * a one-line meal summary: the worst-case histamine badge (max score) plus
 * each distinct FODMAP/gluten/dairy flag present at least once. Reuses the
 * exact same colour map as the per-ingredient badges via `buildIngredientBadges`.
 */
export function buildAggregateBadges(
  ingredients: PhotoIngredient[],
  opts?: DietaryConfirmOpts,
): DietaryBadge[] {
  const visible = ingredients.filter((i) => i.visible)
  const perIngredient = visible.map((ing) => buildIngredientBadges(ing, opts))

  const result: DietaryBadge[] = []

  // Worst-case histamine badge: highest H:n across all ingredients.
  let worstHistamine: { score: number; badge: DietaryBadge } | null = null
  for (let i = 0; i < visible.length; i++) {
    const score = visible[i].histamine_score
    if (score === null) continue
    if (worstHistamine === null || score > worstHistamine.score) {
      const badge = perIngredient[i].find((b) => b.label === `H:${score}`)
      if (badge) worstHistamine = { score, badge }
    }
  }
  if (worstHistamine) result.push(worstHistamine.badge)

  // Every distinct non-histamine badge label present at least once (gluten,
  // dairy, FODMAP). Dedupe by label so "F:O" from two ingredients collapses
  // to one pill.
  const seen = new Set<string>()
  for (const badges of perIngredient) {
    for (const badge of badges) {
      if (badge.label.startsWith('H:') || badge.label === '?') continue
      if (seen.has(badge.label)) continue
      seen.add(badge.label)
      result.push(badge)
    }
  }

  return result
}
