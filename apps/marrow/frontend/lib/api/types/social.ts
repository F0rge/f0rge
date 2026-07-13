export interface PublicUserCard {
  handle: string
  display_name: string | null
  avatar_default_index: number
}

export type ConnectionStatus = 'none' | 'pending_outgoing' | 'pending_incoming' | 'connected'

export interface UserSearchItem extends PublicUserCard {
  connection_status: ConnectionStatus
}

export interface UserSearchResponse {
  users: UserSearchItem[]
}

export interface HandleAvailableResponse {
  available: boolean
  reason?: 'available' | 'taken' | 'invalid' | null
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

export interface GroupListResponse {
  groups: GroupListItem[]
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

export type MealTagStatus =
  | 'pending_analysis'
  | 'pending_approval'
  | 'delivered'
  | 'declined'
  | 'cancelled'

export interface IncomingMealTag {
  id: string
  tagger: PublicUserCard
  source_dish_name: string | null
  source_label: string | null
  source_date: string
  created_at: string
}

export interface OutgoingMealTag {
  id: string
  tagged_user: PublicUserCard
  status: MealTagStatus
  source_dish_name: string | null
  source_label: string | null
  source_date: string
  created_at: string
  resolved_at: string | null
}

export interface MealTagsResponse {
  incoming_pending: IncomingMealTag[]
  outgoing: OutgoingMealTag[]
}
