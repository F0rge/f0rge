import type { Meta, StoryObj } from "@storybook/react"

import {
  Autocomplete,
  AutocompleteContent,
  AutocompleteEmpty,
  AutocompleteInput,
  AutocompleteItem,
  AutocompleteList,
} from "./autocomplete"

const fruits = ["Apple", "Banana", "Cherry", "Date"]

const meta = {
  title: "Primitives/Autocomplete",
  component: Autocomplete,
  parameters: { layout: "centered" },
} satisfies Meta<typeof Autocomplete>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Autocomplete items={fruits} className="w-64">
      <AutocompleteInput placeholder="Pick a fruit" showTrigger />
      <AutocompleteContent>
        <AutocompleteList>
          {(item: string) => (
            <AutocompleteItem key={item} value={item}>
              {item}
            </AutocompleteItem>
          )}
        </AutocompleteList>
        <AutocompleteEmpty>No matches</AutocompleteEmpty>
      </AutocompleteContent>
    </Autocomplete>
  ),
}
