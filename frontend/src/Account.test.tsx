// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AccountAction, EmailRequestForm, Sessions } from './Account'
import { api } from './api'

vi.mock('./api', () => ({ api: vi.fn(), clearSession: vi.fn(),
  ApiError: class extends Error { constructor(public code: string, public status: number) { super(code) } },
}))
beforeEach(() => { vi.resetAllMocks(); window.history.replaceState(null, '', '/') })
afterEach(cleanup)

it('keeps email tokens out of the URL and waits for explicit confirmation', async () => {
  window.history.replaceState(null, '', '/account/verify-email#token=test-secret-link')
  vi.mocked(api).mockResolvedValue(undefined)
  render(<AccountAction language="en" reset={false} />)
  expect(window.location.hash).toBe('')
  expect(api).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Verify email' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Email verified.')
  expect(api).toHaveBeenCalledWith('/auth/verify-email', 'POST', { token: 'test-secret-link' })
})

it('rejects mismatched reset passwords before submitting', () => {
  window.history.replaceState(null, '', '/account/reset-password#token=test-secret-link')
  render(<AccountAction language="en" reset />)
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'new-password-2026!' } })
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'different-password!' } })
  fireEvent.click(screen.getByRole('button', { name: 'Reset password' }))
  expect(screen.getByRole('alert')).toHaveTextContent('The passwords do not match.')
  expect(api).not.toHaveBeenCalled()
})

it('opening another email link in the same tab resets the completed form', async () => {
  window.history.replaceState(null, '', '/account/verify-email#token=first-secret-link')
  vi.mocked(api).mockResolvedValue(undefined)
  render(<AccountAction language="en" reset={false} />)
  fireEvent.click(screen.getByRole('button', { name: 'Verify email' }))
  await screen.findByRole('status')
  act(() => {
    window.history.replaceState(null, '', '/account/verify-email#token=next-secret-link')
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Verify email' }))
  await screen.findByRole('status')
  expect(api).toHaveBeenLastCalledWith('/auth/verify-email', 'POST', { token: 'next-secret-link' })
  expect(window.location.hash).toBe('')
})

it('recovery shows the generic account response', async () => {
  vi.mocked(api).mockResolvedValue({ status: 'accepted' })
  render(<EmailRequestForm language="en" onBack={() => {}} />)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'unknown@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send recovery link' }))
  expect(await screen.findByRole('status')).toHaveTextContent('If the account is eligible')
})

it('requires confirmation and supports cancellation before revoking sessions', async () => {
  vi.mocked(api).mockResolvedValue([{ id: 's1', is_current: true, created_at: '2026-09-22T00:00:00Z', expires_at: '2026-09-29T00:00:00Z', user_agent: 'Test browser' }])
  render(<Sessions language="en" />)
  await screen.findByRole('heading', { name: 'Current session' })
  fireEvent.click(screen.getByRole('button', { name: 'Sign out all sessions' }))
  expect(api).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument()
  expect(api).toHaveBeenCalledTimes(1)
})
