import { ApiError } from './api'

export class RequestKeyUnavailableError extends Error {
  readonly code = 'REQUEST_KEY_UNAVAILABLE'

  constructor() {
    super('A secure random number generator is unavailable in this browser.')
  }
}

export function createRequestKey(): string {
  const source = globalThis.crypto
  if (typeof source?.randomUUID === 'function') return source.randomUUID()
  if (typeof source?.getRandomValues !== 'function') throw new RequestKeyUnavailableError()

  const bytes = source.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function optionalRequestKey(): string | null {
  try { return createRequestKey() }
  catch (error) {
    if (error instanceof RequestKeyUnavailableError) return null
    throw error
  }
}

export function requestErrorCode(error: unknown, fallback = 'REQUEST_FAILED'): string {
  return error instanceof RequestKeyUnavailableError || error instanceof ApiError ? error.code : fallback
}
