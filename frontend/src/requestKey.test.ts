// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { createRequestKey, optionalRequestKey, RequestKeyUnavailableError } from './requestKey'

afterEach(() => vi.unstubAllGlobals())

it('uses native randomUUID when available', () => {
  const randomUUID = vi.fn(() => 'c4f39527-b1c1-41ec-96d4-862373cba402')
  const getRandomValues = vi.fn()
  vi.stubGlobal('crypto', { randomUUID, getRandomValues })
  expect(createRequestKey()).toBe('c4f39527-b1c1-41ec-96d4-862373cba402')
  expect(randomUUID).toHaveBeenCalledOnce()
  expect(getRandomValues).not.toHaveBeenCalled()
})

it('uses cryptographically random bytes with RFC 4122 version and variant on HTTP', () => {
  let call = 0
  vi.stubGlobal('crypto', { getRandomValues: (bytes: Uint8Array) => { bytes.fill(call++); return bytes } })
  const first = createRequestKey()
  const second = createRequestKey()
  expect(first).toBe('00000000-0000-4000-8000-000000000000')
  expect(second).toBe('01010101-0101-4101-8101-010101010101')
  expect(first).not.toBe(second)
  expect(first).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
})

it('fails locally without either secure random API', () => {
  vi.stubGlobal('crypto', {})
  expect(createRequestKey).toThrow(RequestKeyUnavailableError)
  expect(optionalRequestKey()).toBeNull()
})
