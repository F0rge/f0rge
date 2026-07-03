'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Key, RefreshCw, Sparkles } from 'lucide-react'
import {
  useUserSettings,
  useUpdateLLMSettings,
  useTestLLMConnection,
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

export function AiProviderSection() {
  const userSettings = useUserSettings()
  const updateLLM = useUpdateLLMSettings()
  const testLLM = useTestLLMConnection()

  const [llmApiKey, setLlmApiKey] = useState('')
  const [llmModel, setLlmModel] = useState('')
  const [llmCustomModel, setLlmCustomModel] = useState('')
  const [llmUseCustom, setLlmUseCustom] = useState(false)

  const handleSaveLLM = async () => {
    const payload: { llm_api_key?: string; llm_model?: string } = {}
    if (llmApiKey) payload.llm_api_key = llmApiKey
    const model = llmUseCustom ? llmCustomModel.trim() : llmModel
    if (model) payload.llm_model = model
    try {
      await updateLLM.mutateAsync(payload)
      setLlmApiKey('')
      toast.success('AI settings saved')
    } catch (err) {
      handleMutationError(err, 'Failed to save AI settings')
    }
  }

  const handleTestLLM = async () => {
    try {
      const result = await testLLM.mutateAsync()
      if (result.ok) {
        toast.success('AI connection works')
      } else {
        toast.error(`AI connection failed: ${result.detail ?? 'unknown error'}`)
      }
    } catch (err) {
      handleMutationError(err, 'AI connection test failed')
    }
  }

  return (
    <SettingsCard icon={Sparkles} iconClassName="text-purple-500" title="AI Provider">
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
          Used for both AI analysis and embeddings.{' '}
          {userSettings.data?.has_api_key
            ? 'Key set (re-enter to change)'
            : 'No key set'}
        </p>
      </div>

      <ModelPicker
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

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSaveLLM}
          disabled={updateLLM.isPending}
          className={BUTTON_CLASS}
        >
          {updateLLM.isPending ? 'Saving...' : 'Save'}
        </button>
        <button
          type="button"
          onClick={handleTestLLM}
          disabled={testLLM.isPending}
          className={BUTTON_CLASS}
        >
          <RefreshCw className={`size-4 ${testLLM.isPending ? 'animate-spin' : ''}`} />
          {testLLM.isPending ? 'Testing...' : 'Test connection'}
        </button>
      </div>
    </SettingsCard>
  )
}
