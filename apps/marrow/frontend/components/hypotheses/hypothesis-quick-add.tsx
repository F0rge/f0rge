'use client'

import { useState } from 'react'
import { Button } from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { TextInput } from '@f0rge/ui/forms'
import { useCreateHypothesis } from '@/lib/api/hooks'

function slugFromTitle(title: string): string {
  const slug = title
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 63)
  return slug
}

export function HypothesisQuickAdd() {
  const create = useCreateHypothesis()
  const [title, setTitle] = useState('')
  const [slug, setSlug] = useState('')
  const [slugTouched, setSlugTouched] = useState(false)

  function onTitleChange(value: string) {
    setTitle(value)
    if (!slugTouched) {
      setSlug(slugFromTitle(value))
    }
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmedTitle = title.trim()
    const trimmedSlug = (slugTouched ? slug : slugFromTitle(title)).trim()
    if (!trimmedTitle || !trimmedSlug) return
    try {
      await create.mutateAsync({ slug: trimmedSlug, title: trimmedTitle })
      setTitle('')
      setSlug('')
      setSlugTouched(false)
    } catch (err) {
      handleMutationError(err, 'Could not add hypothesis.')
    }
  }

  return (
    <form
      className="mx-auto w-full max-w-md space-y-2 rounded-xl border border-border bg-card p-4 text-left"
      onSubmit={(event) => {
        void onSubmit(event)
      }}
    >
      <TextInput
        required
        label="Title"
        value={title}
        onChange={(event) => onTitleChange(event.currentTarget.value)}
        placeholder="What are you testing?"
      />
      <TextInput
        required
        label="Slug"
        value={slug}
        onChange={(event) => {
          setSlugTouched(true)
          setSlug(event.currentTarget.value)
        }}
        placeholder="short-id"
        description="Lowercase letters, digits, and hyphens."
      />
      <Button type="submit" size="sm" disabled={create.isPending}>
        Add hypothesis
      </Button>
    </form>
  )
}
