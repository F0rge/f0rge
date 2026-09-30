'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useCallback, useLayoutEffect, useRef } from 'react'
import { ClipboardCheck, Pill, CalendarDays, TrendingUp, Microscope } from 'lucide-react'
import { cn } from '@f0rge/ui'
import { UserAvatar } from '@/components/account/user-avatar'
import { useKeyboardOpen } from '@/hooks/use-keyboard-open'
import {
  PILL_UNDERLINE_STROKE,
  collapsedUnderlineDash,
  fullCornerSpan,
  pillBottomPath,
  underlineDash,
  type UnderlineDash,
} from '@/lib/nav/pill-underline'
import { CHROME_TONE, iconWellClass } from '@/lib/ui/status'

const NAV_ITEMS = [
  { href: '/checkin', label: 'Today', icon: ClipboardCheck },
  { href: '/history', label: 'History', icon: CalendarDays },
  { href: '/treatments', label: 'Treatments', icon: Pill },
  { href: '/labs', label: 'Labs', icon: Microscope },
  { href: '/signals', label: 'Signals', icon: TrendingUp },
  { href: '/profile', label: 'Profile', icon: null },
] as const

const EDGE = '0.5s cubic-bezier(0.19, 1, 0.22, 1)'

function toPx(dasharray: string): string {
  return dasharray
    .split(' ')
    .map((part) => `${part}px`)
    .join(' ')
}

