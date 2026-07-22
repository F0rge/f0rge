'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { Button, FetchError } from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { CheckinDefaultsForm } from '@/components/customize/checkin-defaults-form'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import {
  useUserSettings,
  useUpdateCheckinDefaults,
  useSupplementCatalog,
  useSymptomCatalog,
} from '@/lib/api/hooks'

export default function DefaultsClient() {
  const settings = useUserSettings()
  const updateDefaults = useUpdateCheckinDefaults()
  const { data: allSupplements = [], isLoading: supplementsLoading } = useSupplementCatalog(false)
  const { data: allSymptoms = [], isLoading: symptomsLoading } = useSymptomCatalog(false)

  const activeSupplements = useMemo(
    () => allSupplements.filter((s) => !s.archived),
    [allSupplements],
  )
  const activeSymptoms = useMemo(
    () => allSymptoms.filter((s) => !s.archived),
    [allSymptoms],
  )
  const activeSuppKeys = useMemo(
    () => new Set(activeSupplements.map((s) => s.key)),
    [activeSupplements],
  )
  const activeSymptomKeys = useMemo(
    () => new Set(activeSymptoms.map((s) => s.key)),
    [activeSymptoms],
  )

  const serverSupplements = useMemo(() => {
    if (!settings.data || supplementsLoading) return null
    return (settings.data.default_supplements ?? []).filter((k) => activeSuppKeys.has(k))
  }, [settings.data, supplementsLoading, activeSuppKeys])

  const serverSymptoms = useMemo(() => {
    if (!settings.data || symptomsLoading) return null
    return Object.fromEntries(
      Object.entries(settings.data.default_symptoms ?? {}).filter(([k]) =>
        activeSymptomKeys.has(k),
      ),
    )
  }, [settings.data, symptomsLoading, activeSymptomKeys])

  const [localSupplements, setLocalSupplements] = useState<string[] | null>(null)
  const [localSymptoms, setLocalSymptoms] = useState<Record<string, number> | null>(null)

  const selectedSupplements = localSupplements ?? serverSupplements
  const symptomDefaults = localSymptoms ?? serverSymptoms

  const handleSave = async () => {
    if (selectedSupplements === null || symptomDefaults === null) return
    const payload = {
      default_supplements: selectedSupplements.filter((k) => activeSuppKeys.has(k)),
      default_symptoms: Object.fromEntries(
        Object.entries(symptomDefaults).filter(([k]) => activeSymptomKeys.has(k)),
      ),
    }
    try {
      await updateDefaults.mutateAsync(payload)
      setLocalSupplements(null)
      setLocalSymptoms(null)
      toast.success('Check-in defaults saved')
    } catch (err) {
      handleMutationError(err, 'Could not save check-in defaults')
    }
  }

  if (settings.isError) {
    return (
      <PageShell>
        <FetchError message="Failed to load settings." onRetry={() => settings.refetch()} />
      </PageShell>
    )
  }

  const draftReady = selectedSupplements !== null && symptomDefaults !== null

  return (
    <PageShell>
      <PageHeader
        leading={
          <Link
            href="/customize"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back
          </Link>
        }
        title="Check-in defaults"
        subtitle="Prefills empty check-in days. Does not create a day until you change something."
      />

      {draftReady ? (
        <>
          <CheckinDefaultsForm
            supplements={activeSupplements}
            symptoms={activeSymptoms}
            supplementsLoading={supplementsLoading}
            symptomsLoading={symptomsLoading}
            selectedSupplements={selectedSupplements}
            onSupplementsChange={setLocalSupplements}
            symptomDefaults={symptomDefaults}
            onSymptomDefaultsChange={setLocalSymptoms}
          />
          <div className="mt-8">
            <Button
              className="w-full"
              onClick={() => void handleSave()}
              disabled={updateDefaults.isPending}
            >
              {updateDefaults.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </>
      ) : (
        <div className="space-y-4">
          <div className="h-5 w-28 animate-pulse rounded bg-muted" />
          <div className="grid grid-cols-3 gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-xl bg-muted" />
            ))}
          </div>
        </div>
      )}
    </PageShell>
  )
}
