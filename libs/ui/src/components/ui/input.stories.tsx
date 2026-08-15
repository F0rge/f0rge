import type { Meta, StoryObj } from "@storybook/react"

import { Input } from "./input"

const meta = {
  title: "Primitives/Input",
  component: Input,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Input>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { placeholder: "Email" },
}

export const Disabled: Story = {
  args: { placeholder: "Disabled", disabled: true },
}

export const Date: Story = {
  args: { type: "date" },
}
