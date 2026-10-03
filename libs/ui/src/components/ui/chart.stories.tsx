import type { Meta, StoryObj } from "@storybook/react"
import { Bar, BarChart, XAxis } from "recharts"

import { ChartContainer, ChartTooltip, ChartTooltipContent } from "./chart"

const meta = {
  title: "Primitives/Chart",
  component: ChartContainer,
  parameters: { layout: "centered" },
} satisfies Meta<typeof ChartContainer>

export default meta
type Story = StoryObj<typeof meta>

const data = [
  { label: "Mon", value: 4 },
  { label: "Tue", value: 7 },
  { label: "Wed", value: 3 },
]

export const Default: Story = {
  render: () => (
    <ChartContainer
      config={{ value: { label: "Value", color: "var(--primary)" } }}
      className="h-48 w-80"
    >
      <BarChart data={data}>
        <XAxis dataKey="label" tickLine={false} axisLine={false} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="value" fill="var(--color-value)" radius={4} />
      </BarChart>
    </ChartContainer>
  ),
}
