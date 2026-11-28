import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ErrorNotice, openDialogContent } from "./error-notice";

describe("error notice", () => {
  it("targets the content of the top open Carbon dialog", () => {
    const first = { id: "first" } as unknown as Element;
    const top = { id: "top" } as unknown as Element;
    const root = (found: Element[]) => ({
      querySelectorAll: (selector: string) => {
        expect(selector).toBe(".cds--modal.is-visible .cds--modal-content");
        return found as unknown as NodeListOf<Element>;
      },
    });
    expect(openDialogContent(root([first, top]))).toBe(top);
    expect(openDialogContent(root([]))).toBeNull();
  });

  it("announces the error as an alert and renders nothing without one", () => {
    const html = renderToStaticMarkup(createElement(ErrorNotice, { error: "Payment exceeds the balance.", onClose: () => {} }));
    expect(html).toContain('role="alert"');
    expect(html).toContain("Payment exceeds the balance.");
    expect(renderToStaticMarkup(createElement(ErrorNotice, { error: null }))).toBe("");
  });
});
