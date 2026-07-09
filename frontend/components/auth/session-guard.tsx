'use client'

import { useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/lib/api/hooks'

const PUBLIC_ROUTES = ['/login', '/signup']

function isPublicRoute(pathname: string) {
  return PUBLIC_ROUTES.some((route) => pathname.startsWith(route))
}

export function SessionGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { data, isLoading, isError } = useAuth()
  const isPublic = isPublicRoute(pathname)

  useEffect(() => {
    if (isPublic || isLoading) return

    if (isError || !data?.authenticated) {
      const redirect = encodeURIComponent(pathname)
      router.replace(`/login?redirect=${redirect}`)
    }
  }, [data, isError, isLoading, isPublic, pathname, router])

  useEffect(() => {
    if (!isPublic || isLoading) return

    if (data?.authenticated) {
      router.replace('/checkin')
    }
  }, [data, isLoading, isPublic, router])

  if (isPublic) {
    if (isLoading || data?.authenticated) {
      return (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
        </div>
      )
    }
    return children
  }

  if (isLoading || isError || !data?.authenticated) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return children
}
