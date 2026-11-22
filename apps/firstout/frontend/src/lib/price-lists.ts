const CIN7_NAMED_PRICE_LISTS = new Set([
  "Cin7 Stockist",
  "Cin7 Wholesale",
  "Cin7 Decorator",
  "Cin7 Retail",
]);

/** Historical Cin7 price lists. The server skips them when pricing; the UI labels them. */
export function isCin7GeneratedPriceList(name: string | null | undefined): boolean {
  const text = name?.trim() ?? "";
  return CIN7_NAMED_PRICE_LISTS.has(text) || /^Cin7 Tier [1-9]\d*$/.test(text);
}
