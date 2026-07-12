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

export type GroupMemberRole = 'owner' | 'member'
export type GroupMemberStatus = 'invited' | 'joined'

export interface GroupListItem {
  id: string
  name: string
  owner: PublicUserCard
  member_count: number
  my_status: GroupMemberStatus
  my_role: GroupMemberRole
}

export interface GroupMember {
  handle: string
  display_name: string | null
  avatar_default_index: number
  role: GroupMemberRole
  status: GroupMemberStatus
  joined_at: string | null
}

export interface GroupDetail {
  id: string
  name: string
  owner: PublicUserCard
  my_role: GroupMemberRole
  my_status: GroupMemberStatus
  members: GroupMember[]
}
