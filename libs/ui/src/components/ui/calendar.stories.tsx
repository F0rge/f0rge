import type { Meta, StoryObj } from "@storybook/react"

import { Calendar } from "./calendar"

const meta = {
  title: "Primitives/Calendar",
  component: Calendar,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Calendar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <Calendar mode="single" className="rounded-lg border" />,
}
