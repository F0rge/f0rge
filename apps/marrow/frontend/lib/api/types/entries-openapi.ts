/**
 * OpenAPI-derived entry types — use in new code as codegen wiring expands.
 * Drift-checked against backend openapi.json in CI.
 */
import type { components } from '../generated/schema'

export type ApiEntry = components['schemas']['EntryResponse']
export type ApiEntryCreate = components['schemas']['EntryCreate']
export type ApiEntryStats = components['schemas']['EntryStatsResponse']
