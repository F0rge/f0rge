import { describe, expect, it } from "vitest";

import {
  NIA_DESKTOP_LAYOUT,
  NIA_PHONE_LAYOUT,
  niaPanelClassName,
  niaPanelLayout,
  shouldInsetMainForNia,
} from "./nia-panel-layout";

describe("nia panel layout", () => {
  it("uses a bottom sheet on the narrow viewport", () => {
    expect(niaPanelLayout(true)).toBe(NIA_PHONE_LAYOUT);
    expect(niaPanelLayout(false)).toBe(NIA_DESKTOP_LAYOUT);
  });

  it("adds the sheet class without shrinking the dock", () => {
    expect(niaPanelClassName(true, NIA_PHONE_LAYOUT)).toBe(
      "firstout-nia-dock firstout-nia-dock--open firstout-nia-dock--sheet",
    );
    expect(niaPanelClassName(false, NIA_DESKTOP_LAYOUT)).toBe("firstout-nia-dock");
  });

  it("does not inset the page when Nia is a sheet", () => {
    expect(shouldInsetMainForNia(true, NIA_PHONE_LAYOUT)).toBe(false);
    expect(shouldInsetMainForNia(true, NIA_DESKTOP_LAYOUT)).toBe(true);
    expect(shouldInsetMainForNia(false, NIA_DESKTOP_LAYOUT)).toBe(false);
  });
});
