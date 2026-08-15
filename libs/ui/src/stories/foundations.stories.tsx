import type { Meta, StoryObj } from "@storybook/react"

const meta = {
  title: "Foundations",
  parameters: { layout: "padded" },
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

const semanticColors = [
  "background",
  "foreground",
  "primary",
  "primary-foreground",
  "secondary",
  "muted",
  "accent",
  "destructive",
  "border",
  "card",
  "popover",
] as const

export const Colours: Story = {
  render: () => (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {semanticColors.map((token) => (
        <div key={token} className="flex items-center gap-3 rounded-lg border border-border p-3">
          <div
            className="size-10 shrink-0 rounded-md border border-border"
            style={{ background: `var(--${token})` }}
          />
          <div>
            <p className="text-sm font-medium">--{token}</p>
            <p className="text-xs text-muted-foreground">var(--{token})</p>
          </div>
        </div>
      ))}
    </div>
  ),
}

export const Typography: Story = {
  render: () => (
    <div className="space-y-4">
      <p className="font-heading text-2xl font-semibold">Heading (font-heading)</p>
      <p className="text-base">Body text uses font-sans via semantic tokens.</p>
      <p className="text-sm text-muted-foreground">Muted supporting text.</p>
      <p className="font-mono text-sm">Mono sample — font-mono / --font-geist-mono</p>
    </div>
  ),
}

export const Radius: Story = {
  render: () => (
    <div className="flex flex-wrap gap-4">
      {(["sm", "md", "lg", "xl", "2xl"] as const).map((size) => (
        <div key={size} className="flex flex-col items-center gap-2">
          <div
            className="size-16 border border-border bg-muted"
            style={{ borderRadius: `var(--radius-${size})` }}
          />
          <span className="text-xs text-muted-foreground">--radius-{size}</span>
        </div>
      ))}
    </div>
  ),
}

export const Extras: Story = {
  render: () => (
    <div className="max-w-lg space-y-2 text-sm">
      <p className="font-medium">Documented overrides in extras.css</p>
      <ul className="list-inside list-disc text-muted-foreground">
        <li>ios-date-input — Safari date input appearance reset</li>
      </ul>
      <div className="pt-2">
        <label className="text-xs text-muted-foreground" htmlFor="foundations-date">
          Date input (extras.css)
        </label>
        <input
          id="foundations-date"
          type="date"
          className="mt-1 w-full rounded-lg border border-input bg-background px-2 py-1"
        />
      </div>
    </div>
  ),
}
