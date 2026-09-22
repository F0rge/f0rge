'use client'

import { useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { AppWarmup } from '@/components/auth/app-warmup'
import { resolvePostLoginRedirect } from '@/lib/auth/safe-redirect'
import { useAuth } from '@/lib/api/hooks'

const PUBLIC_ROUTES = ['/login', '/signup']

function isPublicRoute(pathname: string) {
  return PUBLIC_ROUTES.some((route) => pathname.startsWith(route))
}

function SessionLoading() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
      <Loader2 className="size-8 animate-spin text-muted-foreground" aria-hidden />
      <p className="text-sm text-muted-foreground">Checking session&hellip;</p>
    </div>
  )
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
    if (!isPublic || isLoading || !isAuthenticated) return

    if (pathname.startsWith('/login')) {
      const redirectParam = new URLSearchParams(window.location.search).get('redirect')
      router.replace(resolvePostLoginRedirect(redirectParam))
      return
    }

    router.replace('/checkin')
  }, [isAuthenticated, isLoading, isPublic, pathname, router])

  if (isPublic) {
    if (isLoading || isAuthenticated) {
      return <SessionLoading />
    }
    return children
  }

  if (isLoading || isError || !isAuthenticated) {
    return <SessionLoading />
  }

  return (
    <>
      <AppWarmup />
      {children}
    </>
  )
}
