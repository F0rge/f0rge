"use client";

import { DataTableSkeleton, SkeletonPlaceholder, SkeletonText, TextInputSkeleton } from "@carbon/react";
import type { ComponentProps, ReactNode } from "react";

export function LoadingRegion({
  label,
  className,
  children,
  announce = true,
  visibleStatus = false,
}: {
  label: string;
  className?: string;
  children?: ReactNode;
  announce?: boolean;
  visibleStatus?: boolean;
}) {
  return (
    <div className={["firstout-page-loading", className].filter(Boolean).join(" ")}>
      {announce && (visibleStatus ? (
        <div className="firstout-loading-status" role="status">
          <div aria-hidden="true"><SkeletonText width="2rem" /></div>
          <span>{label}</span>
        </div>
      ) : <span role="status" className="firstout-sr-only">{label}</span>)}
      {children && <section aria-busy="true" aria-label={label}>{children}</section>}
    </div>
  );
}

type TableLoadingProps = {
  columns: readonly string[] | number;
  rows?: number;
  toolbar?: boolean;
  pagination?: boolean;
  size?: ComponentProps<typeof DataTableSkeleton>["size"];
};

export function LoadingTableRows({
  columns,
  rows = 3,
  toolbar = false,
  pagination = false,
  size,
}: TableLoadingProps) {
  const headers = typeof columns === "number" ? undefined : columns.map((header) => ({ header }));
  return (
    <div className="firstout-loading-table" aria-hidden="true">
      <DataTableSkeleton
        headers={headers}
        columnCount={typeof columns === "number" ? columns : columns.length}
        rowCount={rows}
        size={size}
        showHeader={false}
        showToolbar={toolbar}
      />
      {pagination && (
        <div className="firstout-loading-pagination">
          <SkeletonText width="6rem" />
          <SkeletonText width="5rem" />
        </div>
      )}
    </div>
  );
}

export function LoadingField({ label, height = "2.5rem", width, helperText }: {
  label?: string;
  height?: string;
  width?: string;
  helperText?: string;
}) {
  return (
    <div className="cds--form-item" style={{ width, maxWidth: "100%" }}>
      {label && <span className="cds--label">{label}</span>}
      <SkeletonPlaceholder aria-hidden="true" style={{ width: "100%", height }} />
      {helperText && <p className="cds--form__helper-text">{helperText}</p>}
    </div>
  );
}

export function PageLoading({
  label = "Loading page…",
  title,
  description,
  kind,
  fields,
  columns,
  rows,
  toolbar,
  pagination,
  size,
}: Partial<TableLoadingProps> & {
  label?: string;
  title?: string;
  description?: string;
  kind?: "form" | "status";
  fields?: readonly string[];
}) {
  if (columns === undefined && kind !== "form") {
    return <LoadingRegion label={label} visibleStatus />;
  }
  return (
    <LoadingRegion label={label}>
      {columns !== undefined ? (
        <>
          {title && (
            <div className="cds--data-table-header">
              <h4 className="cds--data-table-header__title">{title}</h4>
              {description && <p className="cds--data-table-header__description">{description}</p>}
            </div>
          )}
          <LoadingTableRows columns={columns} rows={rows} toolbar={toolbar} pagination={pagination} size={size} />
        </>
      ) : (
        <div className="firstout-loading-fields">
          {fields?.length ? fields.map((field) => <LoadingField key={field} label={field} />) : (
            <div aria-hidden="true"><TextInputSkeleton /></div>
          )}
        </div>
      )}
    </LoadingRegion>
  );
}
