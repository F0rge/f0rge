"use client";

import { InlineNotification } from "@carbon/react";
import { useLayoutEffect, useRef, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";

/** The content of the top open Carbon dialog, where an error must show so staff can see it. */
export function openDialogContent(root: Pick<ParentNode, "querySelectorAll">): Element | null {
  const open = root.querySelectorAll(".cds--modal.is-visible .cds--modal-content");
  return open[open.length - 1] ?? null;
}

function watchDialogs(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

const ignore = () => () => {};

/**
 * A page's error notice. While a dialog is open it renders inside that dialog instead of
 * behind it, so an action that fails in a dialog is seen and announced there, once.
 */
export function ErrorNotice({
  error,
  title = "Error",
  onClose,
}: {
  error: string | null | undefined;
  title?: string;
  onClose?: () => void;
}) {
  // Watch the page only while there is an error to place.
  const dialog = useSyncExternalStore(
    error ? watchDialogs : ignore,
    () => (error ? openDialogContent(document) : null),
    () => null,
  );
  const notice = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (dialog) notice.current?.scrollIntoView?.({ block: "nearest" });
  }, [dialog, error]);
  if (!error) return null;
  const element = (
    <div ref={notice}>
      <InlineNotification
        kind="error"
        role="alert"
        title={title}
        subtitle={error}
        // Inside a dialog: no close button, as the dialog's focus trap cannot see a portaled one.
        hideCloseButton={!onClose || dialog !== null}
        onCloseButtonClick={onClose}
        lowContrast
      />
    </div>
  );
  return dialog ? createPortal(element, dialog) : element;
}
