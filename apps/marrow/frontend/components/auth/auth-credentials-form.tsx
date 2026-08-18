'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import { Button, useDebouncedValue } from '@f0rge/ui'
import { isEmail, PasswordInput, TextInput, useForm } from '@f0rge/ui/forms'
import { useHandleAvailable } from '@/lib/api/hooks'
import { statusText } from '@/lib/ui/status'

interface AuthCredentialsFormProps {
  mode: 'login' | 'signup'
  onSubmit: (values: { email: string; password: string; handle?: string }) => void | Promise<void>
  loading?: boolean
  error?: string | null
}

export function AuthCredentialsForm({
  mode,
  onSubmit,
  loading = false,
  error = null,
}: AuthCredentialsFormProps) {
  const isLogin = mode === 'login'
  const [handleDraft, setHandleDraft] = useState('')

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: {
      email: '',
      password: '',
      handle: '',
    },
    validate: {
      email: (value) => (isEmail(value) ? null : 'Enter a valid email'),
      password: (value) => (value.length >= 8 ? null : 'Password must be at least 8 characters'),
      handle: (value) => {
        if (isLogin) return null
        if (value.length < 3) return 'Handle must be at least 3 characters'
        if (value.length > 30) return 'Handle must be at most 30 characters'
        if (!/^[a-z0-9_]+$/.test(value)) return 'Use 3–30 characters: a-z, 0-9, _'
        return null
      },
    },
    onValuesChange: (values) => {
      if (!isLogin) setHandleDraft(values.handle)
    },
  })

  const debouncedHandle = useDebouncedValue(handleDraft, 400)
  const availability = useHandleAvailable(debouncedHandle)

  const handleStatus = useMemo(() => {
    if (isLogin || debouncedHandle.length < 3) return null
    if (availability.isLoading) return 'checking'
    if (availability.data?.available) return 'available'
    if (availability.data?.reason === 'invalid') return 'invalid'
    return 'taken'
  }, [availability.data?.available, availability.data?.reason, availability.isLoading, debouncedHandle.length, isLogin])

  const handleSubmit = form.onSubmit(async (values) => {
    await onSubmit({
      email: values.email,
      password: values.password,
      handle: isLogin ? undefined : values.handle.trim().toLowerCase().replace(/^@/, ''),
    })
  })

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <TextInput
        key={form.key('email')}
        label="Email"
        type="email"
        autoComplete="email"
        inputMode="email"
        required
        disabled={loading}
        error={error ? ' ' : undefined}
        {...form.getInputProps('email')}
      />

      {!isLogin && (
        <div>
          <TextInput
            key={form.key('handle')}
            label="Handle"
            leftSection={<span className="text-sm text-muted-foreground">@</span>}
            placeholder="your_name"
            required
            autoComplete="off"
            spellCheck={false}
            disabled={loading}
            {...form.getInputProps('handle')}
          />
          {handleStatus === 'available' && (
            <p className={`mt-1 text-xs ${statusText.ok}`}>Available</p>
          )}
          {handleStatus === 'taken' && (
            <p className="mt-1 text-xs text-destructive">Already taken</p>
          )}
          {handleStatus === 'invalid' && (
            <p className="mt-1 text-xs text-destructive">Use 3–30 characters: a-z, 0-9, _</p>
          )}
        </div>
      )}

      <PasswordInput
        key={form.key('password')}
        label="Password"
        autoComplete={isLogin ? 'current-password' : 'new-password'}
        required
        disabled={loading}
        {...form.getInputProps('password')}
      />

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button type="submit" disabled={loading} className="w-full">
        {loading ? <Loader2 className="size-4 animate-spin" /> : isLogin ? 'Log in' : 'Create account'}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        {isLogin ? (
          <>
            No account?{' '}
            <Link href="/signup" className="font-medium text-foreground underline-offset-4 hover:underline">
              Sign up
            </Link>
          </>
        ) : (
          <>
            Already have an account?{' '}
            <Link href="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
              Log in
            </Link>
          </>
        )}
      </p>
    </form>
  )
}
