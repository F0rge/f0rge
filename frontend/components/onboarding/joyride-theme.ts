import type { Styles } from 'react-joyride'

export const joyrideThemeOptions = {
  arrowColor: 'var(--background)',
  backgroundColor: 'var(--background)',
  overlayColor: 'rgba(0, 0, 0, 0.55)',
  primaryColor: 'var(--primary)',
  textColor: 'var(--foreground)',
  zIndex: 10000,
}

export const joyrideStyles: Partial<Styles> = {
  tooltip: {
    borderRadius: 12,
    padding: 16,
    fontSize: 14,
    lineHeight: 1.5,
  },
  tooltipTitle: {
    fontSize: 16,
    fontWeight: 600,
    marginBottom: 8,
  },
  buttonPrimary: {
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    padding: '8px 14px',
  },
  buttonBack: {
    borderRadius: 8,
    fontSize: 13,
    marginRight: 8,
  },
  buttonSkip: {
    fontSize: 13,
    color: 'var(--muted-foreground)',
  },
}
