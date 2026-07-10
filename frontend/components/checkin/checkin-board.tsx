'use client'

/**
 * CheckinBoard — V2 cards dashboard state owner.
 *
 * Pure data-entry surface. No reorder mode (that lives in /customize/reorder).
 * Cards render in the order saved in localStorage (ht.cards-v2.order), with
 * cards in ht.cards-v2.hidden filtered out.
 */

import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'
import type { Entry } from '@/lib/api/types'
import { ProtocolCard } from './cards'
import { buildCheckinCardRenderers, CARD_COL_SPAN } from './checkin-card-registry'
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

  return (
    <div className="space-y-4 pb-8">
      <div className="grid grid-cols-12 gap-4 auto-rows-min">
        <ProtocolCard date={date} />

        {state.cardOrder
          .filter((id) => !state.hiddenCards.includes(id))
          .map((id) => (
            <div key={id} className={CARD_COL_SPAN[id]} data-tour={`checkin-${id}`}>
              {cardRenderers[id]()}
            </div>
          ))}
      </div>
    </div>
  )
}
