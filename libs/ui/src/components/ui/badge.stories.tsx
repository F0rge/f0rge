import type { Meta, StoryObj } from "@storybook/react"

import { Badge } from "./badge"

const meta = {
  title: "Primitives/Badge",
  component: Badge,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Badge>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { children: "Badge" },
}

export const Variants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      {(["default", "secondary", "destructive", "outline", "ghost", "link"] as const).map(
        (variant) => (
          <Badge key={variant} variant={variant}>{variant}</Badge>
        ),
      )}
    </div>
  ),
}
