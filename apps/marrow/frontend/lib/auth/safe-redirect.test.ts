import { describe, expect, it } from 'vitest'
import { resolvePostLoginRedirect } from './safe-redirect'

describe('resolvePostLoginRedirect', () => {
  it('defaults when redirect is missing or unsafe', () => {
    expect(resolvePostLoginRedirect(null)).toBe('/checkin')
    expect(resolvePostLoginRedirect('')).toBe('/checkin')
    expect(resolvePostLoginRedirect('//evil.com')).toBe('/checkin')
    expect(resolvePostLoginRedirect('https://evil.com')).toBe('/checkin')
    expect(resolvePostLoginRedirect('/settings')).toBe('/settings')
  })
})
