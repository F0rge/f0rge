'use client';

import { UiProvider } from '@f0rge/ui';
import { useTheme } from 'next-themes';
import { ThemeProvider } from '@/components/theme-provider';

function ThemedUiProvider({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme();
  return (
    <UiProvider colorScheme={resolvedTheme === 'dark' ? 'dark' : 'light'}>
      {children}
    </UiProvider>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <ThemedUiProvider>{children}</ThemedUiProvider>
    </ThemeProvider>
  );
}
