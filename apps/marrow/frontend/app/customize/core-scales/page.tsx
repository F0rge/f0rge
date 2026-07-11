import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { TierBanner } from '@/components/customize/tier-banner'
import { TierPill } from '@/components/customize/tier-pill'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'

export const metadata = { title: 'Core scales' }

// Scale definitions — static, read-only by design.
// Labels and values must match wellbeing-card.tsx and gut-card.tsx exactly.
const WELLBEING_SCALES = [
  { label: 'How was your day?',       values: 'Very Poor · Standard · Very Good' },
  { label: 'Sleep quality (last night)', values: 'Poor · OK · Good' },
  { label: 'Stress level',            values: 'Low · Medium · High' },
]

const GUT_SCALES = [
  { label: 'Bloating',            values: 'None · Mild · Moderate · Severe' },
  { label: 'Stool',               values: 'Normal · Abnormal · Skipped (when Abnormal: Bristol type 1–7)' },
]

interface ScaleRowProps {
  label: string
  values: string
}

function ScaleRow({ label, values }: ScaleRowProps) {
  return (
    <div className="flex items-start justify-between py-2.5 border-t border-muted first:border-t-0">
      <div>
        <div className="text-sm font-medium">{label}</div>
        <div className="mt-0.5 text-[10px] text-muted-foreground">{values}</div>
      </div>
    </div>
  )
}

export default function CoreScalesPage() {
  return (
    <PageShell>
      <PageHeader
        leading={
          <Link
            href="/customize"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Customize
          </Link>
        }
        title="Core scales"
        className="mb-4"
        actions={<TierPill tier="core" />}
      />

      <TierBanner tier="core">
        These scales are the backbone of your data — keeping them consistent is what
        makes cross-month and lab-correlation analysis possible. You can show or hide
        whole sections via Reorder &amp; visibility, but labels and levels are fixed.
      </TierBanner>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
            Wellbeing
          </p>
          <Card>
            <CardContent className="py-1 px-4">
              {WELLBEING_SCALES.map((s) => (
                <ScaleRow key={s.label} label={s.label} values={s.values} />
              ))}
            </CardContent>
          </Card>
        </div>

        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
            Gut
          </p>
          <Card>
            <CardContent className="py-1 px-4">
              {GUT_SCALES.map((s) => (
                <ScaleRow key={s.label} label={s.label} values={s.values} />
              ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <p className="mt-4 text-xs text-muted-foreground">
        To change which sections are visible on your daily check-in, use{' '}
        <Link href="/customize/reorder" className="underline hover:text-foreground">
          Reorder &amp; visibility
        </Link>
        .
      </p>
    </PageShell>
  )
}
