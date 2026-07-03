'use client'

import { useState } from 'react'
import { Plus } from 'lucide-react'
import { useAddIngredient } from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'

interface IngredientEditorProps {
  photoId: number
  onAdded: () => void
}

export function IngredientEditor({ photoId, onAdded }: IngredientEditorProps) {
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const addIngredient = useAddIngredient()

  const handleAdd = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    try {
      await addIngredient.mutateAsync({ photoId, name: trimmed })
      setName('')
      setAdding(false)
      onAdded()
    } catch (err) {
      handleMutationError(err, 'Failed to add ingredient')
    }
  }

  if (!adding) {
    return (
      <button
        type="button"
        onClick={() => setAdding(true)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <Plus className="size-3" />
        Add ingredient
      </button>
    )
  }

  return (
    <div className="flex items-center gap-1.5">
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleAdd()
          if (e.key === 'Escape') {
            setAdding(false)
            setName('')
          }
        }}
        placeholder="Ingredient name"
        autoFocus
        className="h-6 min-w-0 flex-1 rounded border border-border bg-background px-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <button
        type="button"
        onClick={handleAdd}
        disabled={addIngredient.isPending || !name.trim()}
        className="h-6 shrink-0 rounded bg-primary px-2 text-xs font-medium text-primary-foreground disabled:opacity-50"
      >
        Add
      </button>
      <button
        type="button"
        onClick={() => {
          setAdding(false)
          setName('')
        }}
        className="h-6 shrink-0 rounded px-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        Cancel
      </button>
    </div>
  )
}
