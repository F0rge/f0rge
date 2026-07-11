'use client'

import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { Input } from '@f0rge/ui'
import { Label } from '@f0rge/ui'

interface AuthCredentialsFormProps {
  mode: 'login' | 'signup'
  email: string
  password: string
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  loading?: boolean
  error?: string | null
}

export function AuthCredentialsForm({
  mode,
  email,
  password,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  loading = false,
  error = null,
}: AuthCredentialsFormProps) {
  const isLogin = mode === 'login'

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