export function BottomNav() {
  const pathname = usePathname()
  const keyboardOpen = useKeyboardOpen()
  const navHidden = pathname.startsWith('/login') || pathname.startsWith('/signup')
  const barRef = useRef<HTMLElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const pathRef = useRef<SVGPathElement>(null)
  const spanRef = useRef<{ x0: number; x1: number; width: number; height: number } | null>(null)
  const prevIndexRef = useRef<number | null>(null)
  const lastActiveIndexRef = useRef<number | null>(null)

  const activeIndex = NAV_ITEMS.findIndex((item) => pathname.startsWith(item.href))

  const syncBorder = useCallback(() => {
    const bar = barRef.current
    const svg = svgRef.current
    const path = pathRef.current
    if (!bar || !svg || !path) return null

    const cs = getComputedStyle(bar)
    const borderLeft = parseFloat(cs.borderLeftWidth) || 0
    const borderTop = parseFloat(cs.borderTopWidth) || 0
    const borderRight = parseFloat(cs.borderRightWidth) || 0
    const width = bar.offsetWidth
    const height = bar.offsetHeight
    if (width <= 0 || height <= 0) return null

    svg.style.left = `${-borderLeft}px`
    svg.style.top = `${-borderTop}px`
    svg.style.width = `${width}px`
    svg.style.height = `${height}px`
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`)
    path.setAttribute('d', pillBottomPath(width, height, PILL_UNDERLINE_STROKE / 2))

    return {
      width,
      height,
      padLeft: borderLeft + (parseFloat(cs.paddingLeft) || 0),
      padRight: borderRight + (parseFloat(cs.paddingRight) || 0),
      path,
    }
  }, [])

  const paint = useCallback((dash: UnderlineDash, path: SVGPathElement, animate: boolean) => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const motion = `stroke-dasharray ${EDGE}, stroke-dashoffset ${EDGE}`
    if (!animate || reduced) {
      path.style.transition = 'none'
      path.style.strokeDasharray = toPx(dash.dasharray)
      path.style.strokeDashoffset = `${dash.dashoffset}px`
      void path.getBoundingClientRect()
      path.style.transition = motion
      return
    }
    path.style.transition = motion
    void path.getBoundingClientRect()
    path.style.strokeDasharray = toPx(dash.dasharray)
    path.style.strokeDashoffset = `${dash.dashoffset}px`
  }, [])

  const place = useCallback(
    (index: number, direction: number) => {
      const box = syncBorder()
      if (!box || index < 0) return

      const span = fullCornerSpan(index, box.width, box.padLeft, box.padRight, NAV_ITEMS.length)
      spanRef.current = { ...span, width: box.width, height: box.height }
      paint(
        underlineDash(span.x0, span.x1, box.width, box.height),
        box.path,
        direction !== 0,
      )
    },
    [paint, syncBorder],
  )

  const collapseInk = useCallback((direction: number) => {
    const box = syncBorder()
    const span = spanRef.current
    if (!box || !span) return

    const center = (span.x0 + span.x1) / 2
    paint(
      collapsedUnderlineDash(center, box.width, box.height),
      box.path,
      direction !== 0,
    )
  }, [paint, syncBorder])

  const activeIndexRef = useRef(activeIndex)

  useLayoutEffect(() => {
    if (activeIndex < 0) {
      const prev = prevIndexRef.current
      if (prev !== null) {
        collapseInk(Math.sign(0 - prev))
        lastActiveIndexRef.current = prev
      }
      prevIndexRef.current = null
      activeIndexRef.current = -1
      return
    }

    activeIndexRef.current = activeIndex
    const prev = prevIndexRef.current ?? lastActiveIndexRef.current
    const direction = prev === null ? 0 : Math.sign(activeIndex - prev)
    place(activeIndex, direction)
    prevIndexRef.current = activeIndex
    lastActiveIndexRef.current = activeIndex
  }, [activeIndex, place, collapseInk])

  useLayoutEffect(() => {
    const onResize = () => {
      if (activeIndexRef.current < 0) return
      place(activeIndexRef.current, 0)
    }
    window.addEventListener('resize', onResize)
    document.fonts?.ready.then(onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [place])

  if (navHidden) return null

  return (
    <nav
      ref={barRef}
      aria-label="Primary"
      data-tour="bottom-nav"
      className={cn(
        'fixed bottom-[calc(20px+env(safe-area-inset-bottom))] left-1/2 z-50 flex',
        'w-3/4 max-w-[400px] -translate-x-1/2 items-stretch rounded-full',
        'border border-border bg-card/95 px-1 pt-1.5 pb-2',
        'shadow-none backdrop-blur-md',
        'transition-[opacity,transform] duration-[450ms] ease-[cubic-bezier(0.19,1,0.22,1)]',
        keyboardOpen && 'pointer-events-none translate-y-4 opacity-0',
      )}
    >
      <svg
        ref={svgRef}
        aria-hidden
        className="pointer-events-none absolute overflow-visible text-primary"
      >
        <path
          ref={pathRef}
          fill="none"
          stroke="currentColor"
          strokeWidth={PILL_UNDERLINE_STROKE}
          strokeLinecap="round"
        />
      </svg>
      {NAV_ITEMS.map((item, index) => {
        const active = index === activeIndex
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-label={item.label}
            aria-current={active ? 'page' : undefined}
            data-tour={item.href === '/profile' ? 'profile-tab' : undefined}
            className={cn(
              'relative flex min-h-[48px] min-w-0 flex-1 flex-col items-center justify-center gap-0.5 px-0.5 py-1',
              active ? 'text-foreground' : 'text-muted-foreground',
            )}
          >
            {item.icon ? (
              <span
                className={cn(
                  'flex size-8 flex-none items-center justify-center rounded-full',
                  'transition-colors duration-300 ease-out',
                  active ? iconWellClass[CHROME_TONE] : 'bg-transparent',
                )}
              >
                <item.icon className="size-4" />
              </span>
            ) : (
              <span
                className={cn(
                  'relative flex size-8 flex-none items-center justify-center rounded-full',
                  'transition-all duration-300 ease-out',
                  active && 'ring-2 ring-primary',
                )}
              >
                <UserAvatar size="xs" />
              </span>
            )}
            <span
              className={cn(
                'max-w-full truncate text-center text-[9px] leading-tight font-medium',
                active && 'font-semibold',
              )}
            >
              {item.label}
            </span>
          </Link>
        )
      })}
    </nav>
  )
}
