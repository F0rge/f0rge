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
  const isAuthenticated = Boolean(data?.authenticated) && !isError

  useEffect(() => {
    if (isPublic || isLoading) return

    if (isError || !isAuthenticated) {
      const redirect = encodeURIComponent(pathname)
      router.replace(`/login?redirect=${redirect}`)
    }
  }, [isAuthenticated, isError, isLoading, isPublic, pathname, router])

  useEffect(() => {
    if (!isPublic || isLoading) return

    if (isAuthenticated) {
      router.replace('/checkin')
    }
  }, [isAuthenticated, isLoading, isPublic, router])

  if (isPublic) {
    if (isLoading || isAuthenticated) {
      return (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
        </div>
      )
    }
    return children
  }

  if (isLoading || isError || !isAuthenticated) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return children
}
