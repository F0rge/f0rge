import type { Meta, StoryObj } from "@storybook/react"

import { Skeleton } from "./skeleton"

const meta = {
  title: "Primitives/Skeleton",
  component: Skeleton,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Skeleton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <Skeleton className="h-8 w-48" />,
}
