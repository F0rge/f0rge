'use client'

import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { PinPad } from '@/components/auth/pin-pad'
import { useLogin } from '@/lib/api/hooks'
import { useState } from 'react'

export default function LoginPage() {
  const router = useRouter()
  const login = useLogin()
  const [error, setError] = useState(false)

  const handleSubmit = async (pin: string) => {
    setError(false)
    try {
      await login.mutateAsync(pin)
      router.replace('/checkin')
    } catch {
      setError(true)
      toast.error('Wrong PIN')
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 p-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Health Tracker</h1>
        <p className="mt-2 text-sm text-muted-foreground">Enter your PIN</p>
      </div>
      <PinPad
        onSubmit={handleSubmit}
        error={error}
        loading={login.isPending}
      />
    </div>
  )
}
