import type { Meta, StoryObj } from "@storybook/react"

import { Checkbox } from "./checkbox"

const meta = {
  title: "Primitives/Checkbox",
  component: Checkbox,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Checkbox>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <Checkbox defaultChecked aria-label="Accept terms" />,
}
