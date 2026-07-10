'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Key, RefreshCw, Sparkles } from 'lucide-react'
import {
  useUserSettings,
  useUpdateLLMSettings,
  useUpdateEmbeddingSettings,
  useTestLLMConnection,
  useTestEmbeddingConnection,
} from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'
import { SettingsCard } from './settings-card'
import { ModelPicker } from './model-picker'
import { BUTTON_CLASS } from './constants'

const LLM_MODELS = [
  { value: 'google/gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
  { value: 'anthropic/claude-haiku-4-5', label: 'Claude Haiku 4.5' },
  { value: 'anthropic/claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { value: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
] as const

const EMBEDDING_MODELS = [
  { value: 'openai/text-embedding-3-small', label: 'text-embedding-3-small (default)' },
  { value: 'openai/text-embedding-3-large', label: 'text-embedding-3-large' },
  { value: 'google/gemini-embedding-2-preview', label: 'Gemini Embedding 2 Preview' },
  { value: 'baai/bge-m3', label: 'BGE-M3' },
] as const

export function AiSettingsSection() {
  const userSettings = useUserSettings()
  const updateLLM = useUpdateLLMSettings()
  const updateEmbedding = useUpdateEmbeddingSettings()
  const testLLM = useTestLLMConnection()
  const testEmbedding = useTestEmbeddingConnection()

  const [llmApiKey, setLlmApiKey] = useState('')
  const [llmModel, setLlmModel] = useState('')
  const [llmCustomModel, setLlmCustomModel] = useState('')
  const [llmUseCustom, setLlmUseCustom] = useState(false)
  const [embeddingModel, setEmbeddingModel] = useState('')
  const [embeddingCustomModel, setEmbeddingCustomModel] = useState('')
  const [embeddingUseCustom, setEmbeddingUseCustom] = useState(false)

  const saving = updateLLM.isPending || updateEmbedding.isPending

  const handleSave = async () => {
    const llmPayload: { llm_api_key?: string; llm_model?: string } = {}
    if (llmApiKey) llmPayload.llm_api_key = llmApiKey
    const analysisModel = llmUseCustom ? llmCustomModel.trim() : llmModel
    if (analysisModel) llmPayload.llm_model = analysisModel

    const embeddingPayload: { embedding_model?: string } = {}
    const embedModel = embeddingUseCustom ? embeddingCustomModel.trim() : embeddingModel
    if (embedModel) embeddingPayload.embedding_model = embedModel

    if (!llmApiKey && !analysisModel && !embedModel) {
      toast.error('Nothing to save')
      return
    }

    const previous = userSettings.data
    let embeddingUpdated = false

    try {
      if (embedModel) {
        await updateEmbedding.mutateAsync(embeddingPayload)
        embeddingUpdated = true
      }
      if (llmApiKey || analysisModel) {
        await updateLLM.mutateAsync(llmPayload)
      }
      setLlmApiKey('')
      toast.success('AI settings saved')
    } catch (err) {
      if (embeddingUpdated && previous) {
        try {
          await updateEmbedding.mutateAsync({
            embedding_model: previous.embedding_model,
          })
        } catch {
          // Best-effort rollback; original error is still reported.
        }
      }
      handleMutationError(err, 'Failed to save AI settings')
    }
  }

  const handleTestLLM = async () => {
    try {
      const result = await testLLM.mutateAsync()
      if (result.ok) {
        toast.success('Analysis connection works')
      } else {
        toast.error(`Analysis connection failed: ${result.detail ?? 'unknown error'}`)
      }
    } catch (err) {
      handleMutationError(err, 'Analysis connection test failed')
    }
  }

  const handleTestEmbedding = async () => {
    try {
      const result = await testEmbedding.mutateAsync()
      if (result.ok) {
        toast.success('Embedding connection works')
      } else {
        toast.error(`Embedding connection failed: ${result.detail ?? 'unknown error'}`)
      }
    } catch (err) {
      handleMutationError(err, 'Embedding connection test failed')
    }
  }

  return (
    <SettingsCard icon={Sparkles} iconClassName="text-purple-500" title="AI & Embeddings">
      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">Provider</label>
        <p className="text-sm">OpenRouter</p>
      </div>

      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
          <Key className="size-3" />
          API Key
        </label>
        <input
          type="password"
          placeholder="sk-or-..."
          value={llmApiKey}
          onChange={(e) => setLlmApiKey(e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
        />
        <p className="text-xs text-muted-foreground">
          Used for food-photo analysis and semantic search embeddings.{' '}
          {userSettings.data?.has_api_key
            ? 'Key set (re-enter to change)'
            : 'No key set'}
        </p>
      </div>

      <ModelPicker
        label="Analysis model"
        options={LLM_MODELS}
        currentModel={userSettings.data?.llm_model}
        model={llmModel}
        onModelChange={setLlmModel}
        customModel={llmCustomModel}
        onCustomModelChange={setLlmCustomModel}
        useCustom={llmUseCustom}
        onUseCustomChange={setLlmUseCustom}
        customPlaceholder="e.g. mistralai/mistral-7b-instruct"
      />

      <ModelPicker
        label="Embedding model"
        options={EMBEDDING_MODELS}
        currentModel={userSettings.data?.embedding_model}
        model={embeddingModel}
        onModelChange={setEmbeddingModel}
        customModel={embeddingCustomModel}
        onCustomModelChange={setEmbeddingCustomModel}
        useCustom={embeddingUseCustom}
        onUseCustomChange={setEmbeddingUseCustom}
        customPlaceholder="e.g. cohere/embed-v4"
      />

      <p className="text-xs text-muted-foreground">
        Embeddings power future RAG / semantic search. The pipeline is not fully populated yet.
      </p>

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={handleSave} disabled={saving} className={BUTTON_CLASS}>
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button
          type="button"
          onClick={handleTestLLM}
          disabled={testLLM.isPending}
          className={BUTTON_CLASS}
        >
          <RefreshCw className={`size-4 ${testLLM.isPending ? 'animate-spin' : ''}`} />
          {testLLM.isPending ? 'Testing...' : 'Test analysis'}
        </button>
        <button
          type="button"
          onClick={handleTestEmbedding}
          disabled={testEmbedding.isPending}
          className={BUTTON_CLASS}
        >
          <RefreshCw className={`size-4 ${testEmbedding.isPending ? 'animate-spin' : ''}`} />
          {testEmbedding.isPending ? 'Testing...' : 'Test embeddings'}
        </button>
      </div>
    </SettingsCard>
  )
}
