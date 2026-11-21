import { describe, expect, it } from "vitest";

import { moveSection, templateProblem, type DocumentTemplate } from "./document-template";

const words = { title: "Title", number_label: "No.", terms: "" };
const template: DocumentTemplate = {
  logo_position: "right",
  logo_height: 72,
  accent_colour: "#161616",
  font: "sans",
  density: "comfortable",
  table_header: "band",
  sections: [
    { key: "parties", visible: true },
    { key: "lines", visible: true },
    { key: "totals", visible: false },
  ],
  columns: { sku_ref: true, discount: true, line_vat: true },
  wording: { invoice: words, quote: words, credit_note: words, receipt: words },
  footer: "",
  show_trading_name: false,
  paid_stamp: true,
};

describe("document template", () => {
  it("accepts a complete template", () => {
    expect(templateProblem(template)).toBeNull();
  });

  it("rejects a bad colour and blank wording", () => {
    expect(templateProblem({ ...template, accent_colour: "blue" })).toMatch(/colour/);
    expect(
      templateProblem({ ...template, wording: { ...template.wording, receipt: { ...words, title: " " } } }),
    ).toBe("Payment receipt needs a title and a number label.");
  });

  it("moves sections within bounds", () => {
    expect(moveSection(template, 0, 1).sections.map((s) => s.key)).toEqual(["lines", "parties", "totals"]);
    expect(moveSection(template, 0, -1)).toBe(template);
    expect(moveSection(template, 2, 1)).toBe(template);
  });
});
