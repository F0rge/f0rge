import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { NiaThinking } from "./nia-thinking";

describe("NiaThinking", () => {
  it("shows only one Working indicator while waiting", () => {
    const html = renderToStaticMarkup(
      createElement(NiaThinking, {
        streaming: true,
        streamingText: "",
        thinkingText: "hmm",
        toolNames: ["create_sku"],
      }),
    );
    const matches = html.match(/Working \d+s/g) ?? [];
    expect(matches).toHaveLength(1);
    expect(html).not.toContain("Show reasoning");
  });

  it("uses Show reasoning after the answer starts", () => {
    const html = renderToStaticMarkup(
      createElement(NiaThinking, {
        streaming: true,
        streamingText: "Hello",
        thinkingText: "hmm",
        toolNames: [],
      }),
    );
    expect(html).toContain("Show reasoning");
    expect(html).not.toMatch(/Working \d+s/);
  });
});
