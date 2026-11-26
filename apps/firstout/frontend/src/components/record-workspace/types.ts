import type { ReactNode } from "react";
import type {
  WorkspaceAction,
  WorkspaceQuery,
  WorkspaceResource,
} from "@/lib/record-workspace-api";

export interface WorkspaceOption {
  value: string;
  label: string;
}
export interface WorkspaceField {
  key: string;
  label: string;
  type: "text" | "enum" | "number" | "date" | "boolean";
  options?: readonly WorkspaceOption[];
  nullable?: boolean;
  quick?: boolean;
  allLabel?: string;
}
export interface WorkspaceColumn<T> {
  key: string;
  label: string;
  render: (item: T) => ReactNode;
  numeric?: boolean;
  sortable?: boolean;
}
export interface WorkspaceActionDefinition {
  key: WorkspaceAction;
  label: string;
  danger?: boolean;
}
export interface RecordWorkspaceAdapter<T extends { id: string }> {
  resource: WorkspaceResource;
  title: string;
  singular: string;
  plural?: string;
  breadcrumb: string;
  description: string;
  columns: readonly WorkspaceColumn<T>[];
  filters: readonly WorkspaceField[];
  bulkFields?: readonly WorkspaceField[];
  actions?: readonly WorkspaceActionDefinition[];
  lifecycle?: { activeLabel: string; archivedLabel: string };
  defaultSort?: string;
  getTitle: (item: T) => string;
  renderAvatar?: (item: T) => ReactNode;
  getSubtitle?: (item: T) => ReactNode;
  canEdit?: (item: T) => boolean;
}
export interface RecordWorkspaceContext {
  reload: () => void;
  archived: boolean;
}
export interface RecordWorkspaceProps<T extends { id: string }> {
  adapter: RecordWorkspaceAdapter<T>;
  refreshKey?: number;
  onCreate?: () => void;
  createLabel?: string;
  onEdit?: (item: T) => void;
  modalDetails?: boolean;
  listTitle?: string;
  /** Render an action above the inline inspector's scrolling content. */
  renderDetailsHeader?: (item: T) => ReactNode;
  /** Inspector content. Not used when `openRecord` is set. */
  renderDetails?: (item: T, context: RecordWorkspaceContext) => ReactNode;
  /**
   * No-details mode: the list is full width and the page shows the record elsewhere
   * (the catalogue docks the shell SKU panel). Without it, nothing changes.
   */
  openRecord?: {
    /** The row shown with the standard active style, or none. */
    activeId: string | null;
    /** A row was opened; `pageItems` is the current page of rows, in order. */
    onOpen: (item: T, pageItems: readonly T[]) => void;
    /** The current page of rows changed (paging, sorting, filters, reload). */
    onPageItems?: (pageItems: readonly T[]) => void;
  };
  loadingDetails?: { tabs: readonly string[]; fields: readonly string[] };
  headerActions?: ReactNode;
  /** Shown between the header and the filters, e.g. KPI tiles. */
  summary?: ReactNode;
  renderSelectionActions?: (selection: { ids: string[]; query: WorkspaceQuery }) => ReactNode;
  onExport?: (query: WorkspaceQuery) => void | Promise<void>;
  children?: ReactNode;
}
