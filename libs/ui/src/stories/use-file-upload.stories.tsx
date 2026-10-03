import type { Meta, StoryObj } from "@storybook/react"

import { Button } from "../components/ui/button"
import { useFileUpload } from "../hooks/use-file-upload"

const meta = {
  title: "Primitives/FileUpload",
  parameters: { layout: "centered" },
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: function FileUploadDemo() {
    const [{ files }, { openFileDialog, getInputProps }] = useFileUpload({
      accept: "image/*",
      multiple: false,
    })

    return (
      <div className="flex flex-col items-center gap-3">
        <Button type="button" onClick={openFileDialog}>Choose file</Button>
        <input {...getInputProps()} className="sr-only" />
        {files.length > 0 && (
          <p className="text-sm text-muted-foreground">
            {files[0]?.file instanceof File
              ? files[0].file.name
              : "Selected file"}
          </p>
        )}
      </div>
    )
  },
}
