'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiGet,
  apiPost,
  apiPut,
  apiPatch,
  apiDelete,
  apiPostForm,
  ApiError,
} from './client'
import type {
  Entry,
  EntryCreate,
  AuthUser,
  WeatherDailySummary,
  HealthMetricResponse,
  EnrichedDayResponse,
  SupplementCatalogItem,
  SymptomCatalogItem,
  PhotoAnalysis,
  Treatment,
  TreatmentCreate,
  TreatmentUpdate,
  TrendsResponse,
  CorrelatesResponse,
  TreatmentResponseList,
  SleepNextDayResponse,
  Lab,
  LabCreate,
  LabUpdate,
  LabMarkerCatalog,
  MarkerHistoryPoint,
  ExtractionResult,
  UserSettings,
  LLMSettingsUpdate,
  EmbeddingSettingsUpdate,
  TestConnectionResponse,
  ExternalTokenResponse,
  Tracker,
  TrackerValue,
  TrackerCreate,
  TrackerUpdate,
} from './types'

export function useAuth() {
  return useQuery<AuthUser>({
    queryKey: ['auth'],
    queryFn: () => apiGet('/auth/me'),
    retry: false,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (pin: string) => apiPost('/auth/login', { pin }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth'] })
    },
  })
}

export function useEntries(month?: string) {
  const params = month ? `?month=${month}` : ''
  return useQuery<Entry[]>({
    queryKey: ['entries', month ?? 'all'],
    queryFn: () => apiGet(`/entries${params}`),
  })
}

export function useEntry(date: string) {
  return useQuery<Entry>({
    queryKey: ['entry', date],
    queryFn: () => apiGet(`/entries/${date}`),
    enabled: !!date,
    retry: false,
  })
}

export function useCreateEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: EntryCreate) => apiPost('/entries', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useUpdateEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ date, data }: { date: string; data: EntryCreate }) =>
      apiPut(`/entries/${date}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useDeleteEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (date: string) => apiDelete(`/entries/${date}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useUploadPhoto() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      date,
      file,
      label,
      mealTime,
    }: {
      date: string
      file: File
      label?: string
      mealTime?: Date | null
    }) => {
      const formData = new FormData()
      formData.append('file', file)
      if (label) formData.append('label', label)
      if (mealTime) formData.append('meal_time', mealTime.toISOString())
      return apiPostForm(`/entries/${date}/photos`, formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })
}

export function useDeletePhoto() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/photos/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })
}

export function useWeatherSummary(date: string) {
  return useQuery<WeatherDailySummary>({
    queryKey: ['weather', date],
    queryFn: () => apiGet(`/weather/${date}`),
    enabled: !!date,
    retry: false,
  })
}

export function useHealthMetrics(date: string) {
  return useQuery<HealthMetricResponse>({
    queryKey: ['health-metrics', date],
    queryFn: () => apiGet(`/health-metrics/${date}`),
    enabled: !!date,
    retry: false,
  })
}

export function useEnrichedDay(date: string) {
  return useQuery<EnrichedDayResponse>({
    queryKey: ['enriched', date],
    queryFn: () => apiGet(`/enriched/${date}`),
    enabled: !!date,
    retry: false,
  })
}

export function useSupplementCatalog(includeArchived = false) {
  const params = includeArchived ? '?include_archived=true' : ''
  return useQuery<SupplementCatalogItem[]>({
    queryKey: ['supplement-catalog', includeArchived],
    queryFn: () => apiGet(`/supplements/catalog${params}`),
  })
}

export function useAddSupplementCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { key: string; label: string }) =>
      apiPost('/supplements/catalog', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supplement-catalog'] })
    },
  })
}

