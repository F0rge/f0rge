/** Phone Nia chrome: bottom sheet, not a shrunk right dock. */
export const NIA_PHONE_LAYOUT = "sheet" as const;
export const NIA_DESKTOP_LAYOUT = "dock" as const;

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
