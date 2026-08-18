'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import { ClipboardCheck, Pill, CalendarDays, TrendingUp, Microscope } from 'lucide-react'
import { cn } from '@f0rge/ui'
import { UserAvatar } from '@/components/account/user-avatar'
import { useKeyboardOpen } from '@/hooks/use-keyboard-open'
import { CHROME_TONE, iconWellClass } from '@/lib/ui/status'

const NAV_ITEMS = [
  { href: '/checkin', label: 'Today', icon: ClipboardCheck },
  { href: '/history', label: 'History', icon: CalendarDays },
  { href: '/treatments', label: 'Treatments', icon: Pill },
  { href: '/labs', label: 'Labs', icon: Microscope },
  { href: '/signals', label: 'Signals', icon: TrendingUp },
  { href: '/profile', label: 'Profile', icon: null },
] as const

const ICON_W = 32
const ICON_GAP = 6
const MAX_LABEL_W = 62
const BREATHING = 16
const MIN_GROW = 1.2
const EDGE = '0.5s cubic-bezier(0.19, 1, 0.22, 1)'

export function BottomNav() {
  const pathname = usePathname()
  const keyboardOpen = useKeyboardOpen()
  const navHidden = pathname.startsWith('/login') || pathname.startsWith('/signup')
  const barRef = useRef<HTMLElement>(null)
  const inkRef = useRef<HTMLDivElement>(null)
  const labelRefs = useRef<(HTMLSpanElement | null)[]>([])
  const prevIndexRef = useRef<number | null>(null)
  const lastActiveIndexRef = useRef<number | null>(null)

  const activeIndex = NAV_ITEMS.findIndex((item) => pathname.startsWith(item.href))
  const [activeGrow, setActiveGrow] = useState(2.4)

  const place = useCallback(
    (index: number, direction: number) => {
      const bar = barRef.current
      const ink = inkRef.current
      if (!bar || !ink || index < 0) return

      const cs = getComputedStyle(bar)
      const inner = bar.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)
      const n = NAV_ITEMS.length
      const minTabW = ICON_W

      const label = labelRefs.current[index]
      const labelW = label ? Math.min(label.scrollWidth, MAX_LABEL_W) : 0
      const rawNeed = ICON_W + ICON_GAP + labelW + BREATHING

      const grow = Math.max(
        MIN_GROW,
        Math.min(
          (rawNeed * (n - 1)) / (inner - rawNeed),
          (inner - minTabW * (n - 1)) / minTabW,
        ),
      )
      setActiveGrow(grow)

      const unit = inner / (grow + (n - 1))
      const activeW = unit * grow
      const startX = parseFloat(cs.paddingLeft) + unit * index
      const lineW = rawNeed - BREATHING
      const left = startX + (activeW - lineW) / 2
      const right = bar.clientWidth - (left + lineW)

      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

      if (reduced || direction === 0) {
        if (
          Math.abs(parseFloat(ink.style.left || '0') - left) < 0.5 &&
          Math.abs(parseFloat(ink.style.right || '0') - right) < 0.5
        ) {
          return
        }
        ink.style.transition = 'none'
        ink.style.left = `${left}px`
        ink.style.right = `${right}px`
        void ink.offsetWidth
        ink.style.transition = `left ${EDGE}, right ${EDGE}`
        return
      }

      ink.style.transition = `left ${EDGE}, right ${EDGE}`
      void ink.offsetWidth
      ink.style.left = `${left}px`
      ink.style.right = `${right}px`
    },
    [],
  )

  const collapseInk = useCallback((direction: number) => {
    const bar = barRef.current
    const ink = inkRef.current
    if (!bar || !ink) return

    const left = parseFloat(ink.style.left || '0')
    const right = parseFloat(ink.style.right || '0')
    const lineW = bar.clientWidth - left - right
    const center = left + lineW / 2
    const collapsedLeft = center
    const collapsedRight = bar.clientWidth - center

    setActiveGrow(1)

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ink.style.transition =
      reduced || direction === 0
        ? 'none'
        : `left ${EDGE}, right ${EDGE}`
    void ink.offsetWidth
    ink.style.left = `${collapsedLeft}px`
    ink.style.right = `${collapsedRight}px`
  }, [])

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
      aria-hidden={keyboardOpen}
      data-tour="bottom-nav"
      className={cn(
        'fixed bottom-[calc(20px+env(safe-area-inset-bottom))] left-1/2 z-50 flex',
        'w-3/4 max-w-[400px] -translate-x-1/2 items-stretch rounded-full',
        'border border-border bg-card/90 px-[7px] pt-1 pb-2',
        'shadow-[0_18px_40px_-18px_rgba(0,0,0,0.28)] backdrop-blur-[18px] backdrop-saturate-[1.5]',
        'transition-[opacity,transform] duration-[450ms] ease-[cubic-bezier(0.19,1,0.22,1)]',
        keyboardOpen && 'pointer-events-none translate-y-4 opacity-0',
      )}
    >
      <div
        ref={inkRef}
        className="absolute bottom-[5px] left-0 right-full h-[3px] rounded-full bg-chart-1"
      />
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
              'relative flex h-[42px] min-w-0 flex-1 items-center justify-center',
              active ? 'text-foreground' : 'text-muted-foreground',
            )}
            style={{
              flexGrow: active ? activeGrow : 1,
              transition: 'flex-grow 0.5s cubic-bezier(0.19, 1, 0.22, 1), color 0.35s ease',
            }}
          >
            {item.icon ? (
              <span
                className={cn(
                  'flex size-8 flex-none items-center justify-center rounded-full',
                  'transition-all duration-500 ease-[cubic-bezier(0.19,1,0.22,1)]',
                  active ? iconWellClass[CHROME_TONE] : 'bg-transparent',
                  active ? 'scale-100' : 'scale-[0.82]',
                )}
              >
                <item.icon className="size-4" />
              </span>
            ) : (
              <span
                className={cn(
                  'relative flex size-8 flex-none items-center justify-center rounded-full',
                  'transition-all duration-500 ease-[cubic-bezier(0.19,1,0.22,1)]',
                  active ? 'scale-100 ring-[2px] ring-chart-1' : 'scale-[0.82]',
                )}
              >
                <UserAvatar size="xs" />
              </span>
            )}
            <span
              ref={(el) => {
                labelRefs.current[index] = el
              }}
              className={cn(
                'ml-0 max-w-0 overflow-hidden whitespace-nowrap text-[10px] font-semibold opacity-0',
                '-translate-x-1',
                active && 'ml-1.5 max-w-[62px] translate-x-0 opacity-100',
              )}
              style={{
                transition:
                  'opacity 0.28s ease, transform 0.5s cubic-bezier(0.19, 1, 0.22, 1), max-width 0.5s cubic-bezier(0.19, 1, 0.22, 1), margin-left 0.5s cubic-bezier(0.19, 1, 0.22, 1)',
              }}
            >
              {item.label}
            </span>
          </Link>
        )
      })}
    </nav>
  )
}
