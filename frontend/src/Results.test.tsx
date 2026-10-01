// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MyResults, Results } from './Results'
import { api } from './api'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public code: string, public status: number) { super(code) } } }))
afterEach(cleanup)
beforeEach(() => vi.resetAllMocks())

const book = { id: 'book', class_id: 'class', version: 3, publish_at: null as string | null, locked_at: null,
  items: [{ id: 'item', code: 'listen', name: 'Listening', skill: 'listening', max_score: 20, weight: 10000, assessed_at: '2026-09-30T10:00:00Z' }],
  students: [{ enrollment_id: 'enrollment', student_name: 'Learner', final_score: null,
    coverage_percent: 100, skills: {}, marks: [{ item_id: 'item', name: 'Listening', skill: 'listening', max_score: 20, score: null, comment: '' }],
    attendance: { attendance_percent: null } }] }
function reads(data = book) {
  vi.mocked(api).mockImplementation(async path => path === '/results/classes?limit=100'
    ? { items: [{ id: 'class', name: 'Class A', course_id: 'course', gradebook_id: 'book' }], total: 1 }
    : data)
}

it('teacher saves decimal marks and staff sees read-only gradebook', async () => {
  reads()
  const view = render(<Results language="en" teacher manager={false} />)
  fireEvent.change(await screen.findByLabelText('Class'), { target: { value: 'class' } })
  fireEvent.change(await screen.findByLabelText('Score'), { target: { value: '15.50' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save scores' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/results/classes/class/items/item', 'PUT', expect.objectContaining({
    version: 3, scores: [{ enrollment_id: 'enrollment', score: '15.50', comment: '' }],
  })))
  view.unmount()
  reads()
  render(<Results language="en" teacher={false} manager={false} />)
  fireEvent.change(await screen.findByLabelText('Class'), { target: { value: 'class' } })
  await screen.findByText('Listening · 100%')
  expect(screen.queryByRole('button', { name: 'Save scores' })).not.toBeInTheDocument()
})

it('personal view renders only server-published personal rows', async () => {
  vi.mocked(api).mockResolvedValue({ items: [{ class_id: 'class', class_name: 'Class A',
    final_score: 77.5, coverage_percent: 40, skills: { listening: 77.5 },
    marks: [{ item_id: 'item', name: 'Listening', skill: 'listening', max_score: 20, score: 15.5, comment: 'Good' }],
    attendance: { attendance_percent: 100 } }], total: 1 })
  render(<MyResults language="en" />)
  expect(await screen.findByText('Class A')).toBeVisible()
  expect(screen.getAllByText('77.50').length).toBeGreaterThan(0)
  expect(api).toHaveBeenCalledWith('/results/mine?limit=100')
})

it('requires an internal reason when editing marks after publication', async () => {
  reads({ ...book, publish_at: '2026-01-01T00:00:00Z' })
  render(<Results language="en" teacher manager={false} />)
  fireEvent.change(await screen.findByLabelText('Class'), { target: { value: 'class' } })
  expect(await screen.findByLabelText('Reason (required after publication)')).toBeRequired()
})
