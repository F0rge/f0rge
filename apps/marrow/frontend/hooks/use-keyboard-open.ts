'use client'

import { useEffect, useState } from 'react'

const KEYBOARD_THRESHOLD_PX = 150

function getKeyboardOpen(): boolean {
  if (typeof window === 'undefined') return false

  const viewport = window.visualViewport
  if (!viewport) return false

  return window.innerHeight - viewport.height > KEYBOARD_THRESHOLD_PX
}

export function useKeyboardOpen(): boolean {
  const [keyboardOpen, setKeyboardOpen] = useState(false)

  useEffect(() => {
    const viewport = window.visualViewport
    if (!viewport) return

    const update = () => setKeyboardOpen(getKeyboardOpen())
    update()

    viewport.addEventListener('resize', update)
    viewport.addEventListener('scroll', update)

    return () => {
      viewport.removeEventListener('resize', update)
      viewport.removeEventListener('scroll', update)
    }
  }, [])

  return keyboardOpen
}
