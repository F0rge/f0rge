'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Cloud, Cpu, Download, Heart, Key, Lock, RefreshCw, Sparkles, Upload, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import {
  useTriggerWeatherFetch,
  useUserSettings,
  useUpdateLLMSettings,
  useUpdateEmbeddingSettings,
  useTestLLMConnection,
  useTestEmbeddingConnection,
} from '@/lib/api/hooks'
import { apiGetRaw, apiPostForm } from '@/lib/api/client'

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

const BUTTON_CLASS =
  'flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-all hover:bg-muted disabled:opacity-50'

export default function SettingsPage() {
  const weatherFetch = useTriggerWeatherFetch()
  const [uploading, setUploading] = useState(false)
  const [exporting, setExporting] = useState(false)

  // AI settings state
  const userSettings = useUserSettings()
  const updateLLM = useUpdateLLMSettings()
  const updateEmbedding = useUpdateEmbeddingSettings()
  const testLLM = useTestLLMConnection()
  const testEmbedding = useTestEmbeddingConnection()

  const [llmApiKey, setLlmApiKey] = useState('')
  const [llmModel, setLlmModel] = useState('')
  const [llmCustomModel, setLlmCustomModel] = useState('')
  const [llmUseCustom, setLlmUseCustom] = useState(false)

  const [embeddingApiKey, setEmbeddingApiKey] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState('')
  const [embeddingCustomModel, setEmbeddingCustomModel] = useState('')
  const [embeddingUseCustom, setEmbeddingUseCustom] = useState(false)

  const handleSaveLLM = async () => {
    const payload: { llm_api_key?: string; llm_model?: string } = {}
    if (llmApiKey) payload.llm_api_key = llmApiKey
    const model = llmUseCustom ? llmCustomModel.trim() : llmModel
    if (model) payload.llm_model = model
    try {
      await updateLLM.mutateAsync(payload)
      setLlmApiKey('')
      toast.success('AI settings saved')
    } catch {
      toast.error('Failed to save AI settings')
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
    } catch {
      toast.error('AI connection test failed')
    }
  }

  const handleSaveEmbedding = async () => {
    const payload: { embedding_api_key?: string; embedding_model?: string } = {}
    if (embeddingApiKey) payload.embedding_api_key = embeddingApiKey
    const model = embeddingUseCustom ? embeddingCustomModel.trim() : embeddingModel
    if (model) payload.embedding_model = model
    try {
      await updateEmbedding.mutateAsync(payload)
      setEmbeddingApiKey('')
      toast.success('Embedding settings saved')
    } catch {
      toast.error('Failed to save embedding settings')
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
    } catch {
      toast.error('Embedding connection test failed')
    }
  }

  const handleWeatherFetch = async () => {
    try {
      await weatherFetch.mutateAsync()
      toast.success('Weather data fetched')
    } catch {
      toast.error('Weather fetch failed — check API key')
    }
  }

  const handleExportCsv = async () => {
    setExporting(true)
    try {
      const res = await apiGetRaw('/export/feature-matrix.csv')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const disposition = res.headers.get('Content-Disposition')
      const match = disposition?.match(/filename="?([^"]+)"?/)
      a.download = match?.[1] ?? 'feature_matrix.csv'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('CSV export failed:', err)
      toast.error('Export failed')
    } finally {
      setExporting(false)
    }
  }

  const handleXmlUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await apiPostForm('/health-metrics/import', formData)
      toast.success('Health data imported')
    } catch {
      toast.error('Import failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-6">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/checkin" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-5" />
        </Link>
        <h1 className="text-xl font-bold">Settings</h1>
      </div>

      <div className="space-y-6">
        {/* Weather */}
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Cloud className="size-5 text-blue-500" />
            <h2 className="font-semibold">Weather Data</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Fetches hourly from OpenWeatherMap for Luxembourg. Barometric pressure drops correlate with symptom flares.
          </p>
          <button
            type="button"
            onClick={handleWeatherFetch}
            disabled={weatherFetch.isPending}
            className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-all hover:bg-muted disabled:opacity-50"
          >
            <RefreshCw className={`size-4 ${weatherFetch.isPending ? 'animate-spin' : ''}`} />
            Fetch Now
          </button>
        </div>

        {/* AI Provider */}
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-purple-500" />
            <h2 className="font-semibold">AI Provider</h2>
          </div>

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
              {userSettings.data?.has_llm_api_key
                ? 'Key set (re-enter to change)'
                : 'No key set'}
            </p>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Model</label>
            {!llmUseCustom && (
              <select
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">— use current setting ({userSettings.data?.llm_model ?? 'default'}) —</option>
                {LLM_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            )}
            {llmUseCustom && (
              <input
                type="text"
                placeholder="e.g. mistralai/mistral-7b-instruct"
                value={llmCustomModel}
                onChange={(e) => setLlmCustomModel(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              />
            )}
            <label className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
              <input
                type="checkbox"
                checked={llmUseCustom}
                onChange={(e) => setLlmUseCustom(e.target.checked)}
                className="rounded"
              />
              Use custom model name
            </label>
          </div>

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
        </div>

        {/* Embedding Provider */}
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Cpu className="size-5 text-indigo-500" />
            <h2 className="font-semibold">Embedding Provider</h2>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Provider</label>
            <p className="text-sm">OpenRouter</p>
            <p className="text-xs text-muted-foreground">
              Used for future RAG / semantic search. Not currently populated.
            </p>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
              <Key className="size-3" />
              API Key
            </label>
            <input
              type="password"
              placeholder="sk-or-..."
              value={embeddingApiKey}
              onChange={(e) => setEmbeddingApiKey(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            />
            <p className="text-xs text-muted-foreground">
              {userSettings.data?.has_embedding_api_key
                ? 'Key set (re-enter to change)'
                : 'No key set'}
            </p>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Model</label>
            {!embeddingUseCustom && (
              <select
                value={embeddingModel}
                onChange={(e) => setEmbeddingModel(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">— use current setting ({userSettings.data?.embedding_model ?? 'default'}) —</option>
                {EMBEDDING_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            )}
            {embeddingUseCustom && (
              <input
                type="text"
                placeholder="e.g. cohere/embed-v4"
                value={embeddingCustomModel}
                onChange={(e) => setEmbeddingCustomModel(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              />
            )}
            <label className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
              <input
                type="checkbox"
                checked={embeddingUseCustom}
                onChange={(e) => setEmbeddingUseCustom(e.target.checked)}
                className="rounded"
              />
              Use custom model name
            </label>
          </div>

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
        </div>

        {/* External Access Token */}
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Lock className="size-5 text-muted-foreground" />
            <h2 className="font-semibold">External Access Token</h2>
          </div>
          <input
            type="text"
            readOnly
            value={
              userSettings.data?.has_external_api_token
                ? 'Token exists (hidden)'
                : 'No token generated'
            }
            className="w-full rounded-lg border border-border bg-muted px-3 py-2 text-sm text-muted-foreground"
          />
          <p className="text-xs text-muted-foreground">
            For external integrations (e.g., shortcut automations). Not active in this release.
          </p>
          <button
            type="button"
            disabled
            title="Coming soon (#49)"
            className={BUTTON_CLASS}
          >
            Regenerate
          </button>
        </div>

        {/* Apple Health */}
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Heart className="size-5 text-red-500" />
            <h2 className="font-semibold">Apple Health</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Auto-syncs via Health Auto Export iOS app. Use this upload for manual XML imports as a backup.
          </p>
          <label
            className={`flex min-h-[44px] w-full cursor-pointer items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-all hover:bg-muted ${uploading ? 'opacity-50' : ''}`}
          >
            <Upload className="size-4" />
            {uploading ? 'Importing...' : 'Upload Apple Health XML'}
            <input
              type="file"
              accept=".xml,.json"
              onChange={handleXmlUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>
        </div>

        {/* Export Data */}
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Download className="size-5 text-green-500" />
            <h2 className="font-semibold">Export Data</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Download all check-in and health metric data as a CSV feature matrix for analysis.
          </p>
          <button
            type="button"
            onClick={handleExportCsv}
            disabled={exporting}
            className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-all hover:bg-muted disabled:opacity-50"
          >
            <Download className={`size-4 ${exporting ? 'animate-pulse' : ''}`} />
            {exporting ? 'Exporting...' : 'Download CSV'}
          </button>
        </div>

        {/* Info */}
        <div className="rounded-xl border border-border p-4 space-y-2">
          <h2 className="font-semibold">Data Sources</h2>
          <ul className="space-y-1 text-sm text-muted-foreground">
            <li>Weather: auto-fetches hourly (background)</li>
            <li>Apple Health: auto-syncs via Health Auto Export app</li>
            <li>Check-in: manual daily entry</li>
            <li>Vault sync: every 15 minutes to Obsidian</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
