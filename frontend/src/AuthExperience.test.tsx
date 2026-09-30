// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { AuthForm, AuthWelcome } from './AuthExperience'
import { api } from './api'

vi.mock('./api', () => ({ api: vi.fn() }))
beforeEach(() => vi.resetAllMocks())
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })
const props = { language: 'en' as const, registering: false, busy: false, error: '', notice: '', onSubmit: vi.fn(), onMode: vi.fn(), onRecovery: vi.fn() }
const welcome = { language: 'en' as const, phase: 'restoring' as const, profile: null, error: '', onRetry: vi.fn(), onBack: vi.fn(), onComplete: vi.fn() }

it('reveals the password without submitting, keeps autocomplete and has no role picker', () => {
  render(<AuthForm {...props} />)
  const input = screen.getByLabelText('Password', { exact: true })
  expect(input).toHaveAttribute('autocomplete', 'current-password')
  expect(input).toHaveAttribute('minlength', '1')
  fireEvent.click(screen.getByRole('button', { name: 'Show password: Password' }))
  expect(input).toHaveAttribute('type', 'text')
  expect(screen.getByRole('button', { name: 'Hide password: Password' })).toHaveAttribute('aria-pressed', 'true')
  expect(props.onSubmit).not.toHaveBeenCalled()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
})

it('distinguishes center loading, failure and empty results; allows invitation registration', async () => {
  let reject!: (e: Error) => void
  vi.mocked(api).mockReturnValueOnce(new Promise((_, fail) => { reject = fail })).mockResolvedValueOnce([])
  render(<AuthForm {...props} registering />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading centers')
  expect(screen.getByRole('button', { name: 'Register' })).toBeDisabled()
  await act(async () => reject(new Error('offline')))
  expect(screen.getByRole('alert')).toHaveTextContent('Could not load centers')
  fireEvent.click(screen.getByRole('button', { name: 'Reload centers' }))
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
  expect(screen.getByRole('button', { name: 'Register' })).toBeDisabled()
  fireEvent.click(screen.getByRole('checkbox'))
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Register' })).toBeEnabled()
})

it('checks password confirmation before forwarding the register form', async () => {
  vi.mocked(api).mockResolvedValue([{ id: 'center', name: 'My Center' }])
  render(<AuthForm {...props} registering />)
  await screen.findByRole('option', { name: 'My Center' })
  fireEvent.change(screen.getByLabelText('Password', { exact: true }), { target: { value: 'long-password-2026' } })
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'other-password-2026' } })
  fireEvent.submit(screen.getByRole('button', { name: 'Register' }).closest('form')!)
  expect(screen.getByRole('alert')).toBeInTheDocument()
  expect(props.onSubmit).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'long-password-2026' } })
  fireEvent.submit(screen.getByRole('button', { name: 'Register' }).closest('form')!)
  expect(props.onSubmit).toHaveBeenCalledTimes(1)
})

it('disables form actions and navigation while a mutation is pending', () => {
  render(<AuthForm {...props} busy />)
  for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
  fireEvent.submit(screen.getByLabelText('Email').closest('form')!)
  expect(props.onSubmit).not.toHaveBeenCalled()
})

it('delays the loading art, shows slow recovery, never invents percentage progress', () => {
  vi.useFakeTimers()
  const view = render(<AuthWelcome {...welcome} />)
  expect(view.container.querySelector('.auth-welcome')).not.toHaveClass('is-visible')
  act(() => vi.advanceTimersByTime(140))
  expect(view.container.querySelector('.auth-welcome')).toHaveClass('is-visible')
  act(() => vi.advanceTimersByTime(4860))
  expect(screen.getByRole('status')).toHaveTextContent('taking a little longer')
  act(() => vi.advanceTimersByTime(10000))
  fireEvent.click(screen.getByRole('button', { name: 'Check session again' }))
  expect(welcome.onRetry).toHaveBeenCalledTimes(1)
  expect(welcome.onComplete).not.toHaveBeenCalled()
  expect(view.container).not.toHaveTextContent('%')
  view.unmount()
  expect(vi.getTimerCount()).toBe(0)
})

it.each([false, true])('only completes after ready, reduced-motion=%s', reduced => {
  vi.useFakeTimers()
  vi.stubGlobal('matchMedia', () => ({ matches: reduced }))
  const view = render(<AuthWelcome {...welcome} />)
  act(() => vi.advanceTimersByTime(500))
  expect(welcome.onComplete).not.toHaveBeenCalled()
  view.rerender(<AuthWelcome {...welcome} phase="ready" profile={{ id: 'u', email: 'a@b.test', display_name: 'An', is_root_admin: true, membership: null, email_verified_at: null }} />)
  expect(screen.getByRole('heading')).toHaveTextContent('Welcome, An')
  act(() => vi.advanceTimersByTime(reduced ? 0 : 180))
  expect(welcome.onComplete).toHaveBeenCalledTimes(1)
})
