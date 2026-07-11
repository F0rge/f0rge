'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { AuthCredentialsForm } from '@/components/auth/auth-credentials-form'
import { MarrowWordmark } from '@/components/brand/marrow-wordmark'
import { useSignup } from '@/lib/api/hooks'
import { getErrorDetail } from '@f0rge/ui/api'

export default function SignupPage() {
  const router = useRouter()
  const signup = useSignup()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)

    try {
      await signup.mutateAsync({ email, password })
      router.replace('/checkin')
    } catch (err) {
      setError(getErrorDetail(err, 'Could not create account'))
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 p-6">
      <div className="text-center">
        <h1 className="flex justify-center">
          <MarrowWordmark className="h-8" />
        </h1>
        <p className="mt-3 text-lg font-semibold tracking-tight">Create account</p>
        <p className="mt-2 text-sm text-muted-foreground">Sign up to start tracking</p>
      </div>
      <AuthCredentialsForm
        mode="signup"
        email={email}
        password={password}
        onEmailChange={setEmail}
        onPasswordChange={setPassword}
        onSubmit={handleSubmit}
        loading={signup.isPending}
        error={error}
      />
    </div>
  )
}
