import { Select as MantineSelect, type SelectProps } from '@mantine/core'

import { fieldClassNames } from './theme'

export function Select(props: SelectProps) {
  return <MantineSelect classNames={fieldClassNames} comboboxProps={{ withinPortal: true }} {...props} />
}

export type { SelectProps }
