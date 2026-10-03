import type { Meta, StoryObj } from "@storybook/react"

import { Field, FieldDescription, FieldGroup, FieldLabel } from "./field"
import { Input } from "./input"

const meta = {
  title: "Primitives/Field",
  component: Field,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Field>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <FieldGroup className="w-80">
      <Field>
        <FieldLabel>Email</FieldLabel>
        <Input type="email" placeholder="you@example.com" />
        <FieldDescription>We never share your email.</FieldDescription>
      </Field>
    </FieldGroup>
  ),
}
