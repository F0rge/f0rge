'use client'

/**
 * CheckinBoard — V2 cards dashboard state owner.
 *
 * Pure data-entry surface. No reorder mode (that lives in /customize/reorder).
 * Cards render in the order saved in localStorage (ht.cards-v2.order), with
 * cards in ht.cards-v2.hidden filtered out.
 */

import { useMemo } from 'react'
import Link from 'next/link'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'
import {
  Button,
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from '@f0rge/ui'
import type { Entry } from '@/lib/api/types'
import { computeCardColSpans } from '@/lib/checkin/compute-card-col-spans'
import { ProtocolCard } from './cards'
import { buildCheckinCardRenderers } from './checkin-card-registry'
import { useCheckinBoardState } from './use-checkin-board-state'

interface AutosaveFns {
  flush: () => void
  forceFlush: () => Promise<void>
  retry: () => void
  flushBeacon: () => void
}

interface CheckinBoardProps {
  date: string
  existingEntry?: Entry | null
  onAutosaveStateChange?: (state: AutosaveState) => void
  onAutosaveFnsReady?: (fns: AutosaveFns) => void
  onOpenPhotoFocus: (photoId: number) => void
}

export function CheckinBoard({
  date,
  existingEntry,
  onAutosaveStateChange,
  onAutosaveFnsReady,
  onOpenPhotoFocus,
}: CheckinBoardProps) {
  const state = useCheckinBoardState({
    date,
    existingEntry,
    onAutosaveStateChange,
    onAutosaveFnsReady,
  })

  const cardRenderers = buildCheckinCardRenderers({
    date,
    existingEntry,
    state,
    onOpenPhotoFocus,
  })

  const visibleIds = useMemo(
    () => state.cardOrder.filter((id) => !state.hiddenCards.includes(id)),
    [state.cardOrder, state.hiddenCards],
  )

  const colSpans = useMemo(() => computeCardColSpans(visibleIds), [visibleIds])

  return (
    <div className="space-y-4 pb-8">
      <div className="em-stagger checkin-board grid grid-cols-12 gap-4 auto-rows-min">
        <ProtocolCard
          date={date}
          collapsed={state.isCardCollapsed('protocol')}
          onToggleCollapsed={() => state.toggleCardCollapsed('protocol')}
        />

        {visibleIds.length === 0 ? (
          <div className="col-span-12" data-tour="checkin-empty-sections">
            <Empty className="border-border">
              <EmptyHeader>
                <EmptyTitle>No check-in sections visible</EmptyTitle>
                <EmptyDescription>
                  Every section is hidden. Open Reorder &amp; visibility to show sections on your
                  daily check-in again.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button render={<Link href="/customize/reorder" />} className="rounded-full">
                  Reorder &amp; visibility
                </Button>
              </EmptyContent>
            </Empty>
          </div>
        ) : (
          visibleIds.map((id) => (
            <div key={id} className={colSpans[id]} data-tour={`checkin-${id}`}>
              {cardRenderers[id]()}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
