"use client";

import { Button, InlineNotification } from "@carbon/react";
import { useEffect } from "react";
import styles from "./administration.module.css";

export function confirmDiscardChanges(dirty: boolean, message = "Discard the unsaved changes?") {
  return !dirty || window.confirm(message);
}

export function useAdminDraftNavigation(dirty: boolean, saving: boolean, message?: string, onDiscard?: () => void) {
  useEffect(() => {
    if (!dirty) return;

    function beforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = true;
    }

    function confirmNavigation(event: MouseEvent) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null;
      if (!link || (link.target && link.target !== "_self") || link.hasAttribute("download")) return;
      const destination = new URL(link.href);
      if (destination.origin !== window.location.origin ||
        (destination.pathname === window.location.pathname && destination.search === window.location.search)) return;
      if (saving || !confirmDiscardChanges(dirty, message)) {
        event.preventDefault();
        event.stopPropagation();
      } else {
        onDiscard?.();
      }
    }

    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", confirmNavigation, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", confirmNavigation, true);
    };
  }, [dirty, saving, message, onDiscard]);
}

export function AdminSaveActions({
  canMutate, saving, onSave, onDiscard, dirty, saveDisabled = false,
}: {
  canMutate: boolean;
  saving: boolean;
  onSave?: () => void;
  saveDisabled?: boolean;
  onDiscard: () => void;
  dirty: boolean;
}) {
  useAdminDraftNavigation(canMutate && dirty, saving, undefined, onDiscard);

  if (!canMutate) {
    return <InlineNotification kind="info" title="Read only" subtitle="You do not have permission to change settings." hideCloseButton lowContrast />;
  }

  return (
    <div className={styles.saveActions}>
      <span role="status">{dirty ? "Unsaved changes" : ""}</span>
      <Button kind="secondary" disabled={saving || !dirty} onClick={onDiscard}>
        Discard changes
      </Button>
      <Button type={onSave ? "button" : "submit"} disabled={saving || !dirty || saveDisabled} onClick={onSave}>
        {saving ? "Saving…" : "Save changes"}
      </Button>
    </div>
  );
}
