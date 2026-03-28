'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/api/hooks'
import { Loader2 } from 'lucide-react'

export default function RootPage() {
  const router = useRouter()
  const { data, isLoading, isError } = useAuth()

  useEffect(() => {
    if (isLoading) return
    if (isError || !data?.authenticated) {
      router.replace('/login')
    } else {
      router.replace('/checkin')
    }
  }, [data, isLoading, isError, router])

  return (
    <div className="flex flex-1 items-center justify-center">
      <Loader2 className="size-8 animate-spin text-muted-foreground" />
    </div>
  )
}
