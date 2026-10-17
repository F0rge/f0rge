import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { formatCustomerPrice, formatZar, orderMoney } from "./order-money";

const srcRoot = path.resolve(import.meta.dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    if (!full.endsWith(".ts") && !full.endsWith(".tsx")) return [];
    if (full.endsWith(".test.ts") || full.endsWith(".test.tsx")) return [];
    return [full];
  });
}

describe("ZAR customer prices", () => {
  it("formats every accepted amount in rand and refuses another currency", () => {
    expect(formatZar(1150)).toBe(new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" }).format(1150));
    expect(formatZar(1150)).toMatch(/R/);
    expect(formatCustomerPrice(1150, "zar")).toBe(formatZar(1150));
    expect(formatCustomerPrice(1150)).toBe(formatZar(1150));
    expect(orderMoney(1150, "ZAR")).toBe(formatZar(1150));
    expect(formatCustomerPrice(1150, "usd")).toBe("Price unavailable");
    expect(orderMoney(1150, "USD")).not.toMatch(/USD|\$/);
  });

  it("keeps customer-facing currency formatting in the ZAR helper", () => {
    const offenders = sourceFiles(srcRoot).filter((file) => {
      if (file.endsWith(`${path.sep}order-money.ts`)) return false;
      const source = readFileSync(file, "utf8");
      return source.includes('style: "currency"') || source.includes("style: 'currency'");
    });
    expect(offenders).toEqual([]);
    const helper = readFileSync(path.join(srcRoot, "lib", "order-money.ts"), "utf8");
    expect(helper).toContain('const ZAR = "ZAR"');
    expect(helper).toContain("currency: ZAR");
    expect(helper).not.toMatch(/currency:\s*currency/);
  });
});
