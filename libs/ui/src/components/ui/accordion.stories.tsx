import type { Meta, StoryObj } from "@storybook/react"

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "./accordion"

const meta = {
  title: "Primitives/Accordion",
  component: Accordion,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Accordion>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Accordion className="w-[360px] rounded-lg border border-border">
      <AccordionItem value="item-1">
        <AccordionTrigger className="px-4">Account settings</AccordionTrigger>
        <AccordionContent className="px-4">
          Update your profile details and notification preferences.
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="item-2">
        <AccordionTrigger className="px-4">Privacy</AccordionTrigger>
        <AccordionContent className="px-4">
          Control who can see your activity and health data.
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  ),
}
