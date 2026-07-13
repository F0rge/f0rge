'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { Input } from '@f0rge/ui'
import { Label } from '@f0rge/ui'
import { useHandleAvailable } from '@/lib/api/hooks'

interface AuthCredentialsFormProps {
  mode: 'login' | 'signup'
  email: string
  password: string
  handle?: string
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onHandleChange?: (value: string) => void
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  loading?: boolean
  error?: string | null
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

export function AuthCredentialsForm({
  mode,
  email,
  password,
  handle = '',
  onEmailChange,
  onPasswordChange,
  onHandleChange,
  onSubmit,
  loading = false,
  error = null,
}: AuthCredentialsFormProps) {
  const isLogin = mode === 'login'
  const debouncedHandle = useDebouncedValue(handle, 400)
  const availability = useHandleAvailable(debouncedHandle)

  const handleStatus = useMemo(() => {
    if (isLogin || debouncedHandle.length < 3) return null
    if (availability.isLoading) return 'checking'
    if (availability.data?.available) return 'available'
    if (availability.data?.reason === 'invalid') return 'invalid'
    return 'taken'
  }, [availability.data?.available, availability.data?.reason, availability.isLoading, debouncedHandle.length, isLogin])

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          required
          value={email}
          onChange={(event) => onEmailChange(event.target.value)}
          disabled={loading}
          aria-invalid={error ? true : undefined}
        />
      </div>

      {!isLogin && onHandleChange && (
        <div className="flex flex-col gap-2">
          <Label htmlFor="handle">Handle</Label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
              @
            </span>
            <Input
              id="handle"
              value={handle}
              onChange={(event) =>
                onHandleChange(event.target.value.toLowerCase().replace(/^@/, ''))
              }
              className="pl-7"
              placeholder="your_name"
              required
              minLength={3}
              maxLength={30}
              autoComplete="off"
              spellCheck={false}
              disabled={loading}
            />
          </div>
          {handleStatus === 'available' && (
            <p className="text-xs text-emerald-600">Available</p>
          )}
          {handleStatus === 'taken' && (
            <p className="text-xs text-destructive">Already taken</p>
          )}
          {handleStatus === 'invalid' && (
            <p className="text-xs text-destructive">Use 3–30 characters: a-z, 0-9, _</p>
          )}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete={isLogin ? 'current-password' : 'new-password'}
          required
          minLength={8}
          value={password}
          onChange={(event) => onPasswordChange(event.target.value)}
          disabled={loading}
          aria-invalid={error ? true : undefined}
        />
      </div>

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
