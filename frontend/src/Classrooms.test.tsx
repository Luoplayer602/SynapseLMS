// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'
import { Classrooms, FoundationEditor } from './Classrooms'
import type { FoundationOptions, FoundationRecord } from './Classrooms'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error {
  constructor(public code: string, public status: number) { super(code) }
} }))
const branch: FoundationRecord = { id: 'b', code: 'MAIN', name: 'Main branch', version: 1, archived: false, timezone: 'Asia/Ho_Chi_Minh', address: 'Address' }
const room: FoundationRecord = { id: 'r', code: 'R01', name: 'Room 1', version: 1, archived: false, branch_id: 'b', capacity: 20 }
const options: FoundationOptions = { branches: [branch, { ...branch, id: 'b2', name: 'Second branch' }], rooms: [room, { ...room, id: 'r2', branch_id: 'b2', name: 'Room 2' }], courses: [] }
const item: FoundationRecord = { id: 'cls', code: 'C01', name: 'Class 1', version: 2, status: 'draft', branch_id: 'b', room_id: 'r', course_id: 'c', format: 'offline', capacity: 15, starts_on: '2026-10-01', ends_on: '2026-12-01' }
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('staff can inspect facilities but has no mutation controls', () => {
  render(<FoundationEditor language="en" kind="branches" item={branch} options={options} writable={false} onSaved={() => {}} />)
  expect(screen.getByLabelText('Branch address')).toBeDisabled()
  expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Archive' })).not.toBeInTheDocument()
})

it('online removes room, retains branch and never resubmits course or snapshot', async () => {
  vi.mocked(api).mockResolvedValue(item)
  render(<FoundationEditor language="en" kind="classes" item={item} options={options} writable onSaved={() => {}} />)
  fireEvent.change(screen.getByLabelText('Class format'), { target: { value: 'online' } })
  expect(screen.getByLabelText('Default room')).toHaveValue('')
  expect(screen.getByLabelText('Default room')).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(api).toHaveBeenCalledExactlyOnceWith('/classes/cls', 'PATCH', { version: 2, name: 'Class 1', branch_id: 'b', room_id: null, capacity: 15, starts_on: '2026-10-01', ends_on: '2026-12-01', format: 'online' }))
})

it('changing branch clears room and only shows rooms of the chosen branch', () => {
  render(<FoundationEditor language="en" kind="classes" item={item} options={options} writable onSaved={() => {}} />)
  expect(screen.queryByRole('option', { name: /Room 2/ })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Managing branch'), { target: { value: 'b2' } })
  expect(screen.getByLabelText('Default room')).toHaveValue('')
  expect(screen.queryByRole('option', { name: /Room 1/ })).not.toBeInTheDocument()
  expect(screen.getByRole('option', { name: /Room 2/ })).toBeInTheDocument()
})

it('stale version retains unsaved text and disables repeated writes', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('CLASS_RESOURCE_CONFLICT', 409))
  render(<FoundationEditor language="en" kind="classes" item={item} options={options} writable onSaved={() => {}} />)
  fireEvent.change(screen.getByLabelText('Name', { exact: true }), { target: { value: 'Keep these edits' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Copy edits')
  expect(screen.getByLabelText('Name', { exact: true })).toHaveValue('Keep these edits')
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  expect(api).toHaveBeenCalledTimes(1)
})

it('archived classes are read only, restore requires reason and version', async () => {
  vi.mocked(api).mockResolvedValue(item)
  render(<FoundationEditor language="en" kind="classes" item={{ ...item, status: 'archived' }} options={options} writable onSaved={() => {}} />)
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: 'Correct code' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Restore' }))
  expect(screen.getByLabelText('Reason')).toBeRequired()
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Restore reviewed class' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => expect(api).toHaveBeenCalledExactlyOnceWith('/classes/cls/state', 'POST', { version: 2, reason: 'Restore reviewed class', status: 'draft' }))
})

it('code correction cancellation never writes', () => {
  render(<FoundationEditor language="vi" kind="rooms" item={room} options={options} writable onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Sửa mã' }))
  expect(screen.getByLabelText('Lý do')).toBeRequired()
  fireEvent.click(screen.getByRole('button', { name: 'Hủy' }))
  expect(api).not.toHaveBeenCalled()
})

it('mutation network errors warn about uncertainty and are not retried', async () => {
  vi.mocked(api).mockRejectedValue(new Error('offline'))
  render(<FoundationEditor language="en" kind="classes" item={item} options={options} writable onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/refresh|check/i)
  expect(api).toHaveBeenCalledTimes(1)
})

it('staff facility list is read only, supports search and pagination', async () => {
  vi.mocked(api).mockImplementation(async (path) => path.includes('limit=100') ? { items: [branch], total: 1 } : { items: [branch], total: 21 })
  render(<Classrooms language="en" facilities />)
  expect(await screen.findByRole('heading', { name: 'Main branch' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Add branch' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/facilities/branches?q=&status=active&offset=20'))
})

it('navigation from facilities to classes resets the displayed resource kind', async () => {
  vi.mocked(api).mockResolvedValue({ items: [], total: 0 })
  const view = render(<Classrooms language="en" facilities manager />)
  fireEvent.click(screen.getByRole('button', { name: 'Rooms' }))
  expect(await screen.findByRole('button', { name: 'Add room' })).toBeInTheDocument()
  view.rerender(<Classrooms language="en" manager />)
  expect(await screen.findByRole('button', { name: 'Create draft class' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Add room' })).not.toBeInTheDocument()
  await waitFor(() => expect(api).toHaveBeenCalledWith('/classes?q=&status=draft&offset=0'))
})
