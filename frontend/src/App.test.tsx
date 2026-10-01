// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import App from './App'
import { api, ApiError, signIn } from './api'

vi.mock('./api', () => ({
  api: vi.fn(), signIn: vi.fn(), signOut: vi.fn(), clearSession: vi.fn(), setSupportSession: vi.fn(),
  ApiError: class extends Error { constructor(public code: string, public status: number) { super(code) } },
}))
const profile = { id: 'u', email: 'student@example.com', display_name: 'Student', is_root_admin: false,
  membership: { id: 'm', organization_id: 'o', organization_name: 'Center', role: 'student', tenant_available: true } }
beforeEach(() => { vi.resetAllMocks() })
afterEach(() => { cleanup(); vi.useRealTimers() })
describe('authentication UI', () => {
  it('shows sign-in and switches language', async () => {
    vi.mocked(api).mockRejectedValue(new ApiError('INVALID_SESSION', 401))
    render(<MemoryRouter><App /></MemoryRouter>)
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'English' }))
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })
  it('signs in and does not expose member administration to a student', async () => {
    vi.mocked(api).mockRejectedValueOnce(new ApiError('INVALID_SESSION', 401)).mockResolvedValue(profile)
    vi.mocked(signIn).mockResolvedValue()
    render(<MemoryRouter><App /></MemoryRouter>)
    await screen.findByRole('heading', { name: 'Đăng nhập' })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'student@example.com' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'test-password-2026!' } })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByRole('heading', { name: /Chào mừng trở lại/ })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Thành viên' })).not.toBeInTheDocument()
    expect(signIn).toHaveBeenCalledWith('student@example.com', 'test-password-2026!')
  })
  it('reports invalid credentials without exposing server details', async () => {
    vi.mocked(api).mockRejectedValue(new ApiError('INVALID_SESSION', 401))
    vi.mocked(signIn).mockRejectedValue(new ApiError('INVALID_CREDENTIALS', 401))
    render(<MemoryRouter><App /></MemoryRouter>)
    await screen.findByRole('heading', { name: 'Đăng nhập' })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'wrong@example.com' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Email hoặc mật khẩu không đúng.')
  })
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(yes => { resolve = yes })
  return { promise, resolve }
}
async function loginForm() {
  await screen.findByRole('heading', { name: 'Đăng nhập' })
  fireEvent.change(screen.getByLabelText('Email', { exact: true }), { target: { value: 'student@example.com' } })
  fireEvent.change(screen.getByLabelText('Mật khẩu', { exact: true }), { target: { value: 'test-password-2026!' } })
  fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
}

it('ignores a late bootstrap response after signing out in another tab', async () => {
  const pending = deferred<typeof profile>()
  vi.mocked(api).mockReturnValue(pending.promise)
  render(<MemoryRouter><App /></MemoryRouter>)
  act(() => window.dispatchEvent(new Event('synapse-signed-out')))
  await screen.findByRole('heading', { name: 'Đăng nhập' })
  await act(async () => pending.resolve(profile))
  expect(screen.getByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
})

it('does not restore a login that finishes after a signed-out event', async () => {
  const pending = deferred<void>()
  vi.mocked(api).mockRejectedValue(new ApiError('INVALID_SESSION', 401))
  vi.mocked(signIn).mockReturnValue(pending.promise)
  render(<MemoryRouter><App /></MemoryRouter>)
  await loginForm()
  act(() => window.dispatchEvent(new Event('synapse-signed-out')))
  await act(async () => pending.resolve())
  expect(api).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
})

it('retries only the profile read after login succeeds and me fails', async () => {
  vi.mocked(api).mockRejectedValueOnce(new ApiError('INVALID_SESSION', 401)).mockRejectedValueOnce(new Error('offline')).mockResolvedValue(profile)
  vi.mocked(signIn).mockResolvedValue()
  render(<MemoryRouter><App /></MemoryRouter>)
  await loginForm()
  fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra phiên lại' }))
  await screen.findByRole('heading', { name: /Chào mừng trở lại/ })
  expect(signIn).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('button', { name: 'Đăng xuất' })).toBeEnabled()
})

