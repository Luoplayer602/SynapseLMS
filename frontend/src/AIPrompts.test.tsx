// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AIPrompts } from './AIPrompts'
import { api } from './api'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public code: string) { super(code) } } }))
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('requires a tested version and reason before publishing', async () => {
  vi.mocked(api).mockImplementation(async path => path === '/ai/prompts' ? {items: [{id: 'p1', task: 'class_recommendation', locale: 'vi', revision: 1, status: 'draft', body: 'Only rank the supplied candidates and keep warnings visible.', active: false}]} : {valid: true})
  render(<AIPrompts language="en" />)
  expect(await screen.findByText('v1 · draft')).toBeVisible()
  expect(screen.getByRole('button', {name: 'Publish'})).toBeDisabled()
  fireEvent.click(screen.getByRole('button', {name: 'Check structure'}))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/ai/prompts/p1/test', 'POST', undefined))
})
