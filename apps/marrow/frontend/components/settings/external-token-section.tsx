'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Copy, Lock, Plus, Trash2 } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  Badge,
  Button,
  FetchError,
  Field,
  FieldLabel,
  formatDisplayDateTime,
  Input,
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import {
  useCreateExternalToken,
  useExternalTokens,
  useRevokeExternalToken,
} from '@/lib/api/hooks'
import type { ExternalApiTokenItem } from '@/lib/api/types'
import { SettingsCard } from './settings-card'

const MCP_CONFIG_SNIPPET = `{
  "mcpServers": {
    "marrow": {
      "url": "https://mcp.marrow-health.com/mcp",
      "headers": {
        "Authorization": "Bearer {TOKEN}"
      }
    }
  }
}`

function tokenMeta(token: ExternalApiTokenItem): string | null {
  if (!token.created_at) return null
  return formatDisplayDateTime(token.created_at)
}

export function ExternalTokenSection() {
  const tokens = useExternalTokens()
  const create = useCreateExternalToken()
  const revoke = useRevokeExternalToken()
  const [name, setName] = useState('')
  const [revealed, setRevealed] = useState<{ name: string; token: string } | null>(null)
  const [revokeTarget, setRevokeTarget] = useState<ExternalApiTokenItem | null>(null)

  const handleCreate = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    try {
      const result = await create.mutateAsync(trimmed)
      setRevealed({ name: result.name, token: result.token })
      setName('')
      toast.success('Token created — copy it now; it will not be shown again')
    } catch (err) {
      handleMutationError(err, 'Failed to create token')
    }
  }

  const handleRevokeConfirm = async () => {
    if (!revokeTarget) return
    try {
      await revoke.mutateAsync(revokeTarget.id)
      toast.success('Token revoked')
      setRevokeTarget(null)
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

  const rows = tokens.data?.tokens ?? []

  return (
    <SettingsCard icon={Lock} iconClassName="text-muted-foreground" title="External access tokens">
      <p className="text-xs text-muted-foreground">
        For querying your health data from Claude Code or Claude Desktop via MCP. Each token stays
        valid until you revoke it.
      </p>

      {revealed && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Copy the secret for {revealed.name} now. It will not be shown again.
          </p>
          <div className="flex gap-2">
            <Input
              readOnly
              value={revealed.token}
              aria-label={`Secret for ${revealed.name}`}
              className="font-mono text-sm"
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="min-h-11 min-w-11"
              aria-label="Copy token"
              onClick={() => handleCopy(revealed.token)}
            >
              <Copy />
            </Button>
          </div>
        </div>
      )}

      {tokens.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading tokens…</p>
      ) : tokens.isError ? (
        <FetchError message="Couldn't load tokens." onRetry={() => tokens.refetch()} />
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No tokens yet.</p>
      ) : (
        <ul className="space-y-2" aria-label="External access tokens">
          {rows.map((token) => {
            const meta = tokenMeta(token)
            return (
              <li key={token.id}>
                <Item variant="outline" size="sm" className="rounded-lg">
                  <ItemContent>
                    <ItemTitle className="truncate">{token.name}</ItemTitle>
                    {meta && <ItemDescription>{meta}</ItemDescription>}
                  </ItemContent>
                  <ItemActions>
                    <Badge variant="secondary" className="text-[10px]">active</Badge>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="min-h-11 min-w-11"
                      aria-label={`Revoke ${token.name}`}
                      disabled={revoke.isPending && revoke.variables === token.id}
                      onClick={() => setRevokeTarget(token)}
                    >
                      <Trash2 />
                    </Button>
                  </ItemActions>
                </Item>
              </li>
            )
          })}
        </ul>
      )}

      <div className="flex items-end gap-2">
        <Field className="min-w-0 flex-1">
          <FieldLabel htmlFor="token-name">Name</FieldLabel>
          <Input
            id="token-name"
            placeholder="laptop"
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            maxLength={64}
          />
        </Field>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 shrink-0"
          onClick={handleCreate}
          disabled={create.isPending || name.trim().length === 0}
        >
          <Plus />
          {create.isPending ? 'Creating...' : 'Create token'}
        </Button>
      </div>

      <div className="space-y-2 pt-1">
        <p className="text-xs font-medium text-muted-foreground">Connection examples</p>
        <details className="rounded-lg border border-border">
          <summary className="cursor-pointer px-3 py-2 text-xs font-medium select-none">
            Claude / Cursor (JSON config)
          </summary>
          <div className="space-y-2 border-t border-border px-3 py-2">
            <pre className="overflow-x-auto rounded bg-muted p-2 text-xs leading-relaxed">{MCP_CONFIG_SNIPPET}</pre>
            <p className="text-xs text-muted-foreground">
              Paste into Cursor <code className="rounded bg-muted px-1">~/.cursor/mcp.json</code> or
              Claude Desktop config. Replace <code className="rounded bg-muted px-1">{'{TOKEN}'}</code> with
              the secret shown once above.
            </p>
            <Button type="button" variant="ghost" size="sm" onClick={() => handleCopy(MCP_CONFIG_SNIPPET)}>
              <Copy />
              Copy
            </Button>
          </div>
        </details>
      </div>

      <AlertDialog open={revokeTarget !== null} onOpenChange={(open) => { if (!open) setRevokeTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader className="text-left sm:text-left">
            <AlertDialogTitle>Revoke token?</AlertDialogTitle>
            <AlertDialogDescription>
              {revokeTarget
                ? `“${revokeTarget.name}” will stop working immediately. MCP clients using it will lose access.`
                : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="sm:justify-end">
            <AlertDialogCancel type="button" disabled={revoke.isPending}>Cancel</AlertDialogCancel>
            <Button
              type="button"
              variant="destructive"
              onClick={() => void handleRevokeConfirm()}
              disabled={revoke.isPending}
            >
              {revoke.isPending ? 'Revoking…' : 'Revoke token'}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsCard>
  )
}
