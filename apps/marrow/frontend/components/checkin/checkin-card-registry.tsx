'use client'

import type { ReactNode } from 'react'
import type { Entry } from '@/lib/api/types'
import type { CardId } from '@/lib/checkin/card-order'
import type { CheckinBoardState } from './use-checkin-board-state'
import {
  FoodCard,
  WellbeingCard,
  GutCard,
  SupplementsCard,
  MedicationsCard,
  SymptomsCard,
  TrackersCard,
  NotesCard,
} from './cards'

interface BuildCheckinCardRenderersOptions {
  date: string
  existingEntry?: Entry | null
  state: CheckinBoardState
  onOpenPhotoFocus: (photoId: number) => void
}

export function buildCheckinCardRenderers({
  date,
  existingEntry,
  state,
  onOpenPhotoFocus,
}: BuildCheckinCardRenderersOptions): Record<CardId, () => ReactNode> {
  const collapseProps = (id: CardId) => ({
    collapsed: state.isCardCollapsed(id),
    onToggleCollapsed: () => state.toggleCardCollapsed(id),
  })

  return {
    food: () => (
      <FoodCard
        date={date}
        existingEntry={existingEntry}
        existingPhotos={state.existingPhotos}
        dietRisk={state.dietRisk}
        onDietToggle={state.handleDietToggle}
        onPhotosChange={state.setExistingPhotos}
        ensureEntryExists={state.autosave.forceFlush}
        onEntryEnsured={state.markDirty}
        onOpenPhotoFocus={onOpenPhotoFocus}
        {...collapseProps('food')}
      />
    ),
    wellbeing: () => (
      <WellbeingCard
        overall={state.overall}
        onOverallChange={state.setOverallDirty}
        sleepQuality={state.sleepQuality}
        onSleepQualityChange={state.setSleepQualityDirty}
        stress={state.stress}
        onStressChange={state.setStressDirty}
        fivePoint={state.fivePoint}
        {...collapseProps('wellbeing')}
      />
    ),
    gut: () => (
      <GutCard
        bloating={state.bloating}
        onBloatingChange={state.setBloatingDirty}
        stoolStatus={state.stoolStatus}
        onStoolStatusChange={state.setStoolStatusDirty}
        bristolType={state.bristolType}
        onBristolTypeChange={state.setBristolTypeDirty}
        stoolCompleteness={state.stoolCompleteness}
        onStoolCompletenessChange={state.setStoolCompletenessDirty}
        {...collapseProps('gut')}
      />
    ),
    supplements: () => (
      <SupplementsCard
        value={state.supplements}
        onChange={state.handleSupplementChange}
        onTouched={state.handleSupplementTouched}
        {...collapseProps('supplements')}
      />
    ),
    medications: () => (
      <MedicationsCard
        value={state.medications}
        onChange={state.setMedicationsDirty}
        {...collapseProps('medications')}
      />
    ),
    symptoms: () => (
      <SymptomsCard
        value={state.symptomsJson}
        onChange={state.setSymptomsJsonDirty}
        {...collapseProps('symptoms')}
      />
    ),
    trackers: () => (
      <TrackersCard
        alcoholUnits={state.alcoholUnits}
        onAlcoholUnitsChange={state.setAlcoholUnitsDirty}
        caffeineServings={state.caffeineServings}
        onCaffeineServingsChange={state.setCaffeineServingsDirty}
        sick={state.sick}
        onSickChange={state.setSickDirty}
        hotShower={state.hotShower}
        onHotShowerChange={state.setHotShowerDirty}
        date={date}
        {...collapseProps('trackers')}
      />
    ),
    notes: () => (
      <NotesCard
        value={state.notes}
        onChange={state.setNotesValue}
        onEditStart={state.markDirty}
        onBlur={state.handleBlur}
        registerDraftFlush={state.registerNotesDraftFlush}
        {...collapseProps('notes')}
      />
    ),
  }
}
