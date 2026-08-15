import type { Meta, StoryObj } from '@storybook/react'

import { PasswordInput } from './password-input'

const meta: Meta<typeof PasswordInput> = {
  title: 'Forms/PasswordInput',
  component: PasswordInput,
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof PasswordInput>

export const Default: Story = {
  args: {
    label: 'Password',
    placeholder: '••••••••',
  },
}
