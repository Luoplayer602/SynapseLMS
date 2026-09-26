// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'
import { PlanningEditor, TeachingSessions } from './Scheduling'
import type { PlanningContext, SchedulePreview } from './Scheduling'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public code: string, public status: number) { super(code) } } }))
const data: PlanningContext = {
  class: { id: 'c', code: 'C01', name: 'Class One', version: 3, branch_id: 'b', room_id: 'r', status: 'draft', starts_on: '2026-10-01', ends_on: '2026-12-01', capacity: 15, format: 'offline', timezone: 'Asia/Ho_Chi_Minh' },
  teachers: [{ id: 't', name: 'Teacher One', active: true, qualified: true }],
  assignments: [{ teacher_id: 't', override_reason: '' }], rooms: [{ id: 'r', code: 'R01', name: 'Room One', version: 1, capacity: 20, archived: false }],
  plan: { starts_on: '2026-10-05', ends_on: '2026-10-05', confirmed_at: null, slots: [{ weekday: 0, starts_at: '18:00:00', ends_at: '19:30:00', room_id: 'r', teacher_ids: ['t'] }] }, sessions: [],
}
const preview: SchedulePreview = { version: 3, timezone: 'Asia/Ho_Chi_Minh', sessions: [{ slot: 0, date: '2026-10-05', starts_at: '2026-10-05T11:00:00Z', ends_at: '2026-10-05T12:30:00Z', room_id: 'r', teacher_ids: ['t'] }], issues: [], conflicts: [], room_checks: [{ slot: 0, unavailable_room_ids: [] }], can_confirm: true, preview_digest: 'a'.repeat(64) }
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('saving a weekly draft submits explicit version, times, room and teachers', async () => {
  vi.mocked(api).mockResolvedValue(data)
  render(<PlanningEditor data={data} language="en" onSaved={() => {}} />)
  fireEvent.change(screen.getByLabelText('Start time'), { target: { value: '19:00' } })
  expect(screen.getByRole('button', { name: 'Check and preview' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Save schedule draft' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/classes/c/schedule', 'PUT', { version: 3, starts_on: '2026-10-05', ends_on: '2026-10-05', slots: [{ weekday: 0, starts_at: '19:00', ends_at: '19:30', room_id: 'r', teacher_ids: ['t'] }] }))
})

it('preview never confirms until a separate explicit confirmation', async () => {
  vi.mocked(api).mockResolvedValueOnce(preview).mockResolvedValueOnce(data)
  render(<PlanningEditor data={data} language="en" onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Check and preview' }))
  await screen.findByText('Planned session count: 1 · Asia/Ho_Chi_Minh')
  expect(api).toHaveBeenCalledExactlyOnceWith('/classes/c/schedule/preview?version=3')
  fireEvent.click(screen.getByRole('button', { name: 'Confirm schedule' }))
  expect(screen.getByText(/Rescheduling\/cancellation is not available/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => expect(api).toHaveBeenLastCalledWith('/classes/c/schedule/confirm', 'POST', expect.objectContaining({ version: 3, preview_digest: preview.preview_digest, confirmation_key: expect.any(String) })))
})

it('conflicts are visible, confirmation and conflicting room choice are disabled', async () => {
  vi.mocked(api).mockResolvedValue({ ...preview, can_confirm: false, conflicts: [{ type: 'room', slot: 0, date: '2026-10-05', class_code: 'OTHER', starts_at: preview.sessions[0].starts_at, ends_at: preview.sessions[0].ends_at }], room_checks: [{ slot: 0, unavailable_room_ids: ['r'] }] })
  render(<PlanningEditor data={data} language="en" onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Check and preview' }))
  expect(await screen.findByText(/Room conflict.*OTHER/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Confirm schedule' })).toBeDisabled()
  expect(screen.getByRole('option', { name: /Room One.*Unavailable/ })).toBeDisabled()
})

it('editing invalidates the preview and requires another save', async () => {
  vi.mocked(api).mockResolvedValue(preview)
  render(<PlanningEditor data={data} language="en" onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Check and preview' }))
  await screen.findByRole('button', { name: 'Confirm schedule' })
  fireEvent.change(screen.getByLabelText('End time'), { target: { value: '20:00' } })
  expect(screen.queryByRole('button', { name: 'Confirm schedule' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Check and preview' })).toBeDisabled()
})

it('unqualified assignment requires an internal reason; unsaved assignments block schedule writes', () => {
  render(<PlanningEditor data={{ ...data, teachers: [{ ...data.teachers[0], qualified: false }] }} language="en" onSaved={() => {}} />)
  expect(screen.getByLabelText('Assignment override reason (internal)')).toBeRequired()
  fireEvent.change(screen.getByLabelText('Assignment override reason (internal)'), { target: { value: 'Approved exception' } })
  expect(screen.getByRole('button', { name: 'Save schedule draft' })).toBeDisabled()
})

it('confirmed plan is read only and has no preview/confirmation action', () => {
  render(<PlanningEditor data={{ ...data, plan: { ...data.plan!, confirmed_at: '2026-09-26T10:00:00Z' } }} language="en" onSaved={() => {}} />)
  expect(screen.getByRole('button', { name: 'Save assignments' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save schedule draft' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: 'Check and preview' })).not.toBeInTheDocument()
})

it('stale version preserves inputs and blocks writes until refresh', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('CLASS_RESOURCE_CONFLICT', 409))
  render(<PlanningEditor data={data} language="en" onSaved={() => {}} />)
  fireEvent.change(screen.getByLabelText('Start time'), { target: { value: '17:00' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save schedule draft' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Copy edits')
  expect(screen.getByLabelText('Start time')).toHaveValue('17:00')
  expect(screen.getByRole('button', { name: 'Save schedule draft' })).toBeDisabled()
})

it('teacher view only reads own sessions and exposes no editing controls', async () => {
  vi.mocked(api).mockResolvedValue({ items: [], total: 0 })
  render(<TeachingSessions language="vi" />)
  expect(await screen.findByText('Chưa có buổi đã xác nhận.')).toBeInTheDocument()
  expect(api).toHaveBeenCalledExactlyOnceWith('/teaching-sessions?offset=0')
  expect(screen.queryByRole('button', { name: 'Lưu lịch nháp' })).not.toBeInTheDocument()
})

it('switching an unconfirmed class online clears draft room and requires saving', async () => {
  vi.mocked(api).mockResolvedValue(data)
  render(<PlanningEditor data={{ ...data, class: { ...data.class, format: 'online', room_id: null } }} language="en" onSaved={() => {}} />)
  expect(screen.getByLabelText('Session room')).toHaveValue('')
  expect(screen.getByLabelText('Session room')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Check and preview' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Save schedule draft' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/classes/c/schedule', 'PUT', expect.objectContaining({ slots: [expect.objectContaining({ room_id: null })] })))
})

it('removed class teachers are cleared from draft slots without invisible invalid IDs', async () => {
  vi.mocked(api).mockResolvedValue(data)
  render(<PlanningEditor data={{ ...data, assignments: [] }} language="en" onSaved={() => {}} />)
  expect(screen.getByRole('button', { name: 'Check and preview' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Save schedule draft' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/classes/c/schedule', 'PUT', expect.objectContaining({ slots: [expect.objectContaining({ teacher_ids: [] })] })))
})
