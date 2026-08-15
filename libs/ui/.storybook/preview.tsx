import type { Preview } from "@storybook/react"
import React, { useEffect } from "react"

import "../src/styles/storybook.css"
import defaultSkin from "../src/styles/skins/default.css?raw"
import marrowSkin from "../src/styles/skins/marrow.css?raw"

const SKINS: Record<string, string> = {
  default: defaultSkin,
  marrow: marrowSkin,
}

function SkinDecorator({
  Story,
  globals,
}: {
  Story: React.ComponentType
  globals: Record<string, string>
}) {
  useEffect(() => {
    const id = "storybook-skin"
    let el = document.getElementById(id) as HTMLStyleElement | null
    if (!el) {
      el = document.createElement("style")
      el.id = id
      document.head.appendChild(el)
    }
    el.textContent = SKINS[globals.theme] ?? SKINS.default
  }, [globals.theme])

  useEffect(() => {
    document.documentElement.classList.toggle("dark", globals.darkMode === "dark")
  }, [globals.darkMode])

  return (
    <div className="bg-background p-4 font-sans text-foreground">
      <Story />
    </div>
  )
}

const preview: Preview = {
  globalTypes: {
    theme: {
      description: "Colour skin",
      toolbar: {
        title: "Theme",
        icon: "paintbrush",
        items: [
          { value: "default", title: "Default" },
          { value: "marrow", title: "Marrow" },
        ],
        dynamicTitle: true,
      },
    },
    darkMode: {
      description: "Dark mode",
      toolbar: {
        title: "Mode",
        icon: "moon",
        items: [
          { value: "light", title: "Light" },
          { value: "dark", title: "Dark" },
        ],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: {
    theme: "default",
    darkMode: "light",
  },
  decorators: [
    (Story, context) => (
      <SkinDecorator Story={Story} globals={context.globals as Record<string, string>} />
    ),
  ],
}

export default preview
