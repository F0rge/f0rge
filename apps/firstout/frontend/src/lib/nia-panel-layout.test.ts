import { describe, expect, it } from "vitest";

function fakeShell(): HTMLElement {
  const attrs = new Map<string, string>();
  const props = new Map<string, string>();
  return {
    setAttribute(name: string, value: string) {
      attrs.set(name, value);
    },
    removeAttribute(name: string) {
      attrs.delete(name);
    },
    getAttribute(name: string) {
      return attrs.has(name) ? (attrs.get(name) as string) : null;
    },
    style: {
      setProperty(name: string, value: string) {
        props.set(name, value);
      },
      removeProperty(name: string) {
        props.delete(name);
        return "";
      },
      getPropertyValue(name: string) {
        return props.get(name) ?? "";
      },
    },
  } as unknown as HTMLElement;
}

import {
  NIA_DESKTOP_LAYOUT,
  NIA_DOCK_DEFAULT_WIDTH_PX,
  NIA_DOCK_MAX_WIDTH_PX,
  NIA_DOCK_MIN_WIDTH_PX,
  NIA_DOCK_WIDTH_STOPS_PX,
  NIA_PHONE_LAYOUT,
  applyNiaDockWidthVar,
  applyNiaShellOpenState,
  applyNiaShellResizing,
  clampNiaDockWidth,
  clearNiaShellChrome,
  niaDockWidthStopsForViewport,
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

  it("snaps dock width to the allowed stops", () => {
    expect(niaDockWidthStopsForViewport(1400)).toEqual([...NIA_DOCK_WIDTH_STOPS_PX]);
    expect(clampNiaDockWidth(100, 1400)).toBe(NIA_DOCK_MIN_WIDTH_PX);
    expect(clampNiaDockWidth(350, 1400)).toBe(NIA_DOCK_MIN_WIDTH_PX);
    expect(clampNiaDockWidth(370, 1400)).toBe(NIA_DOCK_DEFAULT_WIDTH_PX);
    expect(clampNiaDockWidth(430, 1400)).toBe(NIA_DOCK_MAX_WIDTH_PX);
    expect(clampNiaDockWidth(2000, 1400)).toBe(NIA_DOCK_MAX_WIDTH_PX);
  });

  it("drops stops that would consume most of a short viewport", () => {
    expect(niaDockWidthStopsForViewport(800)).toEqual([NIA_DOCK_MIN_WIDTH_PX]);
    expect(clampNiaDockWidth(448, 800)).toBe(NIA_DOCK_MIN_WIDTH_PX);
  });

  it("updates the dock width var without dropping the open inset", () => {
    const shell = fakeShell();
    applyNiaShellOpenState(shell, NIA_DESKTOP_LAYOUT, true);
    applyNiaDockWidthVar(shell, NIA_DESKTOP_LAYOUT, true, 420);
    expect(shell.getAttribute("data-nia-dock-open")).toBe("true");
    expect(shell.style.getPropertyValue("--firstout-nia-dock-width")).toBe("420px");

    applyNiaDockWidthVar(shell, NIA_DESKTOP_LAYOUT, true, NIA_DOCK_MAX_WIDTH_PX);
    expect(shell.getAttribute("data-nia-dock-open")).toBe("true");
    expect(shell.getAttribute("data-nia-layout")).toBe("dock");
    expect(shell.style.getPropertyValue("--firstout-nia-dock-width")).toBe(
      `${NIA_DOCK_MAX_WIDTH_PX}px`,
    );
  });

  it("clears chrome only from the explicit unmount helper", () => {
    const shell = fakeShell();
    applyNiaShellOpenState(shell, NIA_DESKTOP_LAYOUT, true);
    applyNiaDockWidthVar(shell, NIA_DESKTOP_LAYOUT, true, 384);
    applyNiaShellResizing(shell, true);
    applyNiaDockWidthVar(shell, NIA_DESKTOP_LAYOUT, true, 500);
    expect(shell.getAttribute("data-nia-dock-open")).toBe("true");
    expect(shell.getAttribute("data-nia-resizing")).toBe("true");

    clearNiaShellChrome(shell);
    expect(shell.getAttribute("data-nia-dock-open")).toBeNull();
    expect(shell.getAttribute("data-nia-layout")).toBeNull();
    expect(shell.getAttribute("data-nia-resizing")).toBeNull();
    expect(shell.style.getPropertyValue("--firstout-nia-dock-width")).toBe("");
  });
});
