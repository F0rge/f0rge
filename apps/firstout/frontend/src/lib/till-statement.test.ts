import { describe, expect, it } from "vitest";

import { localIsoDate, statementDueDate } from "./till-statement";

describe("statementDueDate", () => {
  it("adds the customer's terms, else the team's, else 30 days", () => {
    expect(statementDueDate("2026-11-21", 14, 30)).toBe("2026-12-05");
    expect(statementDueDate("2026-11-21", null, 7)).toBe("2026-11-28");
    expect(statementDueDate("2026-11-21", 0, 30)).toBe("2026-11-21");
    expect(statementDueDate("2026-12-20", undefined, undefined)).toBe("2027-01-19");
  });

  it("formats the local calendar date", () => {
    expect(localIsoDate(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
  });
});
