const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
let accessToken: string | null = null
let supportSession: string | null = null
let refreshing: Promise<void> | null = null
const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('synapse-session') : null
channel?.addEventListener('message', () => clearSession(false))

export class ApiError extends Error {
  constructor(public code: string, public status: number) { super(code) }
}
export function clearSession(broadcast = true) {
  accessToken = null; supportSession = null
  if (broadcast) channel?.postMessage('session-changed')
  window.dispatchEvent(new Event('synapse-signed-out'))
}
export function setSupportSession(id: string | null) { supportSession = id }
async function authLock<T>(action: () => Promise<T>): Promise<T> {
  if (navigator.locks) return navigator.locks.request('synapse-auth-cookie', action)
  return action()
}
async function send(path: string, method = 'GET', body?: unknown): Promise<Response> {
  const headers: Record<string, string> = { 'X-Synapse-Client': 'web' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  if (supportSession) headers['X-Support-Session'] = supportSession
  return fetch(base + path, { method, headers, credentials: 'include',
    body: body === undefined ? undefined : JSON.stringify(body) })
}
async function result<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new ApiError(payload.error?.code || 'REQUEST_FAILED', response.status)
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}
export async function refreshSession() {
  if (!refreshing) refreshing = authLock(async () => {
    const token = await result<{ access_token: string }>(await send('/auth/refresh', 'POST'))
    accessToken = token.access_token
  }).finally(() => { refreshing = null })
  return refreshing
}
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response = await send(path, method, body)
  const expiredPasswordRequest = path === '/auth/password' && response.status === 401
    && (await response.clone().json().catch(() => ({}))).error?.code === 'INVALID_SESSION'
  if (response.status === 401 && (!path.startsWith('/auth/') || path === '/auth/me' || expiredPasswordRequest)) {
    try { await refreshSession(); response = await send(path, method, body) }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) clearSession()
      throw error
    }
  }
  return result<T>(response)
}
export async function signIn(email: string, password: string) {
  await authLock(async () => {
    const token = await result<{ access_token: string }>(await send('/auth/login', 'POST', { email, password }))
    accessToken = token.access_token; supportSession = null
    channel?.postMessage('session-changed')
  })
}
export async function signOut() {
  await authLock(async () => { await result(await send('/auth/logout', 'POST')); clearSession() })
}
export interface Membership { id: string; organization_id: string; organization_name: string; role: string; tenant_available: boolean }
export interface Profile { id: string; email: string; display_name: string | null; is_root_admin: boolean; membership: Membership | null }
export interface Organization { id: string; name: string; slug: string; is_active: boolean; is_public: boolean; registration_enabled: boolean }
export interface Member { id: string; user_id: string; email: string; display_name: string; role: string; is_active: boolean }
