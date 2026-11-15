import type { Preview } from "@storybook/react";
import { PrimerProvider } from "../src/index";
const preview: Preview = {
  decorators: [
    (Story) => (
      <PrimerProvider>
        <main style={{ padding: 24 }}>
          <Story />
        </main>
      </PrimerProvider>
    ),
  ],
};
export default preview;
