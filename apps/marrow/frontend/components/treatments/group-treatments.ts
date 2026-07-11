import type { Treatment } from '@/lib/api/types'

export interface TreatmentSection {
  label: string | null // null = ungrouped ("Individual")
  treatments: Treatment[]
}

/** Buckets treatments by group_name, preserving backend order. Sections are
 * ordered by first member appearance; ungrouped items form a trailing
 * "Individual" section. Returns a single unlabeled section when no
 * treatment has a group — shared by the list view and the timeline so both
 * read the same sectioning. */
export function groupTreatments(treatments: Treatment[]): TreatmentSection[] {
  const hasAnyGroup = treatments.some((t) => t.group_name)
  if (!hasAnyGroup) {
    return [{ label: null, treatments }]
  }

  const sections: TreatmentSection[] = []
  const indexByLabel = new Map<string, number>()
  const ungrouped: Treatment[] = []

  for (const t of treatments) {
    if (!t.group_name) {
      ungrouped.push(t)
      continue
    }
    const existingIndex = indexByLabel.get(t.group_name)
    if (existingIndex === undefined) {
      indexByLabel.set(t.group_name, sections.length)
      sections.push({ label: t.group_name, treatments: [t] })
    } else {
      sections[existingIndex].treatments.push(t)
    }
  }

  if (ungrouped.length > 0) {
    sections.push({ label: 'Individual', treatments: ungrouped })
  }
  return sections
}
