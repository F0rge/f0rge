'use client'

import { useState, useCallback, useEffect } from 'react'
import { Delete, Check } from 'lucide-react'

interface PinPadProps {
  onSubmit: (pin: string) => void
  error?: boolean
  loading?: boolean
  pinLength?: number
}

export function PinPad({ onSubmit, error = false, loading = false, pinLength = 4 }: PinPadProps) {
  const [pin, setPin] = useState('')
  // Shake is seeded from `error` on mount via the useState initializer (no setState
  // inside the effect body). The parent bumps `key` on each error so this component
  // remounts and the initializer re-runs with the new error value.
  const [shake, setShake] = useState(error)

  useEffect(() => {
    if (!shake) return
    const timer = setTimeout(() => {
      setShake(false)
      setPin('')
    }, 500)
    return () => clearTimeout(timer)
  }, [shake])

  const addDigit = useCallback(
    (digit: string) => {
      if (loading) return
      setPin((prev) => {
        const next = prev + digit
        if (next.length === pinLength) {
          setTimeout(() => onSubmit(next), 100)
        }
        return next.length <= pinLength ? next : prev
      })
    },
    [loading, pinLength, onSubmit]
  )

  const removeDigit = useCallback(() => {
    if (loading) return
    setPin((prev) => prev.slice(0, -1))
  }, [loading])

  const handleSubmit = useCallback(() => {
    if (pin.length === pinLength && !loading) {
      onSubmit(pin)
    }
  }, [pin, pinLength, loading, onSubmit])

  const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'back', '0', 'submit']

  return (
    <div className="flex flex-col items-center gap-8">
      <div
        className={`flex gap-3 ${shake ? 'animate-shake' : ''}`}
      >
        {Array.from({ length: pinLength }).map((_, i) => (
          <div
            key={i}
            className={`size-4 rounded-full transition-colors duration-200 ${
              i < pin.length
                ? 'bg-foreground'
                : 'border-2 border-muted-foreground/40'
            }`}
          />
        ))}
      </div>

      {error && (
        <p className="text-sm text-destructive">Wrong PIN. Try again.</p>
      )}

      <div className="grid grid-cols-3 gap-3">
        {keys.map((key) => {
          if (key === 'back') {
            return (
              <button
                key={key}
                type="button"
                onClick={removeDigit}
                disabled={loading || pin.length === 0}
                className="flex size-16 items-center justify-center rounded-full text-muted-foreground transition-colors active:bg-muted disabled:opacity-30"
              >
                <Delete className="size-6" />
              </button>
            )
          }
          if (key === 'submit') {
            return (
              <button
                key={key}
                type="button"
                onClick={handleSubmit}
                disabled={loading || pin.length !== pinLength}
                className="flex size-16 items-center justify-center rounded-full text-muted-foreground transition-colors active:bg-muted disabled:opacity-30"
              >
                <Check className="size-6" />
              </button>
            )
          }
          return (
            <button
              key={key}
              type="button"
              onClick={() => addDigit(key)}
              disabled={loading}
              className="flex size-16 items-center justify-center rounded-full text-xl font-medium transition-colors active:bg-muted disabled:opacity-50"
            >
              {key}
            </button>
          )
        })}
      </div>
    </div>
  )
}
