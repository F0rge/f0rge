export interface Account {
  user_id: string
  email: string
  display_name: string | null
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
