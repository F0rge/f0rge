import type { Meta, StoryObj } from "@storybook/react"

import { Avatar, AvatarFallback, AvatarImage } from "./avatar"

const meta = {
  title: "Primitives/Avatar",
  component: Avatar,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Avatar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Avatar>
      <AvatarImage src="https://github.com/shadcn.png" alt="User" />
      <AvatarFallback>UI</AvatarFallback>
    </Avatar>
  ),
}
