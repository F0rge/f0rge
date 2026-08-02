export interface RecentMeal {
  dish_name: string
  source_photo_id: number
  times_logged: number
  last_logged: string // YYYY-MM-DD
  diet_flags: string[]
}

export interface PlatformMeal {
  id: number
  slug: string
  name: string
  cuisine: string
  icon_key: string
  ingredients: string[]
  diet_flags: string[]
}
