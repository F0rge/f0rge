/** True unless the Nia dock is already on `/canvas`. Query/hash ignored; `/canvas/` is the same route. */
export function showViewCanvasButton(pathname: string): boolean {
  const pathOnly = pathname.split(/[?#]/, 1)[0] ?? "";
  const normalized = pathOnly.replace(/\/+$/, "") || "/";
  return normalized !== "/canvas";
}
