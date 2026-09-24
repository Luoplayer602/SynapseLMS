// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { CatalogActions, CourseEditor, Courses } from './Courses'
import type { CourseRecord } from './Courses'
import { api, ApiError } from './api'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error {
  constructor(public code: string, public status: number) { super(code) }
} }))
const metadata = { languages: [{ id: 'l', code: 'EN', name: 'English' }], frameworks: [{ id: 'f', code: 'LOCAL', name: 'Local', language_id: 'l' }], levels: [{ id: 'out', code: 'L1', name: 'First', framework_id: 'f', language_id: 'l', rank: 1 }] }
const course: CourseRecord = { id: 'c', code: 'COURSE', name: 'Course name', description: '', objectives: 'Goal', entry_requirements: '', completion_requirements: '', language_id: 'l', framework_id: 'f', entry_level_id: null, exit_level_id: 'out', status: 'draft', version: 2, missing_fields: [], language: null, framework: null, entry_level: null, exit_level: null }
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('staff cannot see publication controls and cannot edit published content', () => {
  render(<CourseEditor language="en" manager={false} detail={{ ...course, status: 'published' }} settings={metadata} onSaved={() => {}} />)
  expect(screen.queryByRole('button', { name: 'Publish course' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Return to draft' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Course name')).toBeDisabled()
})

it('publication requires explicit confirmation and a reason; cancel makes no request', () => {
  render(<CourseEditor language="en" manager detail={course} settings={metadata} onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Publish course' }))
  expect(screen.getByLabelText('Reason')).toBeRequired()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(api).not.toHaveBeenCalled()
})

it('changing language clears incompatible framework and levels before saving', async () => {
  vi.mocked(api).mockResolvedValue(course)
  render(<CourseEditor language="en" manager detail={course} settings={metadata} onSaved={() => {}} />)
  fireEvent.change(screen.getByLabelText('Teaching language'), { target: { value: '' } })
  expect(screen.getByLabelText('Level framework')).toHaveValue('')
  expect(screen.getByLabelText('Exit level')).toHaveValue('')
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(api).toHaveBeenCalledTimes(1))
  const payload = vi.mocked(api).mock.calls[0][2]
  expect(payload).toMatchObject({ language_id: null, framework_id: null, exit_level_id: null, version: 2 })
  expect(payload).not.toHaveProperty('code')
  expect(payload).not.toHaveProperty('status')
})

it('stale version preserves edits and blocks another save', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('COURSE_CONFLICT', 409))
  render(<CourseEditor language="en" manager detail={course} settings={metadata} onSaved={() => {}} />)
  fireEvent.change(screen.getByLabelText('Course name'), { target: { value: 'Keep this draft' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await screen.findByRole('alert')
  expect(screen.getByLabelText('Course name')).toHaveValue('Keep this draft')
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
})

it('student catalog uses published-only endpoints and has no administrative or enrollment buttons', async () => {
  vi.mocked(api).mockImplementation(async path => path.endsWith('/options') ? { languages: [], levels: [] } : { items: [], total: 0, limit: 20, offset: 0 })
  render(<Courses language="en" catalog />)
  await screen.findByText('No records yet.')
  expect(vi.mocked(api).mock.calls.every(([path]) => path.startsWith('/course-catalog'))).toBe(true)
  expect(screen.queryByRole('button', { name: 'Create course draft' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Enroll/i })).not.toBeInTheDocument()
})

it('deletion requires a matching code, reason and explicit confirmation; cancel sends nothing', async () => {
  const deleted = vi.fn()
  vi.mocked(api).mockResolvedValue(undefined)
  render(<CatalogActions language="en" item={course} path="/courses/c" onChanged={() => {}} onDeleted={deleted} />)
  fireEvent.click(screen.getByRole('button', { name: 'Delete item' }))
  expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled()
  expect(screen.getByLabelText('Reason')).toBeRequired()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(api).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Delete item' }))
  fireEvent.change(screen.getByLabelText('Type current code to confirm deletion'), { target: { value: 'COURSE' } })
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Created by mistake' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => expect(deleted).toHaveBeenCalledOnce())
  expect(api).toHaveBeenCalledWith('/courses/c', 'DELETE', { code: 'COURSE', version: 2, reason: 'Created by mistake' })
})

it('code correction uses its own versioned endpoint and preserves typed code after a conflict', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('COURSE_CONFLICT', 409))
  render(<CatalogActions language="en" item={course} path="/courses/c" onChanged={() => {}} onDeleted={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Correct code' }))
  fireEvent.change(screen.getByLabelText('New code'), { target: { value: 'FIXED' } })
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Typo correction' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await screen.findByRole('alert')
  expect(screen.getByLabelText('New code')).toHaveValue('FIXED')
  expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled()
  expect(api).toHaveBeenCalledWith('/courses/c/code', 'PATCH', { code: 'FIXED', reason: 'Typo correction', version: 2 })
})

it('staff cannot see delete or code correction controls', () => {
  render(<CourseEditor language="en" manager={false} detail={course} settings={metadata} onSaved={() => {}} />)
  expect(screen.queryByRole('button', { name: 'Delete item' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Correct code' })).not.toBeInTheDocument()
})

it('a successful create followed by failed reload is identified as already saved, with refresh available', async () => {
  let created = false
  vi.mocked(api).mockImplementation(async (path, method) => {
    if (method === 'POST') { created = true; return course }
    if (created) throw new ApiError('REQUEST_FAILED', 500)
    if (path.startsWith('/course-settings')) return { items: [], total: 0 }
    return { items: [], total: 0 }
  })
  render(<Courses language="en" manager />)
  await screen.findByText('No records yet.')
  fireEvent.click(screen.getByRole('button', { name: 'Create course draft' }))
  fireEvent.change(screen.getByLabelText('Course code'), { target: { value: 'COURSE' } })
  fireEvent.change(screen.getByLabelText('Course name'), { target: { value: 'Course name' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Changes were saved, but data could not be reloaded')
  expect(screen.getByRole('button', { name: 'Refresh list' })).toBeEnabled()
  expect(screen.queryByRole('button', { name: 'Create course draft' })).not.toBeInTheDocument()
})
