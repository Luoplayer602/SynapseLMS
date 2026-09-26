// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Proficiencies, ProficiencyEditor } from './Proficiencies'
import type { Proficiency } from './Proficiencies'
import { api, ApiError } from './api'
vi.mock('./api', () => ({ api: vi.fn(), ApiError: class extends Error {
  constructor(public code: string, public status: number) { super(code) }
} }))
const levels = [{ id: 'low', code: 'L1', name: 'Lower' }, { id: 'high', code: 'L2', name: 'Higher' }]
const row: Proficiency = { id: 'p', version: 3, language_id: 'l', framework_id: 'f', language: { id: 'l', code: 'EN', name: 'English' }, framework: { id: 'f', code: 'LOCAL', name: 'Local' }, self_level_id: null, self_level: null, self_declared_at: null, verified_level_id: 'high', verified_level: levels[1], verified_at: '2026-09-25T00:00:00Z', verified_by_name: 'Staff', goal_level_id: null, goal_level: null, goal_text: '', target_date: null, goals_updated_at: null }
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('student declaration writes only the declaration and does not expose staff controls', async () => {
  vi.mocked(api).mockResolvedValue({ ...row, self_level_id: 'low' })
  const saved = vi.fn()
  render(<ProficiencyEditor language="en" personal archived={false} item={row} levels={levels} path="/student-proficiencies/me/p" onSaved={saved} />)
  expect(screen.queryByRole('button', { name: 'Verify/adjust proficiency' })).not.toBeInTheDocument()
  expect(screen.queryByText('Internal evidence (hidden from student)')).not.toBeInTheDocument()
  fireEvent.change(screen.getByRole('combobox', { name: 'Self-declared level' }), { target: { value: 'low' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save declaration' }))
  await waitFor(() => expect(saved).toHaveBeenCalledOnce())
  expect(api).toHaveBeenCalledWith('/student-proficiencies/me/p/declaration', 'PATCH', { version: 3, self_level_id: 'low' })
  expect(saved.mock.calls[0][0].verified_level_id).toBe('high')
})

it('unknown level is explicit null and distinct from lowest level', async () => {
  vi.mocked(api).mockResolvedValue(row)
  render(<ProficiencyEditor language="en" personal archived={false} item={row} levels={levels} path="/p" onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Save declaration' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/p/declaration', 'PATCH', { version: 3, self_level_id: null }))
})

it('verification requires source, evidence, reason and confirmation; cancel sends nothing', () => {
  render(<ProficiencyEditor language="en" personal={false} archived={false} item={row} levels={levels} path="/p" onSaved={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Verify/adjust proficiency' }))
  for (const label of ['Verified level', 'Assessment source (internal)', 'Assessment evidence (internal)', 'Reason']) expect(screen.getByLabelText(label)).toBeRequired()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(api).not.toHaveBeenCalled()
})

it('stale goal keeps typed data and blocks resubmission', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('PROFICIENCY_CONFLICT', 409))
  render(<ProficiencyEditor language="en" personal archived={false} item={row} levels={levels} path="/p" onSaved={() => {}} />)
  fireEvent.change(screen.getByRole('textbox', { name: 'Learning goal' }), { target: { value: 'Keep this goal' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save goals' }))
  await screen.findByRole('alert')
  expect(screen.getByRole('textbox', { name: 'Learning goal' })).toHaveValue('Keep this goal')
  expect(screen.getByRole('button', { name: 'Save goals' })).toBeDisabled()
})

it('archived records are read-only but retain history access', async () => {
  vi.mocked(api).mockResolvedValue({ items: [], total: 0 })
  render(<ProficiencyEditor language="en" personal archived item={row} levels={levels} path="/p" onSaved={() => {}} />)
  expect(screen.getByRole('button', { name: 'Save declaration' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save goals' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Proficiency/goals history' }))
  await waitFor(() => expect(api).toHaveBeenCalledWith('/p/history?offset=0'))
})

it('personal options use dedicated minimal endpoints, never the administrative course settings', async () => {
  vi.mocked(api).mockResolvedValue({ items: [], total: 0 })
  render(<Proficiencies language="en" profileId="ignored" personal archived={false} />)
  await screen.findByText('No proficiency records yet.')
  expect(vi.mocked(api).mock.calls.map(([path]) => path)).toEqual(expect.arrayContaining(['/student-proficiencies/me?offset=0', '/student-proficiency-options/levels?limit=100&offset=0']))
  expect(vi.mocked(api).mock.calls.some(([path]) => path.startsWith('/course-settings'))).toBe(false)
})
