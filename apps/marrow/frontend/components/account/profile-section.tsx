'use client'

import { useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Upload, UserRound } from 'lucide-react'
import { Button, useDebouncedValue } from '@f0rge/ui'
import { TextInput, useForm } from '@f0rge/ui/forms'
import { UserAvatar } from '@/components/account/user-avatar'
import { SettingsCard } from '@/components/settings/settings-card'
import {
  useAccount,
  useUpdateAccount,
  useUploadAvatar,
  useDeleteAvatar,
  useHandleAvailable,
} from '@/lib/api/hooks'
import { getErrorDetail, handleMutationError } from '@f0rge/ui/api'
import type { Account } from '@/lib/api/types'
import { statusText } from '@/lib/ui/status'

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
  const [handleError, setHandleError] = useState<string | null>(null)
  const [handleDraft, setHandleDraft] = useState(account.handle ?? '')

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: {
      displayName: account.display_name ?? '',
      handle: account.handle ?? '',
    },
    validate: {
      handle: (value) => {
        if (account.handle) return null
        if (value.length < 3) return 'Handle must be at least 3 characters'
        if (!/^[a-z0-9_]+$/.test(value)) return 'Use 3–30 characters: a-z, 0-9, _'
        return null
      },
    },
    onValuesChange: (values) => {
      if (!account.handle) setHandleDraft(values.handle)
    },
  })

  const debouncedHandle = useDebouncedValue(handleDraft, 400)
  const availability = useHandleAvailable(debouncedHandle)
  const handleChanged = handleDraft.trim().toLowerCase() !== (account.handle ?? '')

  const handleStatus = useMemo(() => {
    if (account.handle || !handleChanged || debouncedHandle.length < 3) return null
    if (availability.isLoading) return 'checking'
    if (availability.data?.available) return 'available'
    if (availability.data?.reason === 'invalid') return 'invalid'
    return 'taken'
  }, [
    account.handle,
    availability.data?.available,
    availability.data?.reason,
    availability.isLoading,
    debouncedHandle.length,
    handleChanged,
  ])

  const handleSave = form.onSubmit(async (values) => {
    setHandleError(null)
    try {
      const payload: { display_name: string | null; handle?: string } = {
        display_name: values.displayName.trim() || null,
      }
      if (!account.handle && handleChanged) {
        payload.handle = values.handle.trim().toLowerCase().replace(/^@/, '')
      }
      await updateAccount.mutateAsync(payload)
      toast.success('Profile updated')
    } catch (err) {
      const detail = getErrorDetail(err, 'Failed to update profile')
      if (!account.handle && handleChanged) {
        setHandleError(detail)
      } else {
        handleMutationError(err, 'Failed to update profile')
      }
    }
  })

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
        <p className="text-sm font-medium leading-none">Email</p>
        <p className="text-sm text-muted-foreground">{account.email}</p>
      </div>

      <div className="space-y-1.5">
        {account.handle ? (
          <>
            <p className="text-sm font-medium leading-none">Handle</p>
            <p className="text-sm font-medium">@{account.handle}</p>
            <p className="text-xs text-muted-foreground">Your handle is permanent and cannot be changed.</p>
          </>
        ) : (
          <>
            <TextInput
              key={form.key('handle')}
              label="Handle"
              leftSection={<span className="text-sm text-muted-foreground">@</span>}
              placeholder="your_name"
              autoComplete="off"
              spellCheck={false}
              {...form.getInputProps('handle')}
            />
            {handleStatus === 'available' && (
              <p className={`text-xs ${statusText.ok}`}>Available</p>
            )}
            {handleStatus === 'taken' && (
              <p className="text-xs text-destructive">Already taken</p>
            )}
            {handleStatus === 'invalid' && (
              <p className="text-xs text-destructive">Use 3–30 characters: a-z, 0-9, _</p>
            )}
            {handleError && <p className="text-xs text-destructive">{handleError}</p>}
          </>
        )}
      </div>

      <TextInput
        key={form.key('displayName')}
        label="Display name"
        placeholder="Optional"
        {...form.getInputProps('displayName')}
      />

      <Button
        type="button"
        onClick={() => handleSave()}
        disabled={
          updateAccount.isPending ||
          (!account.handle && handleChanged && handleStatus !== 'available' && handleStatus !== null)
        }
        className="w-full sm:w-auto"
      >
        {updateAccount.isPending ? 'Saving...' : 'Save'}
      </Button>
    </SettingsCard>
  )
}
