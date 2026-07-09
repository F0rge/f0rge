import Link from 'next/link'
import { ArrowLeft, Activity, BookOpen, Carrot, Layers, Pill, Settings2, Zap } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { HubRow } from '@/components/customize/hub-row'
import { PageShell } from '@/components/layout/page-shell'

export const metadata = { title: 'Customize check-in' }

const HUB_ITEMS = [
  {
    href: '/customize/reorder',
    icon: <Layers className="size-4" />,
    title: 'Reorder & visibility',
    description: 'Drag to reorder sections. Toggle which ones show on your daily check-in.',
  },
  {
    href: '/customize/core-scales',
    icon: <Activity className="size-4" />,
    title: 'Core scales',
    description: 'See how your fixed scales are structured. Labels and levels are locked by design.',
    tier: 'core' as const,
  },
  {
    href: '/customize/catalogs',
    icon: <Pill className="size-4" />,
    title: 'Catalogs',
    description: 'Pick supplements, medications, and diet tags to track from curated lists.',
    tier: 'catalog' as const,
  },
  {
    href: '/customize/ingredients',
    icon: <Carrot className="size-4" />,
    title: 'Dietary ingredients',
    description: 'Edit FODMAP / histamine / gluten / dairy classifications and aliases.',
    tier: 'catalog' as const,
  },
  {
    href: '/customize/trackers',
    icon: <BookOpen className="size-4" />,
    title: 'Custom trackers',
    description: 'Add, edit, archive, and reorder your personal trackers.',
    tier: 'custom' as const,
  },
  {
    href: '/customize/symptoms',
    icon: <Zap className="size-4" />,
    title: 'Custom symptoms',
    description: 'Manage your personal symptom list.',
    tier: 'custom' as const,
  },
]

export default function CustomizePage() {
  return (
    <PageShell>
      <div className="mb-6">
        <Link
          href="/checkin"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back
        </Link>
        <div className="mt-3 flex items-center gap-2">
          <Settings2 className="size-5 text-muted-foreground" />
          <h1 className="text-xl font-semibold tracking-tight">Customize check-in</h1>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Reorder sections, manage catalogs, and add your own trackers and symptoms.
        </p>
      </div>

      {/* Mobile: stacked list */}
      <Card className="overflow-hidden py-0 lg:hidden">
        {HUB_ITEMS.map((item) => (
          <HubRow key={item.href} {...item} />
        ))}
      </Card>

      {/* Desktop: 2-column tile grid */}
      <div className="hidden lg:grid lg:grid-cols-2 lg:gap-4">
        {HUB_ITEMS.map((item) => (
          <Card key={item.href} className="overflow-hidden py-0">
            <HubRow {...item} variant="tile" />
          </Card>
        ))}
      </div>
    </PageShell>
  )
}
