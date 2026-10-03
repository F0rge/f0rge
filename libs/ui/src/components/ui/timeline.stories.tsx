import type { Meta, StoryObj } from "@storybook/react"

import {
  Timeline,
  TimelineContent,
  TimelineIndicator,
  TimelineItem,
  TimelineTitle,
} from "./timeline"

const meta = {
  title: "Primitives/Timeline",
  component: Timeline,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Timeline>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Timeline className="w-80">
      <TimelineItem step={1}>
        <TimelineIndicator />
        <TimelineContent>
          <TimelineTitle>Started</TimelineTitle>
        </TimelineContent>
      </TimelineItem>
      <TimelineItem step={2}>
        <TimelineIndicator />
        <TimelineContent>
          <TimelineTitle>In progress</TimelineTitle>
        </TimelineContent>
      </TimelineItem>
    </Timeline>
  ),
}
