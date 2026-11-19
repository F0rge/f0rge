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
  renderDetails: (item: T, context: RecordWorkspaceContext) => ReactNode;
  loadingDetails?: { tabs: readonly string[]; fields: readonly string[] };
  headerActions?: ReactNode;
  renderSelectionActions?: (selection: { ids: string[]; query: WorkspaceQuery }) => ReactNode;
  onExport?: (query: WorkspaceQuery) => void | Promise<void>;
  children?: ReactNode;
}
