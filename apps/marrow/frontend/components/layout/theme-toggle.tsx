'use client'

import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useSyncExternalStore } from 'react'
import { cn } from '@f0rge/ui'

const THEME_OPTIONS = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'System', Icon: Monitor },
] as const

type ThemeValue = (typeof THEME_OPTIONS)[number]['value']

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  )

  if (!mounted) {
    return (
      <div
        role="menuitem"
        aria-label="Appearance"
        className="px-3 py-2"
      >
        <div className="h-8 rounded-lg bg-muted/50" />
      </div>
    )
  }

  const activeTheme = (theme ?? 'system') as ThemeValue

  return (
    <div role="menuitem" aria-label="Appearance" className="px-3 py-2">
      <div
        role="group"
        aria-label="Theme"
        className="flex rounded-lg border border-border bg-muted/40 p-0.5"
      >
        {THEME_OPTIONS.map(({ value, label, Icon }) => {
          const isActive = activeTheme === value
          return (
            <button
              key={value}
              type="button"
              role="menuitemradio"
              aria-checked={isActive}
              aria-label={label}
              title={label}
              onClick={() => setTheme(value)}
              className={cn(
                'flex flex-1 items-center justify-center rounded-md px-1.5 py-1.5 transition-colors',
                isActive
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Icon className="size-3.5" />
              <span className="sr-only">{label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
