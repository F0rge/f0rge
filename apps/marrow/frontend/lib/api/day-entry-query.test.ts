import { QueryClient, QueryObserver, focusManager } from '@tanstack/react-query'
import { afterEach, describe, expect, it } from 'vitest'
import { bindDocumentReturnEvents, dayEntryRefetchOptions } from './day-entry-query'

const DATE = '2026-10-17'
const STALE_MS = 60_000

function appQueryClient() {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: STALE_MS,
        refetchOnWindowFocus: false,
        retry: false,
      },
    },
  })
  client.mount()
  return client
}

function age(client: QueryClient, queryKey: readonly unknown[]) {
  const query = client.getQueryCache().find({ queryKey })
  if (!query) throw new Error(`missing query ${JSON.stringify(queryKey)}`)
  query.setState({ dataUpdatedAt: Date.now() - STALE_MS - 1_000 })
}

async function settled() {
  await new Promise((resolve) => setTimeout(resolve, 20))
}

describe('bindDocumentReturnEvents', () => {
  it('notifies on visibility and window focus, and unsubscribes', () => {
    const listeners = new Map<string, Set<() => void>>()
    const target = {
      addEventListener(type: string, listener: () => void) {
        const set = listeners.get(type) ?? new Set()
        set.add(listener)
        listeners.set(type, set)
      },
      removeEventListener(type: string, listener: () => void) {
        listeners.get(type)?.delete(listener)
      },
    }
    let calls = 0
    const unbind = bindDocumentReturnEvents(() => {
      calls += 1
    }, target)

    listeners.get('visibilitychange')?.forEach((listener) => listener())
    listeners.get('focus')?.forEach((listener) => listener())
    expect(calls).toBe(2)

    unbind()
    listeners.get('focus')?.forEach((listener) => listener())
    expect(calls).toBe(2)
  })
})

describe('day entry refetch', () => {
  afterEach(() => {
    focusManager.setFocused(undefined)
  })

  it('refetches a stale day when the window regains focus and skips a fresh one', async () => {
    let calls = 0
    const client = appQueryClient()
    const observer = new QueryObserver(client, {
      queryKey: ['entry', DATE],
      queryFn: async () => {
        calls += 1
        return { photos: [{ id: calls }] }
      },
      ...dayEntryRefetchOptions,
    })
    const unsubscribe = observer.subscribe(() => {})
    await settled()
    expect(calls).toBe(1)

    focusManager.setFocused(false)
    focusManager.setFocused(true)
    await settled()
    expect(calls).toBe(1)

    age(client, ['entry', DATE])
    focusManager.setFocused(false)
    focusManager.setFocused(true)
    await settled()
    expect(calls).toBe(2)
    expect(client.getQueryData(['entry', DATE])).toEqual({ photos: [{ id: 2 }] })

    unsubscribe()
    client.unmount()
    client.clear()
  })

  it('refetches a stale prefetched day on mount and reuses a fresh prefetch', async () => {
    let calls = 0
    const client = appQueryClient()
    const queryFn = async () => {
      calls += 1
      return { photos: [{ id: calls }] }
    }

    await client.prefetchQuery({ queryKey: ['entry', DATE], queryFn, staleTime: STALE_MS })
    expect(calls).toBe(1)

    const fresh = new QueryObserver(client, {
      queryKey: ['entry', DATE],
      queryFn,
      ...dayEntryRefetchOptions,
    })
    const unsubFresh = fresh.subscribe(() => {})
    await settled()
    expect(calls).toBe(1)
    unsubFresh()

    // Unsubscribing drops the cache entry. Seed it again the way warmup would,
    // already older than staleTime, then mount the check-in observer.
    client.setQueryData(['entry', DATE], { photos: [{ id: 1 }] }, {
      updatedAt: Date.now() - STALE_MS - 1_000,
    })
    const stale = new QueryObserver(client, {
      queryKey: ['entry', DATE],
      queryFn,
      ...dayEntryRefetchOptions,
    })
    const unsubStale = stale.subscribe(() => {})
    await settled()
    expect(calls).toBe(2)

    unsubStale()
    client.unmount()
    client.clear()
  })

  it('leaves an unrelated query on the global focus default', async () => {
    let entryCalls = 0
    let statsCalls = 0
    const client = appQueryClient()
    const entry = new QueryObserver(client, {
      queryKey: ['entry', DATE],
      queryFn: async () => {
        entryCalls += 1
        return { photos: [] }
      },
      ...dayEntryRefetchOptions,
    })
    const stats = new QueryObserver(client, {
      queryKey: ['entries', 'stats'],
      queryFn: async () => {
        statsCalls += 1
        return { days: 1 }
      },
    })
    const unsubEntry = entry.subscribe(() => {})
    const unsubStats = stats.subscribe(() => {})
    await settled()
    expect(entryCalls).toBe(1)
    expect(statsCalls).toBe(1)

    age(client, ['entry', DATE])
    age(client, ['entries', 'stats'])
    focusManager.setFocused(false)
    focusManager.setFocused(true)
    await settled()

    expect(entryCalls).toBe(2)
    expect(statsCalls).toBe(1)

    unsubEntry()
    unsubStats()
    client.unmount()
    client.clear()
  })
})
