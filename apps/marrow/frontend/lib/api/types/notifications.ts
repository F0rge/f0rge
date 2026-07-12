export interface NotificationItem {
  id: string
  type: string
  payload: Record<string, unknown>
  read_at: string | null
  created_at: string
}

export interface UnreadCountResponse {
  count: number
}

export interface MarkReadRequest {
  ids?: string[]
  all?: boolean
}
