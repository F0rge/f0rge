'use client'

import type { ReactNode } from 'react'
import { MantineProvider } from '@mantine/core'
import '@mantine/core/styles.css'

import { mantineCssVariablesResolver, mantineTheme } from './forms/theme'

export interface UiProviderProps {
  children: ReactNode
  /** Colour scheme. Apps with next-themes should pass `resolvedTheme`. */
  colorScheme?: 'light' | 'dark'
}

export function UiProvider({ children, colorScheme = 'light' }: UiProviderProps) {
  return (
    <MantineProvider
      forceColorScheme={colorScheme}
      theme={mantineTheme}
      cssVariablesResolver={mantineCssVariablesResolver}
    >
      {children}
    </MantineProvider>
  )
}
