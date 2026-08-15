import type { Meta, StoryObj } from '@storybook/react'

import { TextInput } from './text-input'

const meta: Meta<typeof TextInput> = {
  title: 'Forms/TextInput',
  component: TextInput,
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof TextInput>

export const Default: Story = {
  args: {
    label: 'Email',
    placeholder: 'you@example.com',
  },
}

export const WithError: Story = {
  args: {
    label: 'Email',
    placeholder: 'you@example.com',
    error: 'Enter a valid email',
    defaultValue: 'not-an-email',
  },
}

export const Required: Story = {
  args: {
    label: 'Name',
    placeholder: 'Your name',
    required: true,
  },
}
