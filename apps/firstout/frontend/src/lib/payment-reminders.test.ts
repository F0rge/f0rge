import { describe, expect, it } from "vitest";

import { reminderOffsetLabel } from "./payment-reminders";

describe("reminderOffsetLabel", () => {
  it("describes the default schedule in plain language", () => {
    expect(reminderOffsetLabel(-3)).toBe("3 days before the due date");
    expect(reminderOffsetLabel(-1)).toBe("1 day before the due date");
    expect(reminderOffsetLabel(0)).toBe("On the due date");
    expect(reminderOffsetLabel(1)).toBe("1 day overdue");
    expect(reminderOffsetLabel(7)).toBe("7 days overdue");
    expect(reminderOffsetLabel(30)).toBe("30 days overdue");
  });
});
