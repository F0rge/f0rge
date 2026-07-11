'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Copy, Lock, RefreshCw, Trash2 } from 'lucide-react'
import {
  useUserSettings,
  useRegenerateExternalToken,
  useRevokeExternalToken,
} from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { SettingsCard } from './settings-card'
import { BUTTON_CLASS } from './constants'

const MCP_CONFIG_SNIPPET = `{
  "mcpServers": {
    "marrow": {
      "url": "https://marrow-mcp.fly.dev/mcp",
      "headers": {
        "Authorization": "Bearer {TOKEN}"
      }
    }
  }
}`

export function ExternalTokenSection() {
  const userSettings = useUserSettings()
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

  return (
    <SettingsCard icon={Lock} iconClassName="text-muted-foreground" title="External Access Token">
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
            <pre className="overflow-x-auto rounded bg-muted p-2 text-xs leading-relaxed">{MCP_CONFIG_SNIPPET}</pre>
            <p className="text-xs text-muted-foreground">
              Paste into <code className="rounded bg-muted px-1">~/Library/Application Support/Claude/claude_desktop_config.json</code>. Replace <code className="rounded bg-muted px-1">{'{TOKEN}'}</code> with the regenerated token above.
            </p>
            <button
              type="button"
              onClick={() => handleCopy(MCP_CONFIG_SNIPPET)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <Copy className="size-3" />
              Copy
            </button>
          </div>
        </details>
      </div>
    </SettingsCard>
  )
}
