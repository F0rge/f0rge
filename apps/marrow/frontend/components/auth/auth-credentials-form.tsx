'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import {
  Button,
  Field,
  FieldError,
  FieldLabel,
  Input,
  useDebouncedValue,
} from '@f0rge/ui'
import { isEmail, PasswordInput, useForm } from '@f0rge/ui/forms'
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

  const emailProps = form.getInputProps('email')
  const handleProps = form.getInputProps('handle')
  const passwordProps = form.getInputProps('password')

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <Field data-invalid={emailProps.error ? true : undefined}>
        <FieldLabel htmlFor="auth-email">Email</FieldLabel>
        <Input
          id="auth-email"
          key={form.key('email')}
          type="email"
          autoComplete="email"
          inputMode="email"
          required
          disabled={loading}
          {...emailProps}
        />
        {emailProps.error && <FieldError>{emailProps.error}</FieldError>}
      </Field>

      {!isLogin && (
        <Field data-invalid={handleProps.error ? true : undefined}>
          <FieldLabel htmlFor="auth-handle">Handle</FieldLabel>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
              @
            </span>
            <Input
              id="auth-handle"
              key={form.key('handle')}
              className="pl-7"
              placeholder="your_name"
              required
              autoComplete="off"
              spellCheck={false}
              disabled={loading}
              {...handleProps}
            />
          </div>
          {handleProps.error && <FieldError>{handleProps.error}</FieldError>}
          {handleStatus === 'available' && (
            <p className={`text-xs ${statusText.ok}`}>Available</p>
          )}
          {handleStatus === 'taken' && (
            <p className="text-xs text-destructive">Already taken</p>
          )}
          {handleStatus === 'invalid' && (
            <p className="text-xs text-destructive">Use 3–30 characters: a-z, 0-9, _</p>
          )}
        </Field>
      )}

      <PasswordInput
        key={form.key('password')}
        label="Password"
        autoComplete={isLogin ? 'current-password' : 'new-password'}
        required
        disabled={loading}
        {...passwordProps}
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
