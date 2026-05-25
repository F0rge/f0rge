'use client'

/**
 * /customize/catalogs — page wrapper.
 *
 * Loaded via next/dynamic({ ssr: false }) so the client component
 * can use React Query hooks without any SSR mismatch risk.
 */

import dynamic from 'next/dynamic'

const CatalogsClient = dynamic(() => import('./catalogs-client'), {
  ssr: false,
  loading: () => (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="h-6 w-32 animate-pulse rounded bg-muted" />
      <div className="mt-4 h-7 w-40 animate-pulse rounded bg-muted" />
      <div className="mt-3 h-16 w-full animate-pulse rounded bg-muted" />
      <div className="mt-4 h-5 w-28 animate-pulse rounded bg-muted" />
      <div className="mt-2 flex flex-col gap-px">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-10 w-full animate-pulse rounded bg-muted" />
        ))}
      </div>
    </div>
  ),
})

export default function CatalogsPage() {
  return <CatalogsClient />
}
