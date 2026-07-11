'use client'

import {
  Activity,
  Apple,
  Bed,
  Beer,
  Bike,
  BookOpen,
  Brain,
  Clock,
  Coffee,
  Cookie,
  Droplet,
  Droplets,
  Dumbbell,
  Flame,
  Footprints,
  Frown,
  Heart,
  HeartPulse,
  Meh,
  Moon,
  Music,
  Pill,
  Smile,
  Star,
  Sun,
  Thermometer,
  Tv,
  Utensils,
  Wine,
  Zap,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

// Canonical list of picker icons. Key = lowercase string stored in DB.
export const KNOWN_ICONS = [
  'wine',
  'coffee',
  'beer',
  'droplets',
  'droplet',
  'apple',
  'cookie',
  'utensils',
  'footprints',
  'dumbbell',
  'bike',
  'activity',
  'pill',
  'thermometer',
  'heart',
  'heartpulse',
  'smile',
  'frown',
  'meh',
  'brain',
  'moon',
  'sun',
  'clock',
  'bed',
  'star',
  'zap',
  'music',
  'tv',
  'bookopen',
  'flame',
] as const

export type KnownIconName = (typeof KNOWN_ICONS)[number]

export const ICON_COMPONENT_MAP: Record<string, LucideIcon> = {
  wine: Wine,
  coffee: Coffee,
  beer: Beer,
  droplets: Droplets,
  droplet: Droplet,
  apple: Apple,
  cookie: Cookie,
  utensils: Utensils,
  footprints: Footprints,
  dumbbell: Dumbbell,
  bike: Bike,
  activity: Activity,
  pill: Pill,
  thermometer: Thermometer,
  heart: Heart,
  heartpulse: HeartPulse,
  smile: Smile,
  frown: Frown,
  meh: Meh,
  brain: Brain,
  moon: Moon,
  sun: Sun,
  clock: Clock,
  bed: Bed,
  star: Star,
  zap: Zap,
  music: Music,
  tv: Tv,
  bookopen: BookOpen,
  flame: Flame,
}

interface IconPickerProps {
  value: string | null
  onChange: (iconName: string) => void
}

export function IconPicker({ value, onChange }: IconPickerProps) {
  const selected = value?.toLowerCase() ?? null

  return (
    <div className="grid grid-cols-6 gap-1.5">
      {KNOWN_ICONS.map((name) => {
        const Icon = ICON_COMPONENT_MAP[name]
        const isSelected = selected === name
        return (
          <button
            key={name}
            type="button"
            onClick={() => onChange(name)}
            aria-label={name}
            aria-pressed={isSelected}
            className={cn(
              'aspect-square rounded-md border flex items-center justify-center transition-colors',
              isSelected
                ? 'border-foreground bg-foreground/8 ring-2 ring-foreground/20'
                : 'border-border hover:bg-muted',
            )}
          >
            <Icon className="size-4" />
          </button>
        )
      })}
    </div>
  )
}
