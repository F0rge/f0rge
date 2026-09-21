const REVOKE_MS = 60_000;

function filenameFromDisposition(header: string | null, fallback: string): string {
  const named = header?.match(/filename="([^"]+)"/)?.[1];
  return named?.trim() || fallback;
}

function isErrorDocument(contentType: string | null): boolean {
  const type = (contentType ?? "").toLowerCase();
  return type.includes("application/json") || type.includes("text/html");
}

function revokeLater(url: string): void {
  window.setTimeout(() => URL.revokeObjectURL(url), REVOKE_MS);
}

export async function downloadApiFile(
  path: string,
  fallbackFilename: string,
  mode: "save" | "open" = "save",
): Promise<void> {
  const { ApiError, parseErrorMessage } = await import("./api");
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response));
  }
  if (isErrorDocument(response.headers.get("Content-Type"))) {
    throw new ApiError(response.status, await parseErrorMessage(response));
  }

  const filename = filenameFromDisposition(
    response.headers.get("Content-Disposition"),
    fallbackFilename,
  );
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);

  if (mode === "open") {
    const opened = window.open(url, "_blank");
    if (!opened) {
      revokeLater(url);
      window.alert("Allow pop-ups to print.");
      return;
    }
    opened.addEventListener("load", () => {
      revokeLater(url);
    });
    revokeLater(url);
    return;
  }

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  revokeLater(url);
}
