export function printHtml(html: string, reservedWindow?: Window | null): void {
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const printWindow = reservedWindow ?? window.open(url, "_blank");
  if (reservedWindow) reservedWindow.location.href = url;
  if (!printWindow) {
    URL.revokeObjectURL(url);
    window.alert("Allow pop-ups to print.");
    return;
  }

  let printed = false;
  const triggerPrint = () => {
    if (printed) {
      return;
    }
    printed = true;
    printWindow.print();
  };

  printWindow.addEventListener("load", triggerPrint);
  if (!reservedWindow && printWindow.document.readyState === "complete") {
    triggerPrint();
  }
  printWindow.addEventListener("afterprint", () => {
    URL.revokeObjectURL(url);
  });
}
