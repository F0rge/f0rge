export interface PublicUserCard {
  handle: string
  display_name: string | null
  avatar_default_index: number
}

export interface HandleAvailableResponse {
  available: boolean
}

export interface ConnectionItem {
  id: string
  user: PublicUserCard
  since?: string | null
  created_at?: string | null
}

export interface ConnectionListResponse {
  accepted: ConnectionItem[]
  pending_incoming: ConnectionItem[]
  pending_outgoing: ConnectionItem[]
}
