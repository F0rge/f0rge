import type { Meta, StoryObj } from '@storybook/react'

import { NumberInput } from './number-input'

const meta: Meta<typeof NumberInput> = {
  title: 'Forms/NumberInput',
  component: NumberInput,
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof NumberInput>

export const Default: Story = {
  args: {
    label: 'Doses per day',
    placeholder: '1–12',
    min: 1,
    max: 12,
  },
}
