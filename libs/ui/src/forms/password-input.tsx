import { PasswordInput as MantinePasswordInput, type PasswordInputProps } from '@mantine/core'

import { fieldClassNames } from './theme'

export function PasswordInput(props: PasswordInputProps) {
  return <MantinePasswordInput classNames={fieldClassNames} {...props} />
}

export type { PasswordInputProps }