export function useUpdateSupplementCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      key,
      data,
    }: {
      key: string
      data: { label?: string; archived?: boolean; sort_order?: number }
    }) => apiPatch(`/supplements/catalog/${key}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supplement-catalog'] })
    },
  })
}

export function useSymptomCatalog(includeArchived = false) {
  const params = includeArchived ? '?include_archived=true' : ''
  return useQuery<SymptomCatalogItem[]>({
    queryKey: ['symptom-catalog', includeArchived],
    queryFn: () => apiGet(`/symptoms/catalog${params}`),
  })
}

export function useAddSymptomCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { key: string; label: string }) =>
      apiPost('/symptoms/catalog', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['symptom-catalog'] })
    },
  })
}

export function useUpdateSymptomCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      key,
      data,
    }: {
      key: string
      data: { label?: string; archived?: boolean; sort_order?: number }
    }) => apiPatch(`/symptoms/catalog/${key}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['symptom-catalog'] })
    },
  })
}

export function useTriggerWeatherFetch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost('/weather/fetch', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['weather'] })
      queryClient.invalidateQueries({ queryKey: ['enriched'] })
    },
  })
}

export function usePhotoAnalysis(photoId: number | null) {
  return useQuery<PhotoAnalysis | null>({
    queryKey: ['photo-analysis', photoId],
    queryFn: async () => {
      try {
        return await apiGet(`/photos/${photoId}/analysis`)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          return null
        }
        throw err
      }
    },
    enabled: photoId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'pending' || status === 'analyzing') {
        return 2000
      }
      return false
    },
  })
}

export function useConfirmAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (photoId: number) => apiPut(`/photos/${photoId}/analysis/confirm`, {}),
    onSuccess: (_data, photoId) => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis', photoId] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useRetryAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (photoId: number) => apiPut(`/photos/${photoId}/analysis/retry`, {}),
    onSuccess: (_data, photoId) => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis', photoId] })
    },
  })
}

export function useUpdateIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ ingredientId, data }: { ingredientId: number; data: Record<string, unknown> }) =>
      apiPut(`/ingredients/${ingredientId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useAddIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, name }: { photoId: number; name: string }) =>
      apiPost(`/photos/${photoId}/analysis/ingredients`, { name }),
    onSuccess: (_data, { photoId }) => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis', photoId] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useDeleteIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ingredientId: number) => apiDelete(`/ingredients/${ingredientId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useTreatments(activeOn?: string) {
  const params = activeOn ? `?active_on=${activeOn}` : ''
  return useQuery<Treatment[]>({
    queryKey: ['treatments', activeOn ?? 'all'],
    queryFn: () => apiGet(`/treatments${params}`),
  })
}

export function useTreatment(id: number | null) {
  return useQuery<Treatment>({
    queryKey: ['treatment', id],
    queryFn: () => apiGet(`/treatments/${id}`),
    enabled: id !== null,
  })
}

export function useCreateTreatment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: TreatmentCreate) => apiPost('/treatments', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['treatments'] })
    },
  })
}

