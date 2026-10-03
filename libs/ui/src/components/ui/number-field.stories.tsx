import type { Meta, StoryObj } from "@storybook/react"

import {
  NumberField,
  NumberFieldDecrement,
  NumberFieldGroup,
  NumberFieldIncrement,
  NumberFieldInput,
} from "./number-field"

const meta = {
  title: "Primitives/NumberField",
  component: NumberField,
  parameters: { layout: "centered" },
} satisfies Meta<typeof NumberField>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <NumberField defaultValue={3} className="w-40">
      <NumberFieldGroup>
        <NumberFieldDecrement />
        <NumberFieldInput />
        <NumberFieldIncrement />
      </NumberFieldGroup>
    </NumberField>
  ),
}
