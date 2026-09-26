// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'
import { Teachers, TeacherProfileEditor, TeacherRecordEditor } from './Teachers'
import type { TeacherProfile, TeacherRecord } from './Teachers'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error {
  constructor(public code: string, public status: number) { super(code) }
} }))
const profile: TeacherProfile = { id: 'p', user_id: 'u', full_name: 'Teacher', email: 'teacher@example.com', phone: '', introduction: '', internal_notes: 'PRIVATE', version: 1, archived: false }
const options = { languages: [{ id: 'en', name: 'English', code: 'EN' }], frameworks: [{ id: 'scale', name: 'Scale', code: 'S' }], levels: [{ id: 'l1', name: 'Level 1', code: 'L1', rank: 1, language_id: 'en', framework_id: 'scale' }, { id: 'l2', name: 'Level 2', code: 'L2', rank: 2, language_id: 'en', framework_id: 'scale' }] }
const capability: TeacherRecord = { id: 'cap', version: 2, language_id: 'en', revoked_at: null, language: options.languages[0], levels: [] }
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('teacher only submits contact and introduction, with no private or privileged fields', async () => {
  vi.mocked(api).mockResolvedValue(profile)
  render(<TeacherProfileEditor language="en" personal detail={profile} candidate={null} onSaved={() => {}} />)
  expect(screen.queryByText('PRIVATE')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Archive profile' })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Phone number'), { target: { value: '0123' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(api).toHaveBeenCalledExactlyOnceWith('/teachers/me', 'PATCH', { version: 1, phone: '0123', introduction: '' }))
})

it('teacher with no profile sees guidance and cannot create one', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('TEACHER_NOT_FOUND', 404))
  render(<Teachers language="en" personal />)
  expect(await screen.findByText(/Your center has not created/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Create teacher profile' })).not.toBeInTheDocument()
  expect(api).toHaveBeenCalledExactlyOnceWith('/teachers/me')
})

it('stale profile keeps draft and disables further saves until refreshed', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('TEACHER_CONFLICT', 409))
  render(<TeacherProfileEditor language="en" personal detail={profile} candidate={null} onSaved={() => {}} />)
  fireEvent.change(screen.getByLabelText('Introduction / specialty'), { target: { value: 'Keep draft' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Copy edits')
  expect(screen.getByLabelText('Introduction / specialty')).toHaveValue('Keep draft')
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
})

it('archive needs reason and cancelling does not submit', () => {
  render(<TeacherProfileEditor language="en" personal={false} detail={profile} candidate={null} onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Archive profile' }))
  expect(screen.getByLabelText('Reason')).toBeRequired()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(api).not.toHaveBeenCalled()
})

it('archived teacher profile is read only', () => {
  render(<TeacherProfileEditor language="en" personal detail={{ ...profile, archived: true }} candidate={null} onSaved={() => {}} />)
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
})

it('capability submits exactly selected levels and required reason, no lower-level inference', async () => {
  vi.mocked(api).mockResolvedValue(capability)
  render(<TeacherRecordEditor language="en" kind="capabilities" item={null} options={options} path="/teachers/p/capabilities" onSaved={() => {}} onCancel={() => {}} />)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'en' } })
  fireEvent.click(screen.getByRole('checkbox', { name: 'Scale · Level 2 (L2)' }))
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Checked by center' } })
  expect(screen.getByLabelText('Reason')).toBeRequired()
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(api).toHaveBeenCalledExactlyOnceWith('/teachers/p/capabilities', 'POST', { language_id: 'en', level_ids: ['l2'], reason: 'Checked by center' }))
})

it('revocation confirmation has reason and cancel makes no mutation', () => {
  render(<TeacherRecordEditor language="en" kind="capabilities" item={capability} options={options} path="/teachers/p/capabilities" onSaved={() => {}} onCancel={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Revoke record' }))
  expect(screen.getByLabelText('Reason')).toBeRequired()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(api).not.toHaveBeenCalled()
})

it('revoked records must be restored before editing and send explicit version on restore', async () => {
  vi.mocked(api).mockResolvedValue(capability)
  render(<TeacherRecordEditor language="en" kind="capabilities" item={{ ...capability, revoked_at: '2026-09-25T00:00:00Z' }} options={options} path="/teachers/p/capabilities" onSaved={() => {}} onCancel={() => {}} />)
  expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Restore record' }))
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Rechecked' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => expect(api).toHaveBeenCalledExactlyOnceWith('/teachers/p/capabilities/cap/state', 'POST', { version: 2, revoked: false, reason: 'Rechecked' }))
})
