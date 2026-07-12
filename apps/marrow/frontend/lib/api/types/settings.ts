export type TaggedMealMode = 'approve' | 'auto'

export interface UserSettings {
  llm_provider: string
  llm_model: string | null
  embedding_provider: string
  embedding_model: string | null
  has_api_key: boolean
  has_external_api_token: boolean
  onboarding_completed: boolean
  tagged_meal_mode: TaggedMealMode
}

export interface LLMSettingsUpdate {
  llm_provider?: string
  llm_api_key?: string
  llm_model?: string
}

export interface EmbeddingSettingsUpdate {
  embedding_provider?: string
  embedding_model?: string | null
}

export interface TaggedMealModeUpdate {
  tagged_meal_mode: TaggedMealMode
}

export interface TestConnectionResponse {
  ok: boolean
  detail?: string | null
}

export interface ExternalTokenResponse {
  token: string // Plaintext bearer token. Exposed exactly once.
}
