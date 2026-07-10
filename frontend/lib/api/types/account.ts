export interface Account {
  user_id: string
  email: string
  display_name: string | null
  avatar_default_index: number
  has_custom_avatar: boolean
  created_at: string
}

export interface AccountUpdate {
  display_name: string | null
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface DeleteAccountRequest {
  password: string
}
