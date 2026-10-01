// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { GradingSchemes } from './GradingSchemes'
import { api } from './api'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public code: string) { super(code) } } }))
afterEach(cleanup)
beforeEach(() => vi.resetAllMocks())

const scheme = { id: 'scheme', course_id: 'course', name: 'Skills', revision: 1, status: 'draft', version: 1,
  components: [{ code: 'listen', name: 'Listening', skill: 'listening', max_score: 20, weight: 10000 }] }
function reads() {
  vi.mocked(api).mockImplementation(async path => path.startsWith('/results/schemes')
    ? { items: [scheme], total: 1 } : { items: [{ id: 'course', name: 'English' }], total: 1 })
}

it('allows staff to review a draft without mutation controls', async () => {
  reads()
  render(<GradingSchemes language="en" manager={false} />)
  expect(await screen.findByText('Skills · v1')).toBeVisible()
  expect(screen.getByText('Listening (Listening) · 10000/10000 · 20')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Publish scheme' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Save draft' })).not.toBeInTheDocument()
})

it('submits a valid draft with a request key and course scope', async () => {
  reads()
  render(<GradingSchemes language="en" manager />)
  await screen.findByRole('button', { name: 'Save draft' })
  fireEvent.change(screen.getByLabelText('Course'), { target: { value: 'course' } })
  fireEvent.change(screen.getByLabelText('Scheme name'), { target: { value: 'Skills' } })
  fireEvent.change(screen.getByLabelText('Item code'), { target: { value: 'listen' } })
  fireEvent.change(screen.getByLabelText('Item name'), { target: { value: 'Listening' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/results/schemes', 'POST', expect.objectContaining({
    course_id: 'course', name: 'Skills', request_key: expect.any(String),
    components: [expect.objectContaining({ code: 'listen', weight: 10000 })],
  })))
})
