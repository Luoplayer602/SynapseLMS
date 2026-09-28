// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { Admissions, Attendance, BusinessForm, Finances, Notifications } from './Admissions'
import { api, ApiError } from './api'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public code: string, public status: number) { super(code) } } }))
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)
const session = { id: 'session', class_name: 'Class', class_code: 'A', starts_at: '2026-10-05T11:00:00Z', ends_at: '2026-10-05T12:00:00Z', timezone: 'Asia/Ho_Chi_Minh', branch_name: 'Branch', teachers: [], status: 'scheduled' }

it('requires explicit confirmation and sends one unique key, locking after ambiguous network failure', async () => {
  vi.mocked(api).mockRejectedValue(new TypeError('Network unavailable'))
  render(<BusinessForm language="en" title="Collect" path="/collect" body={() => ({ amount: 100 })} onDone={vi.fn()} />)
  expect(screen.getByRole('checkbox')).toBeRequired()
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'Collect' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Outcome uncertain')
  expect(api).toHaveBeenCalledWith('/collect', 'POST', { amount: 100, request_key: expect.any(String) })
  expect(screen.getByRole('button', { name: 'Collect' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Collect' }))
  expect(api).toHaveBeenCalledTimes(1)
})

it('allows correcting validation errors but locks stale state', async () => {
  vi.mocked(api).mockRejectedValueOnce(new ApiError('VALIDATION_ERROR', 422)).mockRejectedValueOnce(new ApiError('BUSINESS_STALE', 409))
  render(<BusinessForm language="en" title="Save" path="/save" body={() => ({ version: 1 })} onDone={vi.fn()} />)
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await screen.findByRole('alert')
  expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled())
})

it('learner can submit a course request with availability but cannot see approval controls', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/admissions/options') return { students: [{ id: 's', full_name: 'Student' }], courses: [{ id: 'c', name: 'English', fee: { amount: 1000 } }], branches: [] } as never
    return { items: [{ id: 'r', student_name: 'Student', course_name: 'English', status: 'submitted' }], total: 1 } as never
  })
  render(<Admissions language="en" staff={false} />)
  await screen.findByRole('button', { name: 'Submit request' })
  expect(screen.queryByRole('button', { name: 'Approve & issue invoice' })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Student'), { target: { value: 's' } })
  fireEvent.change(screen.getByLabelText('Course'), { target: { value: 'c' } })
  fireEvent.change(screen.getByLabelText('Format'), { target: { value: 'any' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add' }))
  fireEvent.click(screen.getByRole('checkbox'))
  fireEvent.click(screen.getByRole('button', { name: 'Submit request' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/admissions/requests', 'POST', expect.objectContaining({ course_id: 'c', student_id: 's', availability: [{ weekday: 0, starts_at: '18:00', ends_at: '21:00' }] })))
})

it('learner invoice includes installments and receipt without collection or reversal controls', async () => {
  const invoice = { id: 'i', student_name: 'Student', total: 1000, gross: 1000, discount: 0, paid: 500, remaining: 500, overdue: 0, snapshot: { course_name: 'English' }, installments: [{ due_on: '2026-10-01', amount: 1000, remaining: 500 }], payments: [{ id: 'p', amount: 500, method: 'cash', created_at: '2026-09-27T10:00:00Z' }] }
  vi.mocked(api).mockImplementation(async path => (path.includes('?') ? { items: [invoice], total: 1 } : invoice) as never)
  render(<Finances language="en" staff={false} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Details / Collect' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Internal receipt' }))
  expect(await screen.findByRole('button', { name: 'Print receipt' })).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Record payment' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Reverse incorrect receipt' })).not.toBeInTheDocument()
})

it('future sessions have readonly attendance and retain the server roster', async () => {
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/attendance/sessions?offset=0') return { items: [session], total: 1 } as never
    if (path.endsWith('/history')) return { items: [], total: 0 } as never
    return { session, version: 0, finalized: false, can_edit: false, records: [{ student_id: 's', student_name: 'Student', status: 'unmarked', note: '' }] } as never
  })
  render(<Attendance language="en" />)
  fireEvent.click(await screen.findByRole('button', { name: 'Attendance roster' }))
  expect(await screen.findByRole('button', { name: 'Save draft' })).toBeDisabled()
  expect(screen.getByRole('combobox')).toHaveValue('unmarked')
})

it('inbox marks only the selected notification read and links to the role appropriate module', async () => {
  vi.mocked(api).mockResolvedValue({ items: [{ id: 'n', kind: 'session.cancel', target_id: 'session', created_at: '2026-09-27T10:00:00Z', read_at: null }], total: 1, unread: 1 })
  render(<MemoryRouter><Notifications language="en" role="student" /></MemoryRouter>)
  const article = (await screen.findByRole('heading', { name: 'Session cancelled' })).closest('article')!
  expect(within(article).getByRole('link')).toHaveAttribute('href', '/my-learning')
  fireEvent.click(within(article).getByRole('button', { name: 'Mark read' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/notifications/n/read', 'POST'))
})
