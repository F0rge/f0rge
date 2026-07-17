'use client'

import { PageShell } from '@/components/layout/page-shell'
import { ProfileHeader } from '@/components/profile/profile-header'
import { ConsistencyRow } from '@/components/profile/consistency-row'
import { MetricCards } from '@/components/profile/metric-cards'
import { MealGrids } from '@/components/profile/meal-grids'

export default function ProfilePage() {
  return (
    <PageShell className="max-w-2xl space-y-5 pb-2">
      <ProfileHeader />
      <ConsistencyRow />
      <MetricCards />
      <MealGrids />
    </PageShell>
  )
}
