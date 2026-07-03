'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Cpu, RefreshCw } from 'lucide-react'
import {
  useUserSettings,
  useUpdateEmbeddingSettings,
  useTestEmbeddingConnection,
} from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'
import { SettingsCard } from './settings-card'
import { ModelPicker } from './model-picker'
import { BUTTON_CLASS } from './constants'

const EMBEDDING_MODELS = [
  { value: 'openai/text-embedding-3-small', label: 'text-embedding-3-small (default)' },
  { value: 'openai/text-embedding-3-large', label: 'text-embedding-3-large' },
  { value: 'google/gemini-embedding-2-preview', label: 'Gemini Embedding 2 Preview' },
  { value: 'baai/bge-m3', label: 'BGE-M3' },
] as const

export function EmbeddingProviderSection() {
  const userSettings = useUserSettings()
  const updateEmbedding = useUpdateEmbeddingSettings()
  const testEmbedding = useTestEmbeddingConnection()

  const [embeddingModel, setEmbeddingModel] = useState('')
  const [embeddingCustomModel, setEmbeddingCustomModel] = useState('')
  const [embeddingUseCustom, setEmbeddingUseCustom] = useState(false)

  const handleSaveEmbedding = async () => {
    const payload: { embedding_model?: string } = {}
    const model = embeddingUseCustom ? embeddingCustomModel.trim() : embeddingModel
    if (model) payload.embedding_model = model
    try {
      await updateEmbedding.mutateAsync(payload)
      toast.success('Embedding settings saved')
    } catch (err) {
      handleMutationError(err, 'Failed to save embedding settings')
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
    <SettingsCard icon={Cpu} iconClassName="text-indigo-500" title="Embedding Provider">
      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">Provider</label>
        <p className="text-sm">OpenRouter</p>
        <p className="text-xs text-muted-foreground">
          Used for future RAG / semantic search. Not currently populated. Uses the API
          key configured above.
        </p>
      </div>

      <ModelPicker
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

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSaveEmbedding}
          disabled={updateEmbedding.isPending}
          className={BUTTON_CLASS}
        >
          {updateEmbedding.isPending ? 'Saving...' : 'Save'}
        </button>
        <button
          type="button"
          onClick={handleTestEmbedding}
          disabled={testEmbedding.isPending}
          className={BUTTON_CLASS}
        >
          <RefreshCw className={`size-4 ${testEmbedding.isPending ? 'animate-spin' : ''}`} />
          {testEmbedding.isPending ? 'Testing...' : 'Test connection'}
        </button>
      </div>
    </SettingsCard>
  )
}
