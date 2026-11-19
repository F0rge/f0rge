"use client";

import { Email, Group, UserRole } from "@carbon/icons-react";
import { ProgressBar, SkeletonText } from "@carbon/react";
import { availableStaffPlaces, type StaffCapacity } from "@/lib/staff-administration";
import styles from "./staff-metrics.module.css";

export function StaffMetrics({ capacity }: { capacity: StaffCapacity | undefined }) {
  const available = capacity && availableStaffPlaces(capacity);
  return (
    <dl aria-label="Staff access summary" className={styles.metrics}>
      <div className={styles.metric}>
        <dt><Group size={16} aria-hidden="true" /> Active members</dt>
        <dd>{capacity ? capacity.active_count : <SkeletonText width="2rem" />}</dd>
      </div>
      <div className={styles.metric}>
        <dt><Email size={16} aria-hidden="true" /> Pending invitations</dt>
        <dd>{capacity ? capacity.pending_count : <SkeletonText width="2rem" />}</dd>
      </div>
      <div className={styles.metric}>
        <dt><UserRole size={16} aria-hidden="true" /> Available staff places</dt>
        <dd>
          {capacity ? <>
            <span>{available} <small>of {capacity.max_members}</small></span>
            <ProgressBar label="Available staff places" hideLabel size="small" value={available} max={capacity.max_members} />
          </> : <SkeletonText width="2rem" />}
        </dd>
        {capacity && capacity.member_count > capacity.active_count && (
          <dd className={styles.capacityNote}>Clerk memberships still occupy places when Firstout access is disabled.</dd>
        )}
      </div>
    </dl>
  );
}
