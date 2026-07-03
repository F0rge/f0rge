'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import { ClipboardCheck, Pill, CalendarDays, TrendingUp, Settings, Microscope } from 'lucide-react'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { href: '/checkin', label: 'Today', icon: ClipboardCheck },
  { href: '/history', label: 'History', icon: CalendarDays },
  { href: '/treatments', label: 'Treatments', icon: Pill },
  { href: '/labs', label: 'Labs', icon: Microscope },
  { href: '/insights', label: 'Insights', icon: TrendingUp },
  { href: '/settings', label: 'Settings', icon: Settings },
] as const

// Content-derived tab sizing. Each tab's "need" is icon + gap + clamped
// label width + breathing room; the active tab's flex-grow is solved so its
// final layout width lands on its need instead of a fixed ratio, so
// "Treatments" doesn't carry the same footprint as "Labs".
const ICON_W = 24
const ICON_GAP = 6
const MAX_LABEL_W = 62
const BREATHING = 16
const MIN_GROW = 1.2

// Leading edge stretches out fast with a small overshoot; trailing edge
// arrives slower with a late snap. Ported verbatim from the approved mockup
// (nav-mockups.html) — tuned empirically, do not re-derive.
const FAST_EDGE = '.18s cubic-bezier(.2,.9,.3,1.18)'
const SLOW_EDGE = '.3s cubic-bezier(.7,.02,.35,1.06)'
const COOL_DELAY_MS = 330
const INK_BASE_TRANSITION = 'background-color .25s'

export function BottomNav() {
  const pathname = usePathname()
  const barRef = useRef<HTMLElement>(null)
  const inkRef = useRef<HTMLDivElement>(null)
  const labelRefs = useRef<(HTMLSpanElement | null)[]>([])
  const prevIndexRef = useRef<number | null>(null)
  const coolTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const activeIndex = NAV_ITEMS.findIndex((item) => pathname.startsWith(item.href))

  // Per-tab flex-grow, keyed by index. Resting tabs stay at 1; the active
  // tab's grow is solved so its final width lands on its content need
  // instead of a fixed ratio (see place() for the derivation).
  const [activeGrow, setActiveGrow] = useState(2.4)

  // Compute the underline's left/right target (px, relative to the bar's
  // border box) from final flex-grow layout math rather than reading
  // mid-transition geometry. Verbatim port of the mockup's targets(), with
  // GROW replaced by a per-call solved value so tab width tracks content.
  // useCallback with an empty dep array: only reads stable refs and the
  // stable setActiveGrow setter, so it's safe to list as an effect dep
  // without refiring on every render.
  const place = useCallback((index: number, direction: number) => {
    const bar = barRef.current
    const ink = inkRef.current
    if (!bar || !ink || index < 0) return

    const cs = getComputedStyle(bar)
    const inner = bar.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)
    const n = NAV_ITEMS.length
    const minTabW = ICON_W

    // icon + gap + clamped label width + breathing room. scrollWidth is
    // read straight off the DOM so it's accurate even while the label is
    // clipped (max-width: 0) on a resting tab.
    const label = labelRefs.current[index]
    const labelW = label ? Math.min(label.scrollWidth, MAX_LABEL_W) : 0
    const rawNeed = ICON_W + ICON_GAP + labelW + BREATHING

    const grow = Math.max(
      MIN_GROW,
      Math.min(
        (rawNeed * (n - 1)) / (inner - rawNeed),
        (inner - minTabW * (n - 1)) / minTabW, // caps activeW at inner - (n-1)*minTabW
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
      ink.style.transition = 'none'
      ink.style.left = `${left}px`
      ink.style.right = `${right}px`
      void ink.offsetWidth
      ink.style.transition = INK_BASE_TRANSITION
      return
    }

    // Direction-aware: the edge in the direction of travel leads (fast,
    // bouncy), the trailing edge follows (slower, late snap).
    ink.style.transition =
      direction > 0
        ? `right ${FAST_EDGE}, left ${SLOW_EDGE}, background-color .18s`
        : `left ${FAST_EDGE}, right ${SLOW_EDGE}, background-color .18s`
    void ink.offsetWidth // commit the transition swap before moving the edges, or one edge snaps

    ink.classList.add('bg-foreground')
    ink.classList.remove('bg-muted-foreground')
    ink.style.left = `${left}px`
    ink.style.right = `${right}px`

    clearTimeout(coolTimeoutRef.current)
    coolTimeoutRef.current = setTimeout(() => {
      ink.classList.remove('bg-foreground')
      ink.classList.add('bg-muted-foreground')
      ink.style.transition = INK_BASE_TRANSITION
    }, COOL_DELAY_MS)
  }, [])

  useLayoutEffect(() => {
    if (activeIndex < 0) return
    const prev = prevIndexRef.current
    const direction = prev === null ? 0 : Math.sign(activeIndex - prev)
    place(activeIndex, direction)
    prevIndexRef.current = activeIndex
  }, [activeIndex, place])

  useLayoutEffect(() => {
    const onResize = () => place(activeIndex, 0)
    window.addEventListener('resize', onResize)
    // Label scrollWidth depends on rendered glyph metrics — re-place once
    // the real font has swapped in, since the mount-time read may have
    // measured a fallback font's (different) width.
    document.fonts?.ready.then(onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [activeIndex, place])

  if (pathname.startsWith('/login')) return null

  return (
    <nav
      ref={barRef}
      aria-label="Primary"
      className={cn(
        'fixed bottom-[calc(20px+env(safe-area-inset-bottom))] left-1/2 z-50 flex',
        'w-3/4 max-w-[400px] -translate-x-1/2 items-stretch rounded-[22px]',
        'border border-border bg-background/88 px-[7px] pt-1 pb-2',
        'shadow-[0_14px_34px_-10px_rgba(0,0,0,0.28)] backdrop-blur-[14px] backdrop-saturate-[1.4]',
      )}
    >
      <div
        ref={inkRef}
        className="absolute bottom-[5px] left-0 right-full h-[2.5px] rounded-full bg-muted-foreground"
        style={{ transition: INK_BASE_TRANSITION }}
      />
      {NAV_ITEMS.map((item, index) => {
        const active = index === activeIndex
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-label={item.label}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'relative flex h-[42px] min-w-0 flex-1 items-center justify-center',
              active ? 'text-foreground' : 'text-muted-foreground',
            )}
            style={{
              flexGrow: active ? activeGrow : 1,
              transition: 'flex-grow .34s cubic-bezier(.34,1.45,.5,1), color .25s',
            }}
          >
            <item.icon
              className={cn('size-6 flex-none', active ? 'scale-[1.02]' : 'scale-[.8]')}
              style={{ transition: 'transform .34s cubic-bezier(.34,1.55,.5,1)' }}
            />
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
                  'opacity .22s, transform .34s cubic-bezier(.34,1.45,.5,1), max-width .34s cubic-bezier(.34,1.45,.5,1), margin-left .34s cubic-bezier(.34,1.45,.5,1)',
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
