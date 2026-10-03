import type { Meta, StoryObj } from "@storybook/react"

import {
  Frame,
  FrameDescription,
  FrameHeader,
  FramePanel,
  FrameTitle,
} from "./frame"

const meta = {
  title: "Primitives/Frame",
  component: Frame,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Frame>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Frame className="w-96">
      <FramePanel>
        <FrameHeader>
          <FrameTitle>Panel</FrameTitle>
          <FrameDescription>Structured frame layout.</FrameDescription>
        </FrameHeader>
      </FramePanel>
    </Frame>
  ),
}
