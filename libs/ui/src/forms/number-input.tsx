import { NumberInput as MantineNumberInput, type NumberInputProps } from '@mantine/core'

import { fieldClassNames } from './theme'

export function NumberInput(props: NumberInputProps) {
  return <MantineNumberInput classNames={fieldClassNames} {...props} />
}

export type { NumberInputProps }
