import type { Meta, StoryObj } from "@storybook/react"
import { InboxIcon } from "lucide-react"

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "./empty"

const meta = {
  title: "Primitives/Empty",
  component: Empty,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Empty>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Empty className="w-80 border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <InboxIcon />
        </EmptyMedia>
        <EmptyTitle>No items</EmptyTitle>
        <EmptyDescription>Add your first entry to get started.</EmptyDescription>
      </EmptyHeader>
    </Empty>
  ),
}
