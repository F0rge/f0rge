import { describe, expect, it } from "vitest";

import type { NiaMessage } from "./api";
import {
  latestNeedsOkToolCallId,
  messageHasStructuredCard,
  messageNeedsOkIsActionable,
  messageShowsDockProse,
} from "./nia-thread-utils";

const CHASE =
  "Yes — chase INV-0004 for Naledi Mokoena, R2070, 40 days overdue on 30-day terms.";

function message(partial: Partial<NiaMessage> & Pick<NiaMessage, "role" | "content">): NiaMessage {
  return {
    id: "m1",
    created_at: "2026-09-03T10:00:00Z",
    structured_payload: null,
    ...partial,
  };
}

describe("messageShowsDockProse", () => {
  it("shows assistant prose with an opened_page card and a recommendation", () => {
    expect(
      messageShowsDockProse(
        message({
          role: "assistant",
          content: CHASE,
          structured_payload: { kind: "opened_page", path: "/invoices/inv-0004" },
        }),
      ),
    ).toBe(true);
  });

  it("shows assistant prose with an overdue_invoices card and a recommendation", () => {
    expect(
      messageShowsDockProse(
        message({
          role: "assistant",
          content: CHASE,
          structured_payload: {
            kind: "overdue_invoices",
            invoices: [{ id: "inv-0004", invoice_number: "INV-0004", remaining_zar: "2070.00" }],
          },
        }),
      ),
    ).toBe(true);
  });

  it("hides prose when the assistant card has empty content", () => {
    expect(
      messageShowsDockProse(
        message({
          role: "assistant",
          content: "",
          structured_payload: { kind: "opened_page", path: "/invoices" },
        }),
      ),
    ).toBe(false);
  });

  it("shows user message text", () => {
    expect(
      messageShowsDockProse(
        message({
          role: "user",
          content: "should I chase overdue invoices?",
        }),
      ),
    ).toBe(true);
  });
});


describe("messageHasStructuredCard", () => {
  it("suppresses opened_page after the same turn navigates", () => {
    expect(
      messageHasStructuredCard(
        message({
          role: "assistant",
          content: "Opened invoices.",
          structured_payload: { kind: "opened_page", path: "/invoices" },
        }),
      ),
    ).toBe(false);
  });

  it("keeps non-navigation structured cards", () => {
    expect(
      messageHasStructuredCard(
        message({
          role: "assistant",
          content: "INV-0004 is overdue.",
          structured_payload: {
            kind: "overdue_invoices",
            invoices: [{ id: "inv-0004", invoice_number: "INV-0004", remaining_zar: "2070.00" }],
          },
        }),
      ),
    ).toBe(true);
  });
});

describe("needs_ok actionability", () => {
  it("marks only the latest needs_ok message as actionable", () => {
    const older = message({
      id: "older",
      role: "assistant",
      content: "Nia needs your approval",
      structured_payload: {
        kind: "needs_ok",
        title: "Update SKU",
        body: "Update SKU: sku_id=1",
        tool_call_id: "old-call",
      },
    });
    const latest = message({
      id: "latest",
      created_at: "2026-09-03T10:01:00Z",
      role: "assistant",
      content: "Nia needs your approval",
      structured_payload: {
        kind: "needs_ok",
        title: "Update SKU",
        body: "Update SKU: sku_id=1, retail_inc_vat=1500.00",
        tool_call_id: "new-call",
      },
    });

    const currentToolCallId = latestNeedsOkToolCallId([older, latest]);

    expect(currentToolCallId).toBe("new-call");
    expect(messageNeedsOkIsActionable(older, currentToolCallId)).toBe(false);
    expect(messageNeedsOkIsActionable(latest, currentToolCallId)).toBe(true);
  });

  it("does not keep an approval actionable after later assistant output", () => {
    const approval = message({
      id: "approval",
      role: "assistant",
      content: "Nia needs your approval",
      structured_payload: {
        kind: "needs_ok",
        title: "Update SKU",
        body: "Update SKU: sku_id=1",
        tool_call_id: "old-call",
      },
    });
    const saved = message({
      id: "saved",
      created_at: "2026-09-03T10:02:00Z",
      role: "assistant",
      content: "Update SKU saved: NIA-CAT.",
    });

    const currentToolCallId = latestNeedsOkToolCallId([approval, saved]);

    expect(currentToolCallId).toBeNull();
    expect(messageNeedsOkIsActionable(approval, currentToolCallId)).toBe(false);
  });
});
