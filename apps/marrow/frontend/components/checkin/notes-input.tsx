'use client'

import { useRef, useState, useEffect, useCallback } from 'react'
import { Field, FieldDescription, FieldTitle, Textarea } from '@f0rge/ui'
import { useFocusScrollIntoView } from '@/hooks/keyboard-viewport'
import { shouldHydrateNotesDraft } from '@/components/checkin/notes-input-sync'

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
  const onFocusScroll = useFocusScrollIntoView()
  const [draft, setDraft] = useState(value)
  const draftRef = useRef(value)
  const onChangeRef = useRef(onChange)
  const hasStartedRef = useRef(false)
  const prevParentValueRef = useRef(value)

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
    const next = draftRef.current
    onChangeRef.current(next)
    return next
  }, [])

  // Sync draft when parent value changes externally (entry hydration / date change).
  useEffect(() => {
    const prevParent = prevParentValueRef.current
    prevParentValueRef.current = value
    if (
      !shouldHydrateNotesDraft(
        hasStartedRef.current,
        draftRef.current,
        value,
        prevParent,
      )
    ) {
      return
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydration from server entry or external notes update
    setDraft(value)
    draftRef.current = value
    adjustHeight()
  }, [value, adjustHeight])

  useEffect(() => {
    registerDraftFlush?.(flushToParent)
    return () => {
      if (hasStartedRef.current) {
        flushToParent()
      }
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
    onChangeRef.current(next)
    adjustHeight()
  }

  const handleBlur = () => {
    if (!hasStartedRef.current) return
    const flushedNotes = flushToParent()
    onBlur?.(flushedNotes)
  }

  const remaining = 500 - draft.length

  return (
    <Field className="gap-3">
      <FieldTitle>Notes (optional)</FieldTitle>
      <Textarea
        ref={textareaRef}
        value={draft}
        onChange={handleChange}
        onFocus={onFocusScroll}
        onBlur={handleBlur}
        placeholder="Anything notable today... meals, events, how you felt"
        maxLength={500}
        rows={3}
        className="min-h-[80px] resize-none field-sizing-content"
      />
      <FieldDescription
        className={`text-right text-xs ${remaining < 50 ? 'text-destructive' : ''}`}
      >
        {remaining} characters remaining
      </FieldDescription>
    </Field>
  )
}
