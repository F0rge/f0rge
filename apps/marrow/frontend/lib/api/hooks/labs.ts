'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut, apiDelete, apiPostForm } from '@f0rge/ui/api'
import type { Lab, LabCreate, LabUpdate, LabMarkerCatalog, MarkerHistoryPoint, ExtractionResult } from '../types'

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