export function useUpdateTreatment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TreatmentUpdate }) =>
      apiPut(`/treatments/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['treatments'] })
      queryClient.invalidateQueries({ queryKey: ['treatment'] })
    },
  })
}

export function useDeleteTreatment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/treatments/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['treatments'] })
      queryClient.invalidateQueries({ queryKey: ['treatment'] })
    },
  })
}

export function useUpdatePhotoMealTime() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, mealTime }: { photoId: number; mealTime: string }) =>
      apiPatch(`/photos/${photoId}`, { meal_time: mealTime }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })
}

// ── Insights hooks ─────────────────────────────────────────────────────────────

export function useInsightsTrends(start: string, end: string) {
  return useQuery<TrendsResponse>({
    queryKey: ['insights-trends', start, end],
    queryFn: () => apiGet(`/insights/trends?start=${start}&end=${end}`),
    enabled: !!start && !!end,
  })
}

export function useInsightsCorrelates(
  outcome: string,
  start: string,
  end: string,
  category?: string,
) {
  const params = new URLSearchParams({ outcome, start, end, min_n: '10' })
  if (category && category !== 'all') params.set('category', category)
  return useQuery<CorrelatesResponse>({
    queryKey: ['insights-correlates', outcome, start, end, category ?? 'all'],
    queryFn: () => apiGet(`/insights/correlates?${params.toString()}`),
    enabled: !!outcome && !!start && !!end,
  })
}

export function useInsightsTreatmentResponse(outcome: string) {
  return useQuery<TreatmentResponseList>({
    queryKey: ['insights-treatment-response', outcome],
    queryFn: () => apiGet(`/insights/treatment-response?outcome=${outcome}`),
    enabled: !!outcome,
  })
}

export function useInsightsSleepNextDay(
  outcome: string,
  metric: string,
  start: string,
  end: string,
) {
  return useQuery<SleepNextDayResponse>({
    queryKey: ['insights-sleep-next-day', outcome, metric, start, end],
    queryFn: () =>
      apiGet(
        `/insights/sleep-next-day?outcome=${outcome}&metric=${metric}&start=${start}&end=${end}`,
      ),
    enabled: !!outcome && !!metric && !!start && !!end,
  })
}

// ── Labs hooks ─────────────────────────────────────────────────────────────────

export function useLabs(filters?: { start_date?: string; end_date?: string; type?: string }) {
  const params = new URLSearchParams()
  if (filters?.start_date) params.set('start_date', filters.start_date)
  if (filters?.end_date) params.set('end_date', filters.end_date)
  if (filters?.type) params.set('type', filters.type)
  const qs = params.toString()
  return useQuery<Lab[]>({
    queryKey: ['labs', filters ?? 'all'],
    queryFn: () => apiGet(`/labs${qs ? `?${qs}` : ''}`),
  })
}

export function useLab(id: number | null) {
  return useQuery<Lab>({
    queryKey: ['lab', id],
    queryFn: () => apiGet(`/labs/${id}`),
    enabled: id !== null,
  })
}

export function useCreateLab() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: LabCreate) => apiPost('/labs', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['labs'] })
    },
  })
}

export function useUpdateLab() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: LabUpdate }) =>
      apiPut(`/labs/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['labs'] })
      queryClient.invalidateQueries({ queryKey: ['lab'] })
    },
  })
}

export function useDeleteLab() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/labs/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['labs'] })
      queryClient.invalidateQueries({ queryKey: ['lab'] })
    },
  })
}

export function useMarkerCatalog(q?: string) {
  const params = q ? `?q=${encodeURIComponent(q)}&limit=500` : '?limit=500'
  return useQuery<LabMarkerCatalog[]>({
    queryKey: ['marker-catalog', q ?? ''],
    queryFn: () => apiGet(`/lab-markers/catalog${params}`),
  })
}

export function useMarkerHistory(canonicalName: string | null) {
  return useQuery<MarkerHistoryPoint[]>({
    queryKey: ['marker-history', canonicalName],
    queryFn: () => apiGet(`/lab-markers/${encodeURIComponent(canonicalName!)}/history`),
    enabled: !!canonicalName,
  })
}

export function useCreateMarker() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { canonical_name: string; display_name: string; common_units?: string[] }) =>
      apiPost('/lab-markers/catalog', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marker-catalog'] })
    },
  })
}

export function useAddAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ catalogId, alias, language }: { catalogId: number; alias: string; language?: string }) =>
      apiPost(`/lab-markers/catalog/${catalogId}/aliases`, { alias, language }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marker-catalog'] })
    },
  })
}

export function useExtractLabText() {
  return useMutation({
    mutationFn: (documentText: string) =>
      apiPost('/labs/extract', { document_text: documentText }) as Promise<ExtractionResult>,
  })
}

export function useExtractLabUpload() {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return apiPostForm('/labs/extract-upload', formData) as Promise<ExtractionResult>
    },
  })
}

// ── Settings hooks ─────────────────────────────────────────────────────────────

export function useUserSettings() {
  return useQuery<UserSettings>({
    queryKey: ['settings'],
    queryFn: () => apiGet('/settings'),
  })
}

export function useUpdateLLMSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: LLMSettingsUpdate) => apiPut('/settings/llm', data) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useUpdateEmbeddingSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: EmbeddingSettingsUpdate) =>
      apiPut('/settings/embedding', data) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useTestLLMConnection() {
  return useMutation({
    mutationFn: () => apiPost('/settings/llm/test', {}) as Promise<TestConnectionResponse>,
  })
}

export function useTestEmbeddingConnection() {
  return useMutation({
    mutationFn: () =>
      apiPost('/settings/embedding/test', {}) as Promise<TestConnectionResponse>,
  })
}

