import type { Meta, StoryObj } from "@storybook/react"
import { useState } from "react"

import { Stepper } from "./stepper"

const meta = {
  title: "Primitives/Stepper",
  component: Stepper,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Stepper>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: function StepperDemo() {
    const [value, setValue] = useState(3)
    return (
      <Stepper
        label="Severity"
        value={value}
        onChange={setValue}
        min={0}
        max={10}
        tooltip="0 = none, 10 = severe"
      />
    )
  },
}

export const Compact: Story = {
  render: function CompactStepperDemo() {
    const [value, setValue] = useState(2)
    return (
      <Stepper
        label="Steps"
        value={value}
        onChange={setValue}
        size="compact"
        min={0}
        max={99}
      />
    )
  },
}
