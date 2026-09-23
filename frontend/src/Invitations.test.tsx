// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { InvitationAcceptance, Invitations } from './Invitations'
import { api, signIn } from './api'

vi.mock('./api', () => ({ api: vi.fn(), signIn: vi.fn(), signOut: vi.fn(),
  ApiError: class extends Error { constructor(public code: string, public status: number) { super(code) } },
}))
const preview = { email: 'invited@example.com', display_name: 'Invited', role: 'teacher',
  organization_name: 'Center A', expires_at: '2026-09-29T00:00:00Z', existing_account: false }
beforeEach(() => { vi.resetAllMocks(); window.history.replaceState(null, '', '/account/accept-invitation#token=secret-invitation') })
afterEach(cleanup)

it('does not accept on opening the email and prevents mismatched passwords', async () => {
  vi.mocked(api).mockResolvedValue(preview)
  render(<InvitationAcceptance language="en" profile={null} restoring={false} onProfile={() => {}} />)
  await screen.findByLabelText('New password')
  expect(window.location.hash).toBe('')
  expect(api).toHaveBeenCalledTimes(1)
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'new-password-2026!' } })
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'different-password!' } })
  fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))
  expect(screen.getByRole('alert')).toHaveTextContent('The passwords do not match.')
  expect(api).toHaveBeenCalledTimes(1)
})

it('an existing account is asked for its current password and not a new one', async () => {
  vi.mocked(api).mockResolvedValue({ ...preview, existing_account: true })
  render(<InvitationAcceptance language="en" profile={null} restoring={false} onProfile={() => {}} />)
  await screen.findByLabelText('Password')
  expect(screen.queryByLabelText('New password')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Accept invitation' })).not.toBeInTheDocument()
  expect(signIn).not.toHaveBeenCalled()
})

it('requires signing out when another account is active', async () => {
  vi.mocked(api).mockResolvedValue({ ...preview, existing_account: true })
  render(<InvitationAcceptance language="en" restoring={false} onProfile={() => {}}
    profile={{ id: 'u', email: 'wrong@example.com', display_name: 'Wrong', is_root_admin: false, membership: null, email_verified_at: null }} />)
  expect(await screen.findByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Accept invitation' })).not.toBeInTheDocument()
})

it('center managers cannot select the manager role and must confirm revocation', async () => {
  vi.mocked(api).mockResolvedValue({ items: [{ id: 'i', email: preview.email, display_name: 'Invited', role: 'teacher', status: 'pending', delivery_status: 'sent', expires_at: preview.expires_at, can_manage: true }], total: 1, limit: 20, offset: 0 })
  render(<Invitations language="en" root={false} />)
  await screen.findByRole('heading', { name: 'Invited' })
  expect(screen.queryByRole('option', { name: 'Center manager' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Revoke invitation' }))
  expect(api).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument()
  expect(api).toHaveBeenCalledTimes(1)
})
