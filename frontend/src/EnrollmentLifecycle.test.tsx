// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { EnrollmentLifecycle } from './EnrollmentLifecycle'
import { api, ApiError } from './api'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public code: string, public status: number) { super(code) } } }))
afterEach(cleanup)
beforeEach(() => vi.resetAllMocks())
const row = { id: 'request', enrollment_id: 'enrollment', state: 'active', version: 1, settled: false, student_name: 'Learner', course_name: 'English', class_name: 'Class A', periods: [{ starts_at: '2026-09-28T10:00:00Z', ends_at: null }] }
const calculation = { total: 1000, paid: 700, remaining: 300, unused: 500, fee: 0, total_sessions: 2, unused_sessions: 1 }
const detail = { ...row, sessions: [{ id: 'session', starts_at: '2026-10-05T10:00:00Z', ends_at: '2026-10-05T11:00:00Z', timezone: 'UTC' }], invoice: { remaining: 300, offset: 0 }, history: [], refunds: [] }
function mockRead(data = detail) {
  vi.mocked(api).mockImplementation(async path => {
    if (path === '/refunds/policy') return { kind: 'fixed', value: 0, version: 0 }
    if (path === '/enrollments?offset=0') return { items: [data], total: 1 }
    if (path === '/enrollments/request') return data
    if (path.endsWith('/preview')) return { source_digest: 'a'.repeat(64), total_sessions: 2, unused_sessions: 1 }
    return {}
  })
}
it('previews and requires confirmation; changing a boundary invalidates the preview', async () => {
  mockRead()
  render(<EnrollmentLifecycle language="en" staff />)
  fireEvent.click(await screen.findByRole('button', { name: 'Details' }))
  fireEvent.change(await screen.findByLabelText('Effective session'), { target: { value: 'session' } })
  fireEvent.change(screen.getByLabelText('Internal reason'), { target: { value: 'Family reasons' } })
  fireEvent.click(screen.getByRole('button', { name: 'Preview impact' }))
  const confirm = await screen.findByRole('button', { name: 'Confirm enrollment change' })
  const form = confirm.closest('form')!
  expect(within(form).getByRole('checkbox')).toBeRequired()
  fireEvent.change(screen.getByLabelText('Internal reason'), { target: { value: 'Updated reason' } })
  expect(screen.queryByRole('button', { name: 'Confirm enrollment change' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Preview impact' }))
  const nextForm = (await screen.findByRole('button', { name: 'Confirm enrollment change' })).closest('form')!
  fireEvent.click(within(nextForm).getByRole('checkbox'))
  fireEvent.click(within(nextForm).getByRole('button'))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/enrollments/request/operations', 'POST', expect.objectContaining({ action: 'suspend', session_id: 'session', source_digest: 'a'.repeat(64), reason: 'Updated reason' })))
})
it('personal view exposes no operations, policy mutation, or refund controls', async () => {
  mockRead()
  render(<EnrollmentLifecycle language="en" staff={false} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Details' }))
  await screen.findByRole('heading', { name: 'Learning periods (end excluded)' })
  expect(screen.queryByLabelText('Action')).not.toBeInTheDocument()
  expect(screen.queryByText('Refund deduction policy')).not.toBeInTheDocument()
  expect(api).not.toHaveBeenCalledWith('/refunds/policy')
})
it('settled case blocks resume and shows cash separately from debt offset', async () => {
  const data = { ...detail, state: 'suspended', settled: true, refunds: [{ id: 'case', status: 'pending', version: 2, proposed: 500, approved: 500, offset_amount: 300, cash_amount: 200, calculation, disbursement: null }] }
  vi.mocked(api).mockImplementation(async path => path === '/enrollments?offset=0' ? { items: [data], total: 1 } : path === '/refunds/policy' ? { kind: 'fixed', value: 0, version: 0 } : data)
  render(<EnrollmentLifecycle language="en" staff />)
  fireEvent.click(await screen.findByRole('button', { name: 'Details' }))
  expect(await screen.findByText('Settled: resumption and receipt reversal are unavailable for this invoice.')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Preview impact' })).not.toBeInTheDocument()
  expect(screen.getByText('Debt offset: 300 VND · Cash to return: 200 VND')).toBeVisible()
  const payout = screen.getByRole('button', { name: 'Record money returned' }).closest('form')!
  vi.mocked(api).mockRejectedValue(new ApiError('BUSINESS_STALE', 409))
  fireEvent.click(within(payout).getByRole('checkbox'))
  fireEvent.click(within(payout).getByRole('button'))
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(within(payout).getByRole('button')).toBeDisabled()
})
it('shows the adjusted debt offset and cash before confirming an override', async () => {
  const data = { ...detail, state: 'suspended', refunds: [{ id: 'case', status: 'proposed', version: 1, proposed: 500, approved: 0, offset_amount: 0, cash_amount: 0, calculation, disbursement: null }] }
  vi.mocked(api).mockImplementation(async path => path === '/enrollments?offset=0' ? { items: [data], total: 1 } : path === '/refunds/policy' ? { kind: 'fixed', value: 0, version: 0 } : data)
  render(<EnrollmentLifecycle language="en" staff />)
  fireEvent.click(await screen.findByRole('button', { name: 'Details' }))
  const form = (await screen.findByRole('button', { name: 'Approve settlement' })).closest('form')!
  expect(within(form).getByRole('status')).toHaveTextContent('Debt offset: 300 VND · Cash to return: 200 VND')
  fireEvent.change(within(form).getByLabelText('Approved refund (VND)'), { target: { value: '200' } })
  expect(within(form).getByRole('status')).toHaveTextContent('Debt offset: 200 VND · Cash to return: 0 VND')
  fireEvent.change(within(form).getByLabelText('Internal reason'), { target: { value: 'Agreed adjustment' } })
  fireEvent.click(within(form).getByRole('checkbox'))
  fireEvent.click(within(form).getByRole('button'))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/refunds/case/decision', 'POST', expect.objectContaining({ amount: 200, reason: 'Agreed adjustment' })))
})
