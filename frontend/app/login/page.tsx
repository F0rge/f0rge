'use client'

import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { toast } from 'sonner'
import { PinPad } from '@/components/auth/pin-pad'
import { useLogin } from '@/lib/api/hooks'

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const login = useLogin()
  const [error, setError] = useState(false)

  const handleSubmit = async (pin: string) => {
    setError(false)
    try {
      await login.mutateAsync(pin)
      const redirect = searchParams.get('redirect') || '/checkin'
      router.replace(redirect)
    } catch {
      setError(true)
      toast.error('Wrong PIN')
    }
  }

  return (
    <PinPad
      onSubmit={handleSubmit}
      error={error}
      loading={login.isPending}
    />
  )
}

export default function LoginPage() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 p-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Health Tracker</h1>
        <p className="mt-2 text-sm text-muted-foreground">Enter your PIN</p>
      </div>
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  )
}
