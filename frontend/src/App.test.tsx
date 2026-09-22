// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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
afterEach(cleanup)
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
    expect(await screen.findByRole('heading', { name: 'Chào mừng đến SynapseLMS' })).toBeInTheDocument()
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
