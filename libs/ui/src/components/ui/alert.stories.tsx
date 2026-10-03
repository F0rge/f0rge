import type { Meta, StoryObj } from "@storybook/react"
import { InfoIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "./alert"

const meta = {
  title: "Primitives/Alert",
  component: Alert,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Alert>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Alert className="max-w-md">
      <InfoIcon />
      <AlertTitle>Heads up</AlertTitle>
      <AlertDescription>Semantic tokens drive alert variants.</AlertDescription>
    </Alert>
  ),
}
