import { createTheme, type CSSVariablesResolver } from '@mantine/core'

export const mantineTheme = createTheme({
  fontFamily: 'var(--font-sans, ui-sans-serif, system-ui, sans-serif)',
  defaultRadius: 'var(--radius)',
  primaryColor: 'primary',
  colors: {
    primary: [
      'var(--primary)',
      'var(--primary)',
      'var(--primary)',
      'var(--primary)',
      'var(--primary)',
      'var(--primary)',
      'var(--primary)',
      'var(--primary)',
      'var(--primary)',
      'var(--primary)',
    ],
  },
})

export const mantineCssVariablesResolver: CSSVariablesResolver = () => ({
  variables: {},
  light: {
    '--mantine-color-body': 'var(--background)',
    '--mantine-color-text': 'var(--foreground)',
    '--mantine-color-dimmed': 'var(--muted-foreground)',
    '--mantine-color-error': 'var(--destructive)',
    '--mantine-color-primary-filled': 'var(--primary)',
    '--mantine-color-primary-filled-hover': 'var(--primary)',
    '--mantine-primary-color-filled': 'var(--primary)',
    '--mantine-primary-color-filled-hover': 'var(--primary)',
    '--mantine-radius-default': 'var(--radius)',
    '--mantine-color-default-border': 'var(--border)',
    '--mantine-color-default-hover': 'var(--muted)',
    '--mantine-color-default': 'var(--background)',
  },
  dark: {
    '--mantine-color-body': 'var(--background)',
    '--mantine-color-text': 'var(--foreground)',
    '--mantine-color-dimmed': 'var(--muted-foreground)',
    '--mantine-color-error': 'var(--destructive)',
    '--mantine-color-primary-filled': 'var(--primary)',
    '--mantine-color-primary-filled-hover': 'var(--primary)',
    '--mantine-primary-color-filled': 'var(--primary)',
    '--mantine-primary-color-filled-hover': 'var(--primary)',
    '--mantine-radius-default': 'var(--radius)',
    '--mantine-color-default-border': 'var(--border)',
    '--mantine-color-default-hover': 'var(--muted)',
    '--mantine-color-default': 'var(--background)',
  },
})

export const fieldClassNames = {
  label: 'text-sm font-medium leading-none text-foreground',
  description: 'text-xs text-muted-foreground',
  error: 'text-xs text-destructive',
  input:
    'min-h-8 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:border-ring focus:ring-3 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30',
  wrapper: 'space-y-1.5',
} as const