export function useRegenerateExternalToken() {
  const queryClient = useQueryClient()
  return useMutation<ExternalTokenResponse, ApiError, void>({
    mutationFn: () => apiPost('/settings/external-token/regenerate', {}) as Promise<ExternalTokenResponse>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useRevokeExternalToken() {
  const queryClient = useQueryClient()
  return useMutation<UserSettings, ApiError, void>({
    mutationFn: () => apiPost('/settings/external-token/revoke', {}) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useImportLabText() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ text, sourcePath, force }: { text: string; sourcePath?: string; force?: boolean }) =>
      apiPost('/labs/import', { document_text: text, source_path: sourcePath, force }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['labs'] })
    },
  })
}

export function useImportLabUpload() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ file, force }: { file: File; force?: boolean }) => {
      const formData = new FormData()
      formData.append('file', file)
      if (force) formData.append('force', 'true')
      return apiPostForm('/labs/import-upload', formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['labs'] })
    },
  })
}

// ── Tracker hooks ──────────────────────────────────────────────────────────────

export function useTrackers(includeArchived = false) {
  const params = includeArchived ? '?include_archived=true' : ''
  return useQuery<Tracker[]>({
    queryKey: ['trackers', includeArchived],
    queryFn: () => apiGet(`/trackers${params}`),
  })
}

export function useCreateTracker() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: TrackerCreate) => apiPost('/trackers', data) as Promise<Tracker>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trackers'] })
    },
  })
}

export function useUpdateTracker() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TrackerUpdate }) =>
      apiPatch(`/trackers/${id}`, data) as Promise<Tracker>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trackers'] })
    },
  })
}

export function useReorderTrackers() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (order: number[]) => apiPatch('/trackers/reorder', { order }),
    onMutate: async (order: number[]) => {
      // Optimistically reorder customs so the dragged row settles in its new slot
      // immediately, instead of snapping back during the PATCH round-trip.
      await queryClient.cancelQueries({ queryKey: ['trackers'] })
      const snapshots: { key: readonly unknown[]; data: Tracker[] | undefined }[] = []
      const queries = queryClient.getQueriesData<Tracker[]>({ queryKey: ['trackers'] })
      for (const [key, data] of queries) {
        snapshots.push({ key, data })
        if (!data) continue
        const byId = new Map(data.map((t) => [t.id, t]))
        const reordered = order
          .map((id) => byId.get(id))
          .filter((t): t is Tracker => t !== undefined)
        const remaining = data.filter((t) => !order.includes(t.id))
        queryClient.setQueryData<Tracker[]>(key, [...remaining, ...reordered])
      }
      return { snapshots }
    },
    onError: (_err, _order, context) => {
      context?.snapshots.forEach(({ key, data }) => queryClient.setQueryData(key, data))
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['trackers'] }),
  })
}

export function useEntryTrackerValues(date: string) {
  return useQuery<TrackerValue[]>({
    queryKey: ['tracker-values', date],
    queryFn: () => apiGet(`/entries/${date}/tracker_values`),
    enabled: !!date,
  })
}

export function useUpsertTrackerValue(date: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ trackerId, value }: { trackerId: number; value: number }) =>
      apiPut(`/entries/${date}/tracker_values/${trackerId}`, { value }) as Promise<TrackerValue>,
    onMutate: async ({ trackerId, value }) => {
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: ['tracker-values', date] })
      const prev = queryClient.getQueryData<TrackerValue[]>(['tracker-values', date])
      queryClient.setQueryData<TrackerValue[]>(['tracker-values', date], (old = []) => {
        const exists = old.find((tv) => tv.tracker_id === trackerId)
        if (exists) {
          return old.map((tv) =>
            tv.tracker_id === trackerId ? { ...tv, value } : tv,
          )
        }
        return [
          ...old,
          { tracker_id: trackerId, date, value, updated_at: new Date().toISOString() },
        ]
      })
      return { prev }
    },
    onError: (_err, _vars, context) => {
      if (context?.prev !== undefined) {
        queryClient.setQueryData(['tracker-values', date], context.prev)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['tracker-values', date] })
    },
  })
}
