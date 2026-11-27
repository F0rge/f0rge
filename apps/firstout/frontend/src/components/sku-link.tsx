"use client";

import Link from "next/link";
import type { MouseEvent, ReactNode } from "react";
import { useSkuPanel } from "@/components/sku-panel/provider";
import type { SkuPanelContext } from "@/lib/sku-panel";

/**
 * A SKU ref or name that docks the SKU panel on the current page. It is a real link to
 * `/catalogue/{id}`, so new-tab, middle-click and no-JS still work.
 */
export function SkuLink({ id, context, className, children }: {
  id: string;
  /** What ↑ ↓ step through once the panel is open (for example every line of this purchase order). */
  context?: SkuPanelContext;
  className?: string;
  children: ReactNode;
}) {
  const panel = useSkuPanel();
  function onClick(event: MouseEvent<HTMLAnchorElement>) {
    if (!panel || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    panel.open(id, context);
  }
  return (
    <Link href={`/catalogue/${id}`} prefetch={false} className={className ?? "cds--link"} onClick={onClick} data-sku-link="">
      {children}
    </Link>
  );
}
