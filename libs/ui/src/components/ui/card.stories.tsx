import type { Meta, StoryObj } from "@storybook/react"

import { Button } from "./button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "./card"

const meta = {
  title: "Primitives/Card",
  component: Card,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Card>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Card className="w-[320px]">
      <CardHeader>
        <CardTitle>Card title</CardTitle>
        <CardDescription>Supporting description for the card.</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm">Card content uses semantic surface tokens.</p>
      </CardContent>
      <CardFooter>
        <Button size="sm">Action</Button>
      </CardFooter>
    </Card>
  ),
}
