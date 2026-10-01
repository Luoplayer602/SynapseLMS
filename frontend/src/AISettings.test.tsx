// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AISettings } from './AISettings'
import { api } from './api'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public code: string) { super(code) } } }))
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('keeps provider credentials masked and submits only a newly typed key', async () => {
  vi.mocked(api).mockImplementation(async path => path === '/ai/providers' ? { items: [{ id: 'p1', code: 'primary', name: 'Primary', kind: 'openai', base_url: '', model_id: 'model', has_key: true, enabled: true, allowed_tasks: ['progress_summary'], timeout_seconds: 20, max_output_tokens: 1024, max_daily_calls: 100 }] } : { items: [] })
  render(<AISettings language="en" root />)
  fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
  expect(screen.getByLabelText('API key / token')).toHaveValue('')
  fireEvent.click(screen.getByRole('button', { name: 'Save provider' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/ai/providers/p1', 'PUT', expect.objectContaining({ api_key: null })))
})
