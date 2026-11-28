"use client";

import { Breadcrumb, BreadcrumbItem } from "@carbon/react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { breadcrumbsForPath } from "@/lib/breadcrumbs";

export function AppBreadcrumb() {
  const crumbs = breadcrumbsForPath(usePathname(), useSearchParams());
  if (crumbs.length < 2) return null;
  return (
    <Breadcrumb
      noTrailingSlash
      className="firstout-breadcrumb"
      aria-label="Breadcrumb"
    >
      {crumbs.map((crumb, index) => (
        <BreadcrumbItem
          key={`${index}:${crumb.label}`}
          isCurrentPage={index === crumbs.length - 1}
          aria-current={index === crumbs.length - 1 ? "page" : undefined}
        >
          {crumb.href ? (
            <Link href={crumb.href}>{crumb.label}</Link>
          ) : (
            crumb.label
          )}
        </BreadcrumbItem>
      ))}
    </Breadcrumb>
  );
}
