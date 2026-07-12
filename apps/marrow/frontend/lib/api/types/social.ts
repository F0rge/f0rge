export interface PublicUserCard {
  handle: string
  display_name: string | null
  avatar_default_index: number
}

export interface HandleAvailableResponse {
  available: boolean
}
