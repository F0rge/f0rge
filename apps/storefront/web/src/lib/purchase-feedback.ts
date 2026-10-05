const RETIRED_PROMISES = new Set([
  "A considered addition to your living space.",
  "Our collection is taking shape. Explore again soon.",
  "Collections are taking shape.",
]);

export function purchaseFeedback(message: string, failed: boolean): {
  role: "alert" | "status";
  tabIndex: -1;
  message: string;
} {
  return { role: failed ? "alert" : "status", tabIndex: -1, message };
}

export function customerFacingCopy(value: string | null | undefined): string | null {
  const text = value?.trim() ?? "";
  if (!text || RETIRED_PROMISES.has(text)) return null;
  return text;
}
