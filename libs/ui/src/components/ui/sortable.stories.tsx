import type { Meta, StoryObj } from "@storybook/react"
import { useState } from "react"

import { Sortable, SortableItem } from "./sortable"

const meta = {
  title: "Primitives/Sortable",
  component: Sortable,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Sortable>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: function SortableDemo() {
    const [items, setItems] = useState(["Alpha", "Beta", "Gamma"])
    return (
      <Sortable
        value={items}
        onValueChange={setItems}
        getItemValue={(item) => item}
        className="flex w-56 flex-col gap-2"
      >
        {items.map((item) => (
          <SortableItem
            key={item}
            value={item}
            className="rounded-lg border bg-card px-3 py-2 text-sm"
          >
            {item}
          </SortableItem>
        ))}
      </Sortable>
    )
  },
}
