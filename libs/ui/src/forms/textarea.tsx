import { Textarea as MantineTextarea, type TextareaProps } from '@mantine/core'
import * as React from 'react'

import { fieldClassNames } from './theme'

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea(props, ref) {
    return <MantineTextarea ref={ref} classNames={fieldClassNames} minRows={3} autosize {...props} />
  },
)

export type { TextareaProps }
