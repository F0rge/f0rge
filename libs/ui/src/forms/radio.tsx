import {
  Radio as MantineRadio,
  RadioGroup as MantineRadioGroup,
  type RadioGroupProps,
  type RadioProps,
} from '@mantine/core'

function Radio(props: RadioProps) {
  return (
    <MantineRadio
      classNames={{
        label: 'text-sm text-foreground',
        error: 'text-xs text-destructive',
      }}
      {...props}
    />
  )
}

function RadioGroup(props: RadioGroupProps) {
  return (
    <MantineRadioGroup
      classNames={{
        label: 'text-sm font-medium leading-none text-foreground',
        description: 'text-xs text-muted-foreground',
        error: 'text-xs text-destructive',
      }}
      {...props}
    />
  )
}

Radio.Group = RadioGroup

export { Radio, RadioGroup }
