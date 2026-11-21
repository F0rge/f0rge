import type { Meta, StoryObj } from "@storybook/react"

import { Button } from "./button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "./sheet"

const meta = {
  title: "Primitives/Sheet",
  component: Sheet,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Sheet>

export default meta
type Story = StoryObj<typeof meta>

const sides = ["left", "right", "top", "bottom"] as const

export const Sides: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      {sides.map((side) => (
        <Sheet key={side}>
          <SheetTrigger render={<Button variant="outline" />}>Open {side}</SheetTrigger>
          <SheetContent side={side}>
            <SheetHeader>
              <SheetTitle>Sheet title</SheetTitle>
              <SheetDescription>
                A Dialog anchored to the {side} edge, for menus and drawers.
              </SheetDescription>
            </SheetHeader>
            <nav className="grid gap-1 px-4">
              {["First link", "Second link", "Third link"].map((label) => (
                <a key={label} href="#" className="rounded-md px-3 py-2 text-sm font-medium hover:bg-muted">
                  {label}
                </a>
              ))}
            </nav>
            <SheetFooter>
              <Button>Done</Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      ))}
    </div>
  ),
}
