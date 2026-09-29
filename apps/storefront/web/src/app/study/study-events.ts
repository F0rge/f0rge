export const STUDY_EVENT_NAME = "storefront:study";
export const SOLA_STUDY_ID = "sola-chair-editorial";

export type StudyProgressMilestone = 25 | 50 | 75 | 100;
export type StudyEventDetail =
  | { type: "entry"; studyId: typeof SOLA_STUDY_ID }
  | { type: "progress"; studyId: typeof SOLA_STUDY_ID; milestone: StudyProgressMilestone }
  | { type: "finish"; studyId: typeof SOLA_STUDY_ID };

export type StudyEventListener = (event: StudyEventDetail) => void;

/** Subscribe to semantic study events without selecting an analytics provider. */
export function subscribeToStudyEvents(listener: StudyEventListener): () => void {
  if (typeof window === "undefined") return () => undefined;

  const handle = (event: Event) => {
    listener((event as CustomEvent<StudyEventDetail>).detail);
  };
  window.addEventListener(STUDY_EVENT_NAME, handle);
  return () => window.removeEventListener(STUDY_EVENT_NAME, handle);
}

export function publishStudyEvent(event: StudyEventDetail): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<StudyEventDetail>(STUDY_EVENT_NAME, { detail: event }));
}
