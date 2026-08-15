import type { Meta, StoryObj } from "@storybook/react"

import { Label } from "./label"

const meta = {
  title: "Primitives/Label",
  component: Label,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Label>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { children: "Label" },
}
