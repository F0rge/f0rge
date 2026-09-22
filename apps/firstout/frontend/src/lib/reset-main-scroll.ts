/** Reset window + main content scroll after a pathname (tab) change. */
export function resetMainScroll(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.scrollTo(0, 0);
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
  const main = document.getElementById("main-content");
  if (main) {
    main.scrollTop = 0;
  }
}
