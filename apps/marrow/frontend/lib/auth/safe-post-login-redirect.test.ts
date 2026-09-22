import { describe, expect, it } from 'vitest'
import { safePostLoginRedirect } from './safe-post-login-redirect'

describe('safePostLoginRedirect', () => {
  it('uses fallback when redirect is missing or empty', () => {
    expect(safePostLoginRedirect(null)).toBe('/checkin')
    expect(safePostLoginRedirect(undefined)).toBe('/checkin')
    expect(safePostLoginRedirect('')).toBe('/checkin')
  })

  it('allows single-slash relative paths', () => {
    expect(safePostLoginRedirect('/checkin')).toBe('/checkin')
    expect(safePostLoginRedirect('/customize/trackers')).toBe('/customize/trackers')
    expect(safePostLoginRedirect('/checkin?tab=food')).toBe('/checkin?tab=food')
  })

  it('rejects protocol-relative, absolute, and scheme URLs', () => {
    expect(safePostLoginRedirect('//evil.example/phish')).toBe('/checkin')
    expect(safePostLoginRedirect('https://evil.example')).toBe('/checkin')
    expect(safePostLoginRedirect('http://evil.example')).toBe('/checkin')
    expect(safePostLoginRedirect('javascript:alert(1)')).toBe('/checkin')
  })

  it('rejects paths without a leading slash', () => {
    expect(safePostLoginRedirect('checkin')).toBe('/checkin')
    expect(safePostLoginRedirect('evil.example')).toBe('/checkin')
  })
})
