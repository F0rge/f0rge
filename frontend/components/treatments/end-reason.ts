/** Human labels for `Treatment.end_reason`, mirroring the backend's
 * `TREATMENT_END_REASONS` (app/schemas/treatment.py). Single source of
 * truth for the discontinue-dialog select options and the ended-treatment
 * badge on the card. */
export const END_REASON_OPTIONS = [
  { value: 'completed', label: 'Completed course' },
  { value: 'side_effects', label: 'Side effects' },
  { value: 'ineffective', label: 'Ineffective' },
  { value: 'doctor_advised', label: 'Doctor advised' },
  { value: 'switched', label: 'Switched treatment' },
  { value: 'other', label: 'Other' },
] as const

const END_REASON_LABELS: Record<string, string> = Object.fromEntries(
  END_REASON_OPTIONS.map((o) => [o.value, o.label]),
)

export function getEndReasonLabel(reason: string): string {
  return END_REASON_LABELS[reason] ?? reason
}
