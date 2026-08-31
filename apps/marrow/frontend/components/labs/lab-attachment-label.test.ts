import { describe, expect, it } from 'vitest'
import { humanSourceFilename } from './lab-attachment-label'

describe('humanSourceFilename', () => {
  it('returns null when the path is missing', () => {
    expect(humanSourceFilename(null)).toBeNull()
    expect(humanSourceFilename(undefined)).toBeNull()
    expect(humanSourceFilename('')).toBeNull()
    expect(humanSourceFilename('   ')).toBeNull()
  })

  it('hides upload content hashes', () => {
    expect(humanSourceFilename(`upload:${'a'.repeat(64)}`)).toBeNull()
  })

  it('hides bare storage keys and content-addressed files', () => {
    expect(
      humanSourceFilename('872ba02b5c6796750a79b70bdc8749576ef6f734567294'),
    ).toBeNull()
    expect(
      humanSourceFilename(`lab_attachments/2026-08/${'ab'.repeat(32)}.png`),
    ).toBeNull()
  })

  it('keeps a real original filename from source_path', () => {
    expect(humanSourceFilename('labs/blood-panel-aug.pdf')).toBe(
      'blood-panel-aug.pdf',
    )
    expect(humanSourceFilename('labs/lab_blood.md')).toBe('lab_blood.md')
  })
})
