import Link from 'next/link'
import { ArrowLeft, Activity, BookOpen, Layers, Pill, Settings2, Zap } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { HubRow } from '@/components/customize/hub-row'

export const metadata = { title: 'Customize check-in' }

export default function CustomizePage() {
  return (
    <div className="mx-auto w-full max-w-lg p-4">
      {/* Header */}
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

      {/* Hub list */}
      <Card className="overflow-hidden py-0">
        <HubRow
          href="/customize/reorder"
          icon={<Layers className="size-4" />}
          title="Reorder & visibility"
          description="Drag to reorder sections. Toggle which ones show on your daily check-in."
        />
        <HubRow
          href="/customize/core-scales"
          icon={<Activity className="size-4" />}
          title="Core scales"
          description="See how your fixed scales are structured. Labels and levels are locked by design."
          tier="core"
        />
        <HubRow
          href="/customize/catalogs"
          icon={<Pill className="size-4" />}
          title="Catalogs"
          description="Pick supplements and diet tags to track from curated lists."
          tier="catalog"
          comingSoon
        />
        <HubRow
          href="/customize/trackers"
          icon={<BookOpen className="size-4" />}
          title="Custom trackers"
          description="Add, edit, archive, and reorder your personal trackers."
          tier="custom"
        />
        <HubRow
          href="/customize/symptoms"
          icon={<Zap className="size-4" />}
          title="Custom symptoms"
          description="Manage your personal symptom list."
          tier="custom"
          comingSoon
        />
      </Card>

    </div>
  )
}
