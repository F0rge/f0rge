"use client";

import {
  DataTableSkeleton,
  SkeletonPlaceholder,
  SkeletonText,
  TextInputSkeleton,
  Tile,
} from "@carbon/react";

export type PageLoadingKind =
  | "home"
  | "till"
  | "purchase-orders"
  | "settings"
  | "organisation"
  | "table"
  | "form";

/** Native Carbon skeletons reserve the space the requested page will occupy. */
export function PageLoading({
  kind = "table",
  label = "Loading page…",
}: {
  kind?: PageLoadingKind;
  label?: string;
}) {
  const form =
    kind === "form" || kind === "settings" || kind === "organisation";
  return (
    <section
      className={`firstout-page-loading firstout-page-loading--${kind}`}
      aria-busy="true"
      aria-label={label}
    >
      <span role="status" className="firstout-sr-only">
        {label}
      </span>
      <div aria-hidden="true">
        <SkeletonText heading width="35%" />
        <SkeletonText width="55%" />
        {kind === "home" && (
          <div className="firstout-loading-metrics">
            {Array.from({ length: 4 }, (_, index) => (
              <Tile key={index}>
                <SkeletonText width="65%" />
                <SkeletonText heading width="45%" />
              </Tile>
            ))}
          </div>
        )}
        {form ? (
          <div className="firstout-loading-columns">
            <Tile>
              <SkeletonText heading width="55%" />
              {Array.from({ length: 4 }, (_, index) => (
                <TextInputSkeleton key={index} />
              ))}
            </Tile>
            <Tile>
              <SkeletonText heading width="60%" />
              <SkeletonPlaceholder className="firstout-loading-brand" />
              <SkeletonText paragraph lineCount={3} />
            </Tile>
          </div>
        ) : kind === "till" ? (
          <div className="firstout-loading-columns">
            <div className="firstout-loading-products">
              {Array.from({ length: 6 }, (_, index) => (
                <Tile key={index}>
                  <SkeletonPlaceholder className="firstout-loading-product" />
                  <SkeletonText />
                  <SkeletonText width="40%" />
                </Tile>
              ))}
            </div>
            <Tile>
              <SkeletonText heading width="60%" />
              <SkeletonText paragraph lineCount={5} />
              <TextInputSkeleton />
              <SkeletonText heading />
            </Tile>
          </div>
        ) : (
          <div
            className={
              kind === "purchase-orders"
                ? "firstout-loading-columns"
                : undefined
            }
          >
            <DataTableSkeleton
              rowCount={5}
              columnCount={4}
              showHeader={false}
            />
            {kind === "purchase-orders" && (
              <Tile>
                <SkeletonText heading />
                <SkeletonText paragraph lineCount={6} />
              </Tile>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
