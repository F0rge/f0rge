import type { Meta, StoryObj } from "@storybook/react"
import { useState } from "react"

import { Button } from "./button"
import {
  Stepper,
  StepperContent,
  StepperDescription,
  StepperIndicator,
  StepperItem,
  StepperNav,
  StepperPanel,
  StepperSeparator,
  StepperTitle,
  StepperTrigger,
} from "./stepper"

const meta = {
  title: "Primitives/Stepper",
  component: Stepper,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Stepper>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: function StepperDemo() {
    const [step, setStep] = useState(1)
    return (
      <Stepper value={step} onValueChange={setStep} className="w-[min(100%,28rem)]">
        <StepperNav>
          <StepperItem step={1}>
            <StepperTrigger>
              <StepperIndicator />
              <div className="text-left">
                <StepperTitle>Account</StepperTitle>
                <StepperDescription>Sign in details</StepperDescription>
              </div>
            </StepperTrigger>
            <StepperSeparator />
          </StepperItem>
          <StepperItem step={2}>
            <StepperTrigger>
              <StepperIndicator />
              <div className="text-left">
                <StepperTitle>Profile</StepperTitle>
                <StepperDescription>Basic info</StepperDescription>
              </div>
            </StepperTrigger>
            <StepperSeparator />
          </StepperItem>
          <StepperItem step={3}>
            <StepperTrigger>
              <StepperIndicator />
              <div className="text-left">
                <StepperTitle>Done</StepperTitle>
                <StepperDescription>Review</StepperDescription>
              </div>
            </StepperTrigger>
          </StepperItem>
        </StepperNav>
        <StepperPanel className="mt-4">
          <StepperContent step={1}>Step 1 content</StepperContent>
          <StepperContent step={2}>Step 2 content</StepperContent>
          <StepperContent step={3}>Step 3 content</StepperContent>
        </StepperPanel>
        <div className="mt-4 flex gap-2">
          <Button
            variant="outline"
            disabled={step <= 1}
            onClick={() => setStep((s) => Math.max(1, s - 1))}
          >
            Back
          </Button>
          <Button
            disabled={step >= 3}
            onClick={() => setStep((s) => Math.min(3, s + 1))}
          >
            Next
          </Button>
        </div>
      </Stepper>
    )
  },
}
