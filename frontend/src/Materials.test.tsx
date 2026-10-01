// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Materials, MyMaterials } from './Materials'
import { api } from './api'

vi.mock('./api', () => ({ api: vi.fn(), apiContent: vi.fn(), ApiError: class extends Error { constructor(public code: string) { super(code) } } }))
afterEach(cleanup)
beforeEach(() => vi.resetAllMocks())

const material = { id: 'm1', title: 'Unit 1', description: 'Read this', source: 'School', status: 'published',
  audience: 'students', scope: 'library', class_id: null,
  latest: { id: 'v1', revision: 1, kind: 'link', file_status: 'ready', filename: '', source_url: 'https://example.org', published_at: '2026-09-30T00:00:00Z' } }

function reads() {
  vi.mocked(api).mockImplementation(async (path, method) => {
    if (method && method !== 'GET') return { id: 'new' }
    if (path === '/materials?limit=100') return { items: [material] }
    if (path === '/classes?limit=100') return { items: [{ id: 'c1', name: 'Class A' }] }
    if (path === '/courses?limit=100') return { items: [{ id: 'course', name: 'English' }] }
    if (path === '/materials/curricula' || path === '/materials/reviews') return { items: [] }
    if (path === '/materials/mine') return { items: [{ id: 'a1', material, version: material.latest }] }
    return { items: [] }
  })
}

it('creates a tenant material and offers published versions for a class', async () => {
  reads()
  render(<Materials language="en" role="staff" />)
  expect(await screen.findByText('Read this')).toBeVisible()
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'New lesson' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/materials', 'POST', expect.objectContaining({ title: 'New lesson', audience: 'students' })))
  expect(screen.getByText('Assign to class')).toBeVisible()
})

it('renders only granted learner items returned by the API', async () => {
  reads()
  render(<MyMaterials language="en" />)
  expect(await screen.findByText('Unit 1')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Open / download' })).toBeVisible()
})
