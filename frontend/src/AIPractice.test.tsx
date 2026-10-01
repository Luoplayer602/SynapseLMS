// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AIPractice } from './AIPractice'
import { api } from './api'

vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error { constructor(public code: string) { super(code) } } }))
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('shows only approved answer choices and keeps locked themes disabled', async () => {
  vi.mocked(api).mockImplementation(async path => path === '/practice/mine' ? {items: [{id: 'q1', course_id: 'c1', locale: 'en', stem: 'Choose the correct answer.', options: ['one', 'two'], status: 'published'}]} : {current_streak: 1, best_streak: 1, unlocked: ['synapse-soft'], selected: 'synapse-soft'})
  render(<MemoryRouter><AIPractice language="en" /></MemoryRouter>)
  expect(await screen.findByText('Choose the correct answer.')).toBeVisible()
  expect(screen.getAllByRole('button', {name: 'Locked'})).toHaveLength(3)
  screen.getAllByRole('button', {name: 'Locked'}).forEach(button => expect(button).toBeDisabled())
  expect(screen.queryByText('Answer:')).not.toBeInTheDocument()
})
