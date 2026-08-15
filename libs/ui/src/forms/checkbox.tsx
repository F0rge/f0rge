import { Checkbox as MantineCheckbox, type CheckboxProps } from '@mantine/core'

export function Checkbox(props: CheckboxProps) {
  return (
    <MantineCheckbox
      classNames={{
        label: 'text-sm text-foreground',
        error: 'text-xs text-destructive',
      }}
      {...props}
    />
  )
}

export type { CheckboxProps }
