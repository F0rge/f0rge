import type { Meta, StoryObj } from "@storybook/react"

import { Button } from "./button"
import { Popover, PopoverContent, PopoverTrigger } from "./popover"

const meta = {
  title: "Primitives/Popover",
  component: Popover,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Popover>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Popover>
      <PopoverTrigger render={<Button variant="outline" />}>Open</PopoverTrigger>
      <PopoverContent className="w-56">Popover content</PopoverContent>
    </Popover>
  ),
}
