'use client'

import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { AuthCredentialsForm } from '@/components/auth/auth-credentials-form'
import { MarrowWordmark } from '@/components/brand/marrow-wordmark'
import { useLogin } from '@/lib/api/hooks'
import { safePostLoginRedirect } from '@/lib/auth/safe-post-login-redirect'
import { getErrorDetail } from '@f0rge/ui/api'
import { useState } from 'react'

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const login = useLogin()
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (values: { email: string; password: string }) => {
    setError(null)
    try {
      await login.mutateAsync(values)
      router.replace(safePostLoginRedirect(searchParams.get('redirect')))
    } catch (err) {
      setError(getErrorDetail(err, 'Invalid email or password'))
    }
  }

  return (
    <AuthCredentialsForm
      mode="login"
      onSubmit={handleSubmit}
      loading={login.isPending}
      error={error}
    />
  )
}

export default function LoginPage() {
  return (
    <div className="auth-shell">
      <div className="auth-panel space-y-8">
        <div className="text-center">
          <h1 className="flex justify-center">
            <MarrowWordmark className="h-8" />
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">Log in to your health journal</p>
        </div>
        <Suspense>
          <LoginForm />
        </Suspense>
      </div>
    </div>
  )
}
