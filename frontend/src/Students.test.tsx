// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ProfileEditor, Students } from './Students'
import type { StudentDetail } from './Students'
import { api, ApiError } from './api'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error {
  constructor(public code: string, public status: number) { super(code) }
} }))
const detail: StudentDetail = { id: 'p', code: 'SL-TEST', user_id: 'u', email: 'test@example.com',
  full_name: 'Student', date_of_birth: null, phone: null, address: null, internal_notes: 'Private',
  guardians: [], missing_fields: ['phone'], archived: false, version: 2 }
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('self editor never displays or submits internal notes, scope or user id', async () => {
  vi.mocked(api).mockResolvedValue(detail)
  render(<ProfileEditor language="en" personal detail={detail} candidate={null} defaultName="" onSaved={() => {}} />)
  expect(screen.queryByText('Private')).not.toBeInTheDocument()
  expect(screen.queryByLabelText(/Internal notes/)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(api).toHaveBeenCalledTimes(1))
  const payload = vi.mocked(api).mock.calls[0][2] as Record<string, unknown>
  expect(payload.version).toBe(2)
  for (const key of ['internal_notes', 'user_id', 'organization_id', 'code', 'archived']) expect(payload).not.toHaveProperty(key)
})

it('stale edit is blocked until reload and preserves the typed draft', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('STUDENT_CONFLICT', 409))
  render(<ProfileEditor language="en" personal detail={detail} candidate={null} defaultName="" onSaved={() => {}} />)
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Keep my edit' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Copy edits')
  expect(screen.getByLabelText('Full name')).toHaveValue('Keep my edit')
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
})

it('archive requires a reason and cancel sends no request', () => {
  render(<ProfileEditor language="en" personal={false} detail={detail} candidate={null} defaultName="" onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Archive profile' }))
  expect(screen.getByLabelText('Reason')).toBeRequired()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(api).not.toHaveBeenCalled()
})

it('self GET missing profile opens draft without automatically creating data', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('STUDENT_NOT_FOUND', 404))
  render(<Students language="en" personal displayName="Existing user" />)
  expect(await screen.findByLabelText('Full name')).toHaveValue('Existing user')
  expect(api).toHaveBeenCalledExactlyOnceWith('/students/me')
})

it('only one guardian can be selected primary in the editor', () => {
  render(<ProfileEditor language="en" personal detail={detail} candidate={null} defaultName="" onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Add contact' }))
  fireEvent.click(screen.getByRole('button', { name: 'Add contact' }))
  const boxes = screen.getAllByLabelText('Primary contact')
  expect(boxes[0]).toBeChecked()
  fireEvent.click(boxes[1])
  expect(boxes[0]).not.toBeChecked()
  expect(boxes[1]).toBeChecked()
})
