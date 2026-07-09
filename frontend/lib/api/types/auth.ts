export interface AuthUser {
  authenticated: boolean
  email?: string
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface SignupCredentials {
  email: string
  password: string
}
