import { TextInput as MantineTextInput, type TextInputProps } from '@mantine/core'

import { fieldClassNames } from './theme'

export function TextInput(props: TextInputProps) {
  return <MantineTextInput classNames={fieldClassNames} {...props} />
}

export type { TextInputProps }
