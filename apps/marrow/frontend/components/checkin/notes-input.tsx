'use client'

import { useRef, useState, useEffect, useCallback } from 'react'
import { Label } from '@f0rge/ui'

const SYNC_DEBOUNCE_MS = 500

interface NotesInputProps {
  value: string
  onChange: (value: string) => void
  onEditStart?: () => void
  onBlur?: (flushedNotes: string) => void
  registerDraftFlush?: (flush: () => string) => void
}

export function NotesInput({
  value,
  onChange,
  onEditStart,
  onBlur,
  registerDraftFlush,
}: NotesInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [draft, setDraft] = useState(value)
  const draftRef = useRef(value)
  const onChangeRef = useRef(onChange)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasStartedRef = useRef(false)

  useEffect(() => {
    onChangeRef.current = onChange
  }, [onChange])

  const adjustHeight = useCallback(() => {
    requestAnimationFrame(() => {
      const el = textareaRef.current
      if (el) {
        el.style.height = 'auto'
        el.style.height = `${el.scrollHeight}px`
      }
    })
  }, [])

  const flushToParent = useCallback((): string => {
    if (debounceTimerRef.current !== null) {
      clearTimeout(debounceTimerRef.current)
      debounceTimerRef.current = null
    }
    const next = draftRef.current
    onChangeRef.current(next)
    return next
  }, [])

  const scheduleSync = useCallback((next: string) => {
    if (debounceTimerRef.current !== null) {
      clearTimeout(debounceTimerRef.current)
    }
    debounceTimerRef.current = setTimeout(() => {
      debounceTimerRef.current = null
      onChangeRef.current(next)
    }, SYNC_DEBOUNCE_MS)
  }, [])

  // Sync draft when parent value changes externally (entry load / date change).
  useEffect(() => {
    if (draftRef.current !== value && debounceTimerRef.current === null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- hydration from server entry only when not mid-typing
      setDraft(value)
      draftRef.current = value
      hasStartedRef.current = false
      adjustHeight()
    }
  }, [value, adjustHeight])

  useEffect(() => {
    registerDraftFlush?.(flushToParent)
    return () => {
      flushToParent()
      registerDraftFlush?.(() => '')
    }
  }, [registerDraftFlush, flushToParent])

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const next = e.target.value
    if (next.length > 500) return

    if (!hasStartedRef.current) {
      hasStartedRef.current = true
      onEditStart?.()
    }

    setDraft(next)
    draftRef.current = next
    scheduleSync(next)
    adjustHeight()
  }

  const handleBlur = () => {
    const flushedNotes = flushToParent()
    onBlur?.(flushedNotes)
  }

  const remaining = 500 - draft.length

  return (
    <div className="space-y-3">
      <Label className="text-sm font-medium leading-none">Notes (optional)</Label>
      <textarea
        ref={textareaRef}
        value={draft}
        onChange={handleChange}
        onBlur={handleBlur}
        placeholder="Anything notable today... meals, events, how you felt"
        className="w-full min-h-[80px] resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        rows={3}
      />
      <p className={`text-xs text-right ${remaining < 50 ? 'text-destructive' : 'text-muted-foreground'}`}>
        {remaining} characters remaining
      </p>
    </div>
  )
}
