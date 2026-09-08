"use client";

import { useEffect, useId, useRef } from "react";

import { buildSpreadsheetConfig } from "@/lib/nia-spreadsheet";

import styles from "./nia-spreadsheet.module.css";

import "jspreadsheet-ce/dist/jspreadsheet.css";
import "jspreadsheet-ce/dist/jspreadsheet.themes.css";
import "jsuites/dist/jsuites.css";

export type NiaSpreadsheetProps = {
  title?: string;
  headers: string[];
  rows: string[][];
  readOnly?: boolean;
  compact?: boolean;
  className?: string;
};

type JspreadsheetModule = {
  (
    element: HTMLDivElement | HTMLTableElement,
    options: ReturnType<typeof buildSpreadsheetConfig>,
  ): unknown;
  destroy: (element: HTMLElement, destroyEventHandlers?: boolean) => void;
};

function resolveJspreadsheet(mod: unknown): JspreadsheetModule {
  if (typeof mod === "function") {
    return mod as JspreadsheetModule;
  }
  if (mod && typeof mod === "object" && "default" in mod) {
    const nested = (mod as { default: unknown }).default;
    if (typeof nested === "function") {
      return nested as JspreadsheetModule;
    }
  }
  throw new Error("jspreadsheet-ce did not export a constructor");
}

export function NiaSpreadsheet({
  title,
  headers,
  rows,
  readOnly = true,
  compact = false,
  className,
}: NiaSpreadsheetProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const headingId = useId();
  const headersKey = JSON.stringify(headers);
  const rowsKey = JSON.stringify(rows);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) {
      return;
    }

    let cancelled = false;
    let destroy: (() => void) | undefined;

    void import("jspreadsheet-ce").then((mod) => {
      if (cancelled || hostRef.current !== el) {
        return;
      }
      const jspreadsheet = resolveJspreadsheet(mod);
      const options = buildSpreadsheetConfig({
        headers: JSON.parse(headersKey) as string[],
        rows: JSON.parse(rowsKey) as string[][],
        readOnly,
        compact,
      });
      jspreadsheet(el, options);
      destroy = () => {
        try {
          jspreadsheet.destroy(el, true);
        } catch {
          el.replaceChildren();
        }
      };
      if (cancelled) {
        destroy();
      }
    });

    return () => {
      cancelled = true;
      destroy?.();
    };
  }, [compact, headersKey, readOnly, rowsKey]);

  const rootClass = [
    styles.root,
    compact ? styles.compact : undefined,
    "vellano-nia-spreadsheet",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={rootClass} aria-labelledby={title ? headingId : undefined}>
      {title ? (
        <h2 id={headingId} className={`cds--type-heading-compact-01 ${styles.heading}`}>
          {title}
        </h2>
      ) : null}
      <div
        ref={hostRef}
        className={styles.host}
        role="region"
        aria-label={title ? undefined : "Spreadsheet"}
        aria-labelledby={title ? headingId : undefined}
      />
    </section>
  );
}
