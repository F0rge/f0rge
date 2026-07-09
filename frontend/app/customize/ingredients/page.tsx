'use client'

/**
 * /customize/ingredients — page wrapper.
 *
 * Loaded via next/dynamic({ ssr: false }) so the client component
 * can use React Query hooks without any SSR mismatch risk.
 *
 * NOTE: in Next.js 16, `dynamic({ ssr: false })` is only valid inside
 * a Client Component. Removing the `'use client'` directive here
 * breaks the build with "ssr: false is not allowed with next/dynamic
 * in Server Components" — verified 2026-05-25. Same constraint applies
 * to `customize/catalogs/page.tsx`.
 */

import dynamic from 'next/dynamic'
import { PageShell } from '@/components/layout/page-shell'

const IngredientsClient = dynamic(() => import('./ingredients-client'), {
  ssr: false,
  loading: () => (
    <PageShell>
      <div className="h-6 w-32 animate-pulse rounded bg-muted" />
      <div className="mt-4 h-7 w-40 animate-pulse rounded bg-muted" />
      <div className="mt-3 h-16 w-full animate-pulse rounded bg-muted" />
      <div className="mt-4 h-11 w-full animate-pulse rounded bg-muted" />
      <div className="mt-3 flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-14 w-full animate-pulse rounded bg-muted" />
        ))}
      </div>
    </PageShell>
  ),
})

export default function IngredientsPage() {
  return <IngredientsClient />
}
