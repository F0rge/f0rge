'use client'

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Upload, UserRound } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { Input } from '@f0rge/ui'
import { Label } from '@f0rge/ui'
import { UserAvatar } from '@/components/account/user-avatar'
import { SettingsCard } from '@/components/settings/settings-card'
import {
  useAccount,
  useUpdateAccount,
  useUploadAvatar,
  useDeleteAvatar,
} from '@/lib/api/hooks'
import { getErrorDetail, handleMutationError } from '@f0rge/ui/api'
import type { Account } from '@/lib/api/types'
import { useHandleAvailable } from '@/lib/api/hooks'

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
const MAX_BYTES = 5 * 1024 * 1024

export function ProfileSection() {
  const account = useAccount()

  if (!account.data) {
    return (
      <SettingsCard icon={UserRound} title="Profile">
        <p className="text-sm text-muted-foreground">
          {account.isLoading ? 'Loading...' : 'Could not load account'}
        </p>
      </SettingsCard>
    )
  }

  return <ProfileForm account={account.data} />
}

function ProfileForm({ account }: { account: Account }) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const updateAccount = useUpdateAccount()
  const uploadAvatar = useUploadAvatar()
  const deleteAvatar = useDeleteAvatar()
  const [displayName, setDisplayName] = useState(account.display_name ?? '')
  const [handle, setHandle] = useState(account.handle ?? '')
  const [handleError, setHandleError] = useState<string | null>(null)
  const debouncedHandle = useDebouncedValue(handle, 400)
  const availability = useHandleAvailable(debouncedHandle)
  const handleChanged = handle.trim().toLowerCase() !== (account.handle ?? '')
  const handleStatus =
    !handleChanged || debouncedHandle.length < 3
      ? null
      : availability.isLoading
        ? 'checking'
        : availability.data?.available
          ? 'available'
          : 'taken'

  const handleSave = async () => {
    setHandleError(null)
    try {
      const payload: { display_name: string | null; handle?: string } = {
        display_name: displayName.trim() || null,
      }
      if (handleChanged && !account.handle) {
        payload.handle = handle.trim().toLowerCase().replace(/^@/, '')
      }
      await updateAccount.mutateAsync(payload)
      toast.success('Profile updated')
    } catch (err) {
      const detail = getErrorDetail(err, 'Failed to update profile')
      if (handleChanged) {
        setHandleError(detail)
      } else {
        handleMutationError(err, 'Failed to update profile')
      }
    }
  }

  const handleAvatarChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (!ACCEPTED_TYPES.includes(file.type)) {
      toast.error('Use a JPEG, PNG, WebP, or HEIC image')
      return
    }
    if (file.size > MAX_BYTES) {
      toast.error('Image must be 5 MB or smaller')
      return
    }
    try {
      await uploadAvatar.mutateAsync(file)
      toast.success('Profile photo updated')
    } catch (err) {
      handleMutationError(err, 'Failed to upload profile photo')
    } finally {
      event.target.value = ''
    }
  }

  const handleRemoveAvatar = async () => {
    try {
      await deleteAvatar.mutateAsync()
      toast.success('Profile photo removed')
    } catch (err) {
      handleMutationError(err, 'Failed to remove profile photo')
    }
  }

  const avatarBusy = uploadAvatar.isPending || deleteAvatar.isPending

  return (
    <SettingsCard icon={UserRound} title="Profile">
      <div className="flex items-center gap-4">
        <UserAvatar size="md" />
        <div className="flex flex-col gap-2">
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium">
            <Upload className="size-4" />
            {avatarBusy ? 'Uploading...' : 'Upload photo'}
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_TYPES.join(',')}
              onChange={handleAvatarChange}
              className="hidden"
              disabled={avatarBusy}
            />
          </label>
          {account.has_custom_avatar && (
            <button
              type="button"
              onClick={handleRemoveAvatar}
              disabled={avatarBusy}
              className="text-left text-sm text-muted-foreground underline-offset-4 hover:underline"
            >
              Remove photo
            </button>
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>Email</Label>
        <p className="text-sm text-muted-foreground">{account.email}</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="handle">Handle</Label>
        {account.handle ? (
          <p className="text-sm font-medium">@{account.handle}</p>
        ) : (
          <>
            <div className="relative">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                @
              </span>
              <Input
                id="handle"
                value={handle}
                onChange={(e) => setHandle(e.target.value.toLowerCase().replace(/^@/, ''))}
                className="pl-7"
                placeholder="your_name"
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            {handleStatus === 'available' && (
              <p className="text-xs text-emerald-600">Available</p>
            )}
            {handleStatus === 'taken' && (
              <p className="text-xs text-destructive">Already taken</p>
            )}
            {handleError && <p className="text-xs text-destructive">{handleError}</p>}
          </>
        )}
        {account.handle && (
          <p className="text-xs text-muted-foreground">Your handle is permanent and cannot be changed.</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="display-name">Display name</Label>
        <Input
          id="display-name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Optional"
        />
      </div>

      <Button
        type="button"
        onClick={handleSave}
        disabled={
          updateAccount.isPending ||
          (!account.handle &&
            handleChanged &&
            handleStatus !== 'available' &&
            handleStatus !== null)
        }
        className="w-full sm:w-auto"
      >
        {updateAccount.isPending ? 'Saving...' : 'Save'}
      </Button>
    </SettingsCard>
  )
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}
