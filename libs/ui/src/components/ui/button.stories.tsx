import type { Meta, StoryObj } from "@storybook/react"

import { Button } from "./button"

const meta = {
  title: "Primitives/Button",
  component: Button,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Button>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { children: "Button" },
}

const variants = [
  "default",
  "outline",
  "secondary",
  "ghost",
  "destructive",
  "link",
] as const

const sizes = [
  "default",
  "xs",
  "sm",
  "lg",
  "icon",
  "icon-xs",
  "icon-sm",
  "icon-lg",
] as const

export const Variants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      {variants.map((variant) => (
        <Button key={variant} variant={variant}>
          {variant}
        </Button>
      ))}
    </div>
  ),
}

export const Sizes: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-2">
      {sizes.map((size) => (
        <Button key={size} size={size}>
          {size.startsWith("icon") ? "+" : size}
        </Button>
      ))}
    </div>
  ),
}
