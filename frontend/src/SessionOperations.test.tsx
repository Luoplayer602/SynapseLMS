// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'
import { SessionEditor, SessionPanel, WeeklyAgenda } from './SessionOperations'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public code: string, public status: number) { super(code) } } }))
const row = { id: 's', version: 1, status: 'scheduled', class_code: 'A', class_name: 'Alpha', branch_id: 'b', branch_name: 'Branch', room_id: 'r', room_name: 'Room', starts_at: '2026-10-05T11:00:00Z', ends_at: '2026-10-05T12:30:00Z', timezone: 'Asia/Ho_Chi_Minh', format: 'offline', teachers: [{ id: 't', name: 'Teacher' }] }
const detail = { session: row, class: { id: 'c', code: 'A', name: 'Alpha', version: 4, starts_on: '2026-10-01', ends_on: '2026-12-01', capacity: 15 }, rooms: [{ id: 'r', code: 'R', name: 'Room', version: 1, capacity: 20 }], teachers: [{ id: 't', name: 'Teacher', active: true, qualified: true }], override_reason: '', can_edit: true }
const preview = { before: row, after: { ...row, teacher_ids: ['t'], can_apply: true, issues: [], conflicts: [] } }
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('previews without mutation and confirms the exact versioned request explicitly', async () => {
  vi.mocked(api).mockResolvedValueOnce(preview).mockResolvedValueOnce({ session: { ...row, version: 2 } })
  const applied = vi.fn()
  render(<SessionEditor detail={detail} language="en" onApplied={applied} />)
  expect(screen.getByLabelText('Start time')).toHaveValue('18:00')
  fireEvent.change(screen.getByLabelText('Change reason (internal)'), { target: { value: 'Change requested' } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview change' }))
  await screen.findByRole('button', { name: 'Confirm session change' })
  expect(api).toHaveBeenCalledTimes(1)
  const payload = vi.mocked(api).mock.calls[0][2]
  expect(payload).toEqual(expect.objectContaining({ version: 1, action: 'reschedule', day: '2026-10-05', starts_at: '18:00', room_id: 'r', request_key: expect.any(String) }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm session change' }))
  await waitFor(() => expect(api).toHaveBeenLastCalledWith('/class-sessions/s/operations', 'POST', payload))
  await waitFor(() => expect(applied).toHaveBeenCalled())
})

it('edits discard preview; conflicts cannot be applied', async () => {
  vi.mocked(api).mockResolvedValue({ ...preview, after: { ...preview.after, can_apply: false, issues: ['SCHEDULE_TEACHER_UNAVAILABLE'] } })
  render(<SessionEditor detail={detail} language="en" onApplied={() => {}} />)
  fireEvent.change(screen.getByLabelText('Change reason (internal)'), { target: { value: 'Requested' } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview change' }))
  expect(await screen.findByRole('button', { name: 'Confirm session change' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('End time'), { target: { value: '20:00' } })
  expect(screen.queryByRole('button', { name: 'Confirm session change' })).not.toBeInTheDocument()
})

it('cancel sends no time/teacher changes; cancelled sessions offer restore only', async () => {
  vi.mocked(api).mockResolvedValue(preview)
  const { unmount } = render(<SessionEditor detail={detail} language="en" onApplied={() => {}} />)
  fireEvent.change(screen.getByLabelText('Session action'), { target: { value: 'cancel' } })
  fireEvent.change(screen.getByLabelText('Change reason (internal)'), { target: { value: 'Cancelled meeting' } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview change' }))
  await waitFor(() => expect(api).toHaveBeenCalled())
  expect(vi.mocked(api).mock.calls[0][2]).toEqual({ version: 1, action: 'cancel', reason: 'Cancelled meeting', request_key: expect.any(String) })
  unmount()
  render(<SessionEditor detail={{ ...detail, session: { ...row, status: 'cancelled' } }} language="en" onApplied={() => {}} />)
  expect(screen.getByLabelText('Session action')).toHaveValue('restore')
  expect(screen.queryByRole('option', { name: 'Cancel session' })).not.toBeInTheDocument()
})

it('past sessions are read-only; loading history is staff-only API and lazy', async () => {
  vi.mocked(api).mockImplementation(async path => path.endsWith('/history?offset=0') ? { items: [], total: 0 } : { ...detail, can_edit: false })
  render(<SessionPanel id="s" language="en" />)
  expect(api).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Session details / changes' }))
  expect(await screen.findByRole('button', { name: 'Preview change' })).toBeDisabled()
  expect(screen.getByText('No changes since initial confirmation.')).toBeInTheDocument()
})

it('an uncertain mutation is never retried; requires refreshing before another write', async () => {
  vi.mocked(api).mockResolvedValueOnce(preview).mockRejectedValueOnce(new Error('Disconnected'))
  render(<SessionEditor detail={detail} language="en" onApplied={() => {}} />)
  fireEvent.change(screen.getByLabelText('Change reason (internal)'), { target: { value: 'Requested' } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview change' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Confirm session change' }))
  await screen.findByRole('alert')
  expect(screen.getByRole('button', { name: 'Preview change' })).toBeDisabled()
  expect(api).toHaveBeenCalledTimes(2)
})

it('stale session version blocks edits and preserves entered reason', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('CLASS_RESOURCE_CONFLICT', 409))
  render(<SessionEditor detail={detail} language="en" onApplied={() => {}} />)
  fireEvent.change(screen.getByLabelText('Change reason (internal)'), { target: { value: 'Keep my reason' } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview change' }))
  await screen.findByRole('alert')
  expect(screen.getByLabelText('Change reason (internal)')).toHaveValue('Keep my reason')
  expect(screen.getByRole('button', { name: 'Preview change' })).toBeDisabled()
})

it('weekly agenda applies filters with a seven-day range and offers inline session details', async () => {
  vi.mocked(api).mockImplementation(async path => path.endsWith('/options') ? { branches: [], rooms: [{ id: 'r', name: 'Room' }], teachers: [] } : { items: [row], total: 1 })
  render(<WeeklyAgenda language="en" />)
  await screen.findByRole('heading', { name: 'Alpha (A)' })
  fireEvent.change(screen.getByLabelText('Week starting'), { target: { value: '2026-10-05' } })
  fireEvent.change(screen.getByLabelText('Filter room'), { target: { value: 'r' } })
  fireEvent.click(screen.getByRole('button', { name: 'Show agenda' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/class-sessions?starts_on=2026-10-05&ends_on=2026-10-11&status=scheduled&room_id=r&offset=0'))
  expect(await screen.findByRole('button', { name: 'Session details / changes' })).toBeEnabled()
})
