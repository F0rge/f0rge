'use client'

import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { AuthCredentialsForm } from '@/components/auth/auth-credentials-form'
import { MarrowWordmark } from '@/components/brand/marrow-wordmark'
import { useLogin } from '@/lib/api/hooks'
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
      const redirect = searchParams.get('redirect') || '/checkin'
      router.replace(redirect)
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
    <div className="flex flex-1 flex-col items-center justify-center gap-8 p-6">
      <div className="text-center">
        <h1 className="flex justify-center">
          <MarrowWordmark className="h-8" />
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">Log in to continue</p>
      </div>
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  )
}
