import type { Meta, StoryObj } from "@storybook/react"

import { Switch } from "./switch"

const meta = {
  title: "Primitives/Switch",
  component: Switch,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Switch>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <Switch defaultChecked aria-label="Notifications" />,
}
