import { afterEach, describe, expect, it, vi } from "vitest";
import { labelPageCss, loadLabelSettings } from "./label-settings";
import { setStaffTokenGetter } from "./staff-fetch";

describe("tenant print settings", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setStaffTokenGetter(null);
  });
  it("fetches fresh settings with the active staff token for every print", async () => {
    let tenant = "a";
    setStaffTokenGetter(async () => tenant);
    const fetch = vi.fn(
      async (_path, options) =>
        new Response(
          JSON.stringify({
            label_width_mm:
              options.headers.get("Authorization") === "Bearer a" ? 100 : 80,
            has_logo: false,
          }),
        ),
    );
    vi.stubGlobal("fetch", fetch);
    expect((await loadLabelSettings()).label_width_mm).toBe(100);
    tenant = "b";
    expect((await loadLabelSettings()).label_width_mm).toBe(80);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it("bounds dimensions before interpolating print CSS", () => {
    expect(
      labelPageCss({
        label_width_mm: 999,
        label_height_mm: -1,
        label_show_name: true,
        label_show_barcode: true,
        label_show_logo: false,
        label_show_reference: true,
      }),
    ).toContain("size: 300mm 20mm");
  });
});
