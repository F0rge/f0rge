/** Phone Nia chrome: bottom sheet, not a shrunk right dock. */
export const NIA_PHONE_LAYOUT = "sheet" as const;
export const NIA_DESKTOP_LAYOUT = "dock" as const;

export const NIA_DOCK_MIN_WIDTH_PX = 320;
export const NIA_DOCK_DEFAULT_WIDTH_PX = 384;
export const NIA_DOCK_MAX_WIDTH_RATIO = 0.8;

export type NiaPanelLayout = typeof NIA_PHONE_LAYOUT | typeof NIA_DESKTOP_LAYOUT;

export function niaPanelLayout(narrowViewport: boolean): NiaPanelLayout {
  return narrowViewport ? NIA_PHONE_LAYOUT : NIA_DESKTOP_LAYOUT;
}

export function niaPanelClassName(open: boolean, layout: NiaPanelLayout): string {
  const classes = ["firstout-nia-dock"];
  if (open) {
    classes.push("firstout-nia-dock--open");
  }
  if (layout === NIA_PHONE_LAYOUT) {
    classes.push("firstout-nia-dock--sheet");
  }
  return classes.join(" ");
}

/** Right-column inset only when the desktop dock is open. Sheets overlay. */
export function shouldInsetMainForNia(open: boolean, layout: NiaPanelLayout): boolean {
  return open && layout === NIA_DESKTOP_LAYOUT;
}

export function clampNiaDockWidth(width: number, viewportWidth: number): number {
  const maxWidth = Math.floor(viewportWidth * NIA_DOCK_MAX_WIDTH_RATIO);
  return Math.min(maxWidth, Math.max(NIA_DOCK_MIN_WIDTH_PX, width));
}

/** Open/layout attributes. Do not call on every width tick — cleanup would drop the main inset. */
export function applyNiaShellOpenState(
  shell: HTMLElement,
  layout: NiaPanelLayout,
  dockOpen: boolean,
): void {
  shell.setAttribute("data-nia-layout", layout);
  if (dockOpen) {
    shell.setAttribute("data-nia-dock-open", "true");
  } else {
    shell.removeAttribute("data-nia-dock-open");
  }
}

/** Width var only. Safe during drag; never removes data-nia-dock-open. */
export function applyNiaDockWidthVar(
  shell: HTMLElement,
  layout: NiaPanelLayout,
  dockOpen: boolean,
  widthPx: number,
): void {
  if (shouldInsetMainForNia(dockOpen, layout)) {
    shell.style.setProperty("--firstout-nia-dock-width", `${widthPx}px`);
  } else {
    shell.style.removeProperty("--firstout-nia-dock-width");
  }
}

export function applyNiaShellResizing(shell: HTMLElement, resizing: boolean): void {
  if (resizing) {
    shell.setAttribute("data-nia-resizing", "true");
  } else {
    shell.removeAttribute("data-nia-resizing");
  }
}

export function clearNiaShellChrome(shell: HTMLElement): void {
  shell.removeAttribute("data-nia-dock-open");
  shell.removeAttribute("data-nia-layout");
  shell.removeAttribute("data-nia-resizing");
  shell.style.removeProperty("--firstout-nia-dock-width");
}