it('rejects stale reads after returning to login and starting a new session', async () => {
  const old = deferred<typeof profile>()
  vi.mocked(api).mockReturnValueOnce(old.promise).mockResolvedValue(profile)
  vi.mocked(signIn).mockResolvedValue()
  render(<MemoryRouter><App /></MemoryRouter>)
  act(() => window.dispatchEvent(new Event('synapse-signed-out')))
  await loginForm()
  await screen.findByRole('heading', { name: /Chào mừng trở lại/ })
  await act(async () => old.resolve({ ...profile, display_name: 'Old user', is_root_admin: true }))
  expect(screen.queryByText('Old user')).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Trung tâm' })).not.toBeInTheDocument()
})

it('preserves the password-reset token through bootstrap and language changes', async () => {
  window.history.replaceState({}, '', '/account/reset-password#token=private-link-token')
  const pending = deferred<typeof profile>()
  vi.mocked(api).mockImplementation(path => path === '/auth/me' ? pending.promise : Promise.resolve({}))
  render(<MemoryRouter initialEntries={['/account/reset-password']}><App /></MemoryRouter>)
  expect(window.location.hash).toBe('')
  await act(async () => pending.resolve(profile))
  fireEvent.click(screen.getByRole('button', { name: 'English' }))
  fireEvent.change(screen.getByLabelText('New password', { exact: true }), { target: { value: 'new-password-2026!' } })
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'new-password-2026!' } })
  fireEvent.submit(screen.getByRole('button', { name: 'Reset password' }).closest('form')!)
  await waitFor(() => expect(api).toHaveBeenCalledWith('/auth/reset-password', 'POST', { token: 'private-link-token', password: 'new-password-2026!' }))
  window.history.replaceState({}, '', '/')
})

it('handles StrictMode bootstrap without auth mutations', async () => {
  vi.mocked(api).mockResolvedValue(profile)
  render(<StrictMode><MemoryRouter><App /></MemoryRouter></StrictMode>)
  await screen.findByRole('heading', { name: /Chào mừng trở lại/ })
  expect(signIn).not.toHaveBeenCalled()
  expect(vi.mocked(api).mock.calls.every(([, method]) => !method || method === 'GET')).toBe(true)
})

it('lets a slow profile retry finish without a late response replacing it', async () => {
  vi.useFakeTimers()
  const old = deferred<typeof profile>()
  vi.mocked(api).mockReturnValueOnce(old.promise).mockResolvedValue(profile)
  render(<MemoryRouter><App /></MemoryRouter>)
  await act(async () => vi.advanceTimersByTime(15000))
  fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra phiên lại' }))
  await act(async () => { await Promise.resolve() })
  await act(async () => vi.advanceTimersByTime(180))
  expect(screen.getByRole('heading', { name: /Chào mừng trở lại/ })).toBeVisible()
  await act(async () => old.resolve({ ...profile, is_root_admin: true, display_name: 'Stale root' }))
  expect(screen.queryByText('Stale root')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Đăng xuất' })).toBeEnabled()
  expect(signIn).not.toHaveBeenCalled()
})

it.each(['student', 'teacher', 'staff', 'organization_manager', 'root', 'none', 'unavailable'])('uses the server role without a role selector: %s', async role => {
  vi.mocked(api).mockResolvedValue({ ...profile, is_root_admin: role === 'root', membership: role === 'none' || role === 'root' ? null : { ...profile.membership, role: role === 'unavailable' ? 'student' : role, tenant_available: role !== 'unavailable' } })
  render(<MemoryRouter><App /></MemoryRouter>)
  await screen.findByRole('heading', { name: /Chào mừng trở lại/ })
  const admin = ['staff', 'organization_manager'].includes(role)
  expect(!!screen.queryByRole('link', { name: 'Học viên' })).toBe(admin)
  expect(screen.queryAllByRole('link', { name: 'Trung tâm' }).length > 0).toBe(role === 'root')
})
