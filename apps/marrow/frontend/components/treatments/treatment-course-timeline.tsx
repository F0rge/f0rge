'use client'

import type { Treatment } from '@/lib/api/types'
import {
  formatDisplayDate,
  Timeline,
  TimelineContent,
  TimelineDate,
  TimelineIndicator,
  TimelineItem,
  TimelineSeparator,
  TimelineTitle,
} from '@f0rge/ui'
import { getEndReasonLabel } from './end-reason'

interface TreatmentCourseTimelineProps {
  treatment: Treatment
}

export function TreatmentCourseTimeline({ treatment }: TreatmentCourseTimelineProps) {
  const activeStep = treatment.end_date ? 2 : 1

  return (
    <Timeline value={activeStep} className="w-full py-1">
      <TimelineItem step={1}>
        <TimelineIndicator />
        <TimelineSeparator />
        <TimelineContent>
          <TimelineDate dateTime={treatment.start_date}>
            {formatDisplayDate(treatment.start_date)}
          </TimelineDate>
          <TimelineTitle>Started</TimelineTitle>
          {treatment.dose && (
            <p className="text-xs text-muted-foreground">{treatment.dose}</p>
          )}
        </TimelineContent>
      </TimelineItem>
      <TimelineItem step={2}>
        <TimelineIndicator />
        <TimelineContent>
          {treatment.end_date ? (
            <>
              <TimelineDate dateTime={treatment.end_date}>
                {formatDisplayDate(treatment.end_date)}
              </TimelineDate>
              <TimelineTitle>
                {treatment.end_reason === 'completed'
                  ? 'Completed'
                  : treatment.end_reason
                    ? `Ended · ${getEndReasonLabel(treatment.end_reason)}`
                    : 'Ended'}
              </TimelineTitle>
              {treatment.end_note && (
                <p className="text-xs text-muted-foreground">{treatment.end_note}</p>
              )}
            </>
          ) : (
            <>
              <TimelineTitle>Ongoing</TimelineTitle>
              <p className="text-xs text-muted-foreground">No end date recorded</p>
            </>
          )}
        </TimelineContent>
      </TimelineItem>
    </Timeline>
  )
}
