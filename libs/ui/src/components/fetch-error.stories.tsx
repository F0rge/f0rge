import type { Meta, StoryObj } from "@storybook/react"

import { FetchError } from "./fetch-error"

const meta = {
  title: "Primitives/FetchError",
  component: FetchError,
  parameters: { layout: "centered" },
} satisfies Meta<typeof FetchError>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { message: "Failed to load data." },
}

export const WithRetry: Story = {
  args: {
    message: "Network error.",
    onRetry: () => undefined,
  },
}
