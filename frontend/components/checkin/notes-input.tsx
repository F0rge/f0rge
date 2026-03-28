'use client'

import { useRef, useEffect } from 'react'

interface NotesInputProps {
  value: string
  onChange: (value: string) => void
}

export function NotesInput({ value, onChange }: NotesInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${el.scrollHeight}px`
    }
  }, [value])

  const remaining = 500 - value.length

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium leading-none">Notes (optional)</label>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => {
          if (e.target.value.length <= 500) {
            onChange(e.target.value)
          }
        }}
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
