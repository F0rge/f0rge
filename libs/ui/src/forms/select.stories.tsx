import type { Meta, StoryObj } from '@storybook/react'

import { Select } from './select'

const meta: Meta<typeof Select> = {
  title: 'Forms/Select',
  component: Select,
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof Select>

export const Default: Story = {
  args: {
    label: 'Reason',
    placeholder: 'Select a reason',
    data: [
      { value: 'completed', label: 'Completed course' },
      { value: 'side_effects', label: 'Side effects' },
      { value: 'other', label: 'Other' },
    ],
  },
}
