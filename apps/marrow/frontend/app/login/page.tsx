'use client'

import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { AuthCredentialsForm } from '@/components/auth/auth-credentials-form'
import { MarrowWordmark } from '@/components/brand/marrow-wordmark'
import { useLogin } from '@/lib/api/hooks'
import { getErrorDetail } from '@f0rge/ui/api'

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)

    try {
      await login.mutateAsync({ email, password })
      const redirect = searchParams.get('redirect') || '/checkin'
      router.replace(redirect)
    } catch (err) {
      setError(getErrorDetail(err, 'Invalid email or password'))
    }
  }

  return (
    <AuthCredentialsForm
      mode="login"
      email={email}
      password={password}
      onEmailChange={setEmail}
      onPasswordChange={setPassword}
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
