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

export const CARD_COL_SPAN: Record<CardId, string> = {
  food: 'col-span-12',
  wellbeing: 'col-span-12 lg:col-span-4',
  gut: 'col-span-12 lg:col-span-4',
  supplements: 'col-span-12 lg:col-span-4',
  medications: 'col-span-12 lg:col-span-6',
  symptoms: 'col-span-12 lg:col-span-6',
  trackers: 'col-span-12 lg:col-span-6',
  notes: 'col-span-12 lg:col-span-6',
}

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
        neuro={state.neuro}
        onNeuroChange={state.setNeuroDirty}
        fivePoint={state.fivePoint}
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
        jointPain={state.jointPain}
        onJointPainChange={state.setJointPainDirty}
      />
    ),
    supplements: () => (
      <SupplementsCard
        value={state.supplements}
        onChange={state.handleSupplementChange}
        onTouched={state.handleSupplementTouched}
      />
    ),
    medications: () => (
      <MedicationsCard
        value={state.medications}
        onChange={state.setMedicationsDirty}
      />
    ),
    symptoms: () => (
      <SymptomsCard
        value={state.symptomsJson}
        onChange={state.setSymptomsJsonDirty}
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
      />
    ),
    notes: () => (
      <NotesCard
        value={state.notes}
        onChange={state.setNotesValue}
        onEditStart={state.markDirty}
        onBlur={state.handleBlur}
        registerDraftFlush={state.registerNotesDraftFlush}
      />
    ),
  }
}
