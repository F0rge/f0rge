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
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (values: { email: string; password: string; handle?: string }) => {
    setError(null)
    try {
      await signup.mutateAsync({
        email: values.email,
        password: values.password,
        handle: values.handle ?? '',
      })
      router.replace('/checkin')
    } catch (err) {
      setError(getErrorDetail(err, 'Could not create account'))
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-panel space-y-8">
        <div className="text-center">
          <h1 className="flex justify-center">
            <MarrowWordmark className="h-8" />
          </h1>
          <p className="mt-3 text-lg font-semibold tracking-tight text-foreground">Create account</p>
          <p className="mt-2 text-sm text-muted-foreground">Sign up to start your health journal</p>
        </div>
        <AuthCredentialsForm
          mode="signup"
          onSubmit={handleSubmit}
          loading={signup.isPending}
          error={error}
        />
      </div>
    </div>
  )
}
