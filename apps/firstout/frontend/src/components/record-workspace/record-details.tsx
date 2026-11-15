import type { ReactNode } from "react";
import styles from "./record-workspace.module.css";

export function RecordDetails({ children }: { children: ReactNode }) {
  return <dl className={styles.details}>{children}</dl>;
}
export function RecordDetail({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {children === null || children === undefined || children === ""
          ? "—"
          : children}
      </dd>
    </div>
  );
}
