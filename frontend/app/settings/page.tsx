'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { ArrowLeft, Cloud, Copy, Cpu, Download, Heart, Key, Lock, RefreshCw, Sparkles, Trash2, Upload } from 'lucide-react'
import Link from 'next/link'
import {
  useTriggerWeatherFetch,
  useUserSettings,
  useUpdateLLMSettings,
  useUpdateEmbeddingSettings,
  useTestLLMConnection,
  useTestEmbeddingConnection,
  useRegenerateExternalToken,
  useRevokeExternalToken,
} from '@/lib/api/hooks'
import { apiGetRaw, apiPostForm, handleMutationError } from '@/lib/api/client'

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

  const [embeddingModel, setEmbeddingModel] = useState('')
  const [embeddingCustomModel, setEmbeddingCustomModel] = useState('')
  const [embeddingUseCustom, setEmbeddingUseCustom] = useState(false)

  // External Access Token state
  const [plaintextToken, setPlaintextToken] = useState<string | null>(null)
  const regenerate = useRegenerateExternalToken()
  const revoke = useRevokeExternalToken()

  const handleRegenerate = async () => {
    try {
      const result = await regenerate.mutateAsync()
      setPlaintextToken(result.token)
      toast.success('Token regenerated — copy it now; it will not be shown again')
    } catch (err) {
      handleMutationError(err, 'Failed to regenerate token')
    }
  }

  const handleRevoke = async () => {
    try {
      await revoke.mutateAsync()
      setPlaintextToken(null)
      toast.success('Token revoked')
    } catch (err) {
      handleMutationError(err, 'Failed to revoke token')
    }
  }

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('Copied to clipboard')
    } catch (err) {
      handleMutationError(err, 'Copy failed — select and copy manually')
    }
  }

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

  const handleWeatherFetch = async () => {
    try {
      await weatherFetch.mutateAsync()
      toast.success('Weather data fetched')
    } catch (err) {
      handleMutationError(err, 'Weather fetch failed — check API key')
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
    } catch (err) {
      handleMutationError(err, 'Import failed')
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
              Used for both AI analysis and embeddings.{' '}
              {userSettings.data?.has_api_key
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
              Used for future RAG / semantic search. Not currently populated. Uses the API
              key configured above.
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
          <p className="text-xs text-muted-foreground">
            For querying your health data from Claude Code or Claude Desktop via MCP.
          </p>

          {plaintextToken ? (
            <div className="space-y-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={plaintextToken}
                  className="w-full rounded-lg border border-border bg-muted px-3 py-2 text-sm font-mono"
                />
                <button
                  type="button"
                  onClick={() => handleCopy(plaintextToken)}
                  aria-label="Copy token"
                  className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl border border-border px-3 transition-all hover:bg-muted"
                >
                  <Copy className="size-4" />
                </button>
              </div>
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Copy this now — it will not be shown again. Closing this page will hide it.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleRegenerate}
                  disabled={regenerate.isPending}
                  className={BUTTON_CLASS}
                >
                  <RefreshCw className={`size-4 ${regenerate.isPending ? 'animate-spin' : ''}`} />
                  {regenerate.isPending ? 'Regenerating...' : 'Regenerate'}
                </button>
                <button
                  type="button"
                  onClick={handleRevoke}
                  disabled={revoke.isPending}
                  className={BUTTON_CLASS}
                >
                  <Trash2 className="size-4" />
                  {revoke.isPending ? 'Revoking...' : 'Revoke'}
                </button>
              </div>
            </div>
          ) : userSettings.data?.has_external_api_token ? (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                Token exists (hidden). Regenerate to view a new one, or Revoke to disable.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleRegenerate}
                  disabled={regenerate.isPending}
                  className={BUTTON_CLASS}
                >
                  <RefreshCw className={`size-4 ${regenerate.isPending ? 'animate-spin' : ''}`} />
                  {regenerate.isPending ? 'Regenerating...' : 'Regenerate'}
                </button>
                <button
                  type="button"
                  onClick={handleRevoke}
                  disabled={revoke.isPending}
                  className={BUTTON_CLASS}
                >
                  <Trash2 className="size-4" />
                  {revoke.isPending ? 'Revoking...' : 'Revoke'}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">No token generated yet.</p>
              <button
                type="button"
                onClick={handleRegenerate}
                disabled={regenerate.isPending}
                className={BUTTON_CLASS}
              >
                <RefreshCw className={`size-4 ${regenerate.isPending ? 'animate-spin' : ''}`} />
                {regenerate.isPending ? 'Regenerating...' : 'Regenerate'}
              </button>
            </div>
          )}

          {/* Connection examples */}
          <div className="space-y-2 pt-1">
            <p className="text-xs font-medium text-muted-foreground">Connection examples</p>

            <details className="rounded-lg border border-border">
              <summary className="cursor-pointer px-3 py-2 text-xs font-medium select-none">
                Claude Desktop / Claude Code (JSON config)
              </summary>
              <div className="border-t border-border px-3 py-2 space-y-2">
                <pre className="overflow-x-auto rounded bg-muted p-2 text-xs leading-relaxed">{`{
  "mcpServers": {
    "health-tracker": {
      "url": "https://health-mcp.leo-figueiredo.com/mcp",
      "headers": {
        "Authorization": "Bearer {TOKEN}"
      }
    }
  }
}`}</pre>
                <p className="text-xs text-muted-foreground">
                  Paste into <code className="rounded bg-muted px-1">~/Library/Application Support/Claude/claude_desktop_config.json</code>. Replace <code className="rounded bg-muted px-1">{'{TOKEN}'}</code> with the regenerated token above.
                </p>
                <button
                  type="button"
                  onClick={() => handleCopy(`{\n  "mcpServers": {\n    "health-tracker": {\n      "url": "https://health-mcp.leo-figueiredo.com/mcp",\n      "headers": {\n        "Authorization": "Bearer {TOKEN}"\n      }\n    }\n  }\n}`)}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Copy className="size-3" />
                  Copy
                </button>
              </div>
            </details>
          </div>
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
