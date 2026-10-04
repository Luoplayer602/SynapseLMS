// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Dashboard } from './Dashboard'
import { api } from './api'
import type { Profile } from './api'

vi.mock('./api', () => ({ api: vi.fn() }))
const profile: Profile = { id: 'u1', email: 'manager@example.com', display_name: 'Mai Anh', is_root_admin: false, email_verified_at: null,
  membership: { id: 'm1', organization_id: 'o1', organization_name: 'Synapse Academy', role: 'organization_manager', tenant_available: true } }
beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

it('shows only counts returned by center APIs and links recent requests to their workflow', async () => {
  vi.mocked(api).mockImplementation(path => {
    if (path.startsWith('/students')) return Promise.resolve({ items: [], total: 1284 })
    if (path.startsWith('/classes')) return Promise.resolve({ items: [], total: 32 })
    if (path.startsWith('/admissions/requests')) return Promise.resolve({ items: [{ id: 'r1', student_name: 'Lan', course_name: 'English B1', status: 'waiting' }], total: 7 })
    if (path.startsWith('/admissions/invoices')) return Promise.resolve({ items: [], total: 12 })
    return Promise.resolve({ items: [], total: 0 })
  })
  render(<MemoryRouter><Dashboard profile={profile} language="vi" support={false}><p>Account</p></Dashboard></MemoryRouter>)
  expect(await screen.findByText('Lan')).toBeInTheDocument()
  expect(screen.getByText('1.284')).toBeInTheDocument()
  expect(screen.getByText('32')).toBeInTheDocument()
  expect(screen.getByText('7')).toBeInTheDocument()
  expect(screen.getByText('12')).toBeInTheDocument()
  expect(screen.getByText(/Chờ xếp lớp/).closest('a')).toHaveAttribute('href', '/admissions')
  expect(screen.getByRole('link', { name: 'Xem lịch học' })).toHaveAttribute('href', '/class-calendar')
  expect(api).toHaveBeenCalledTimes(5)
})

it('keeps tenant figures out of the root dashboard without a support session', async () => {
  render(<MemoryRouter><Dashboard profile={{ ...profile, is_root_admin: true, membership: null }} language="vi" support={false}><p>Account</p></Dashboard></MemoryRouter>)
  expect(screen.getByText(/Dữ liệu trung tâm chỉ xuất hiện/)).toBeInTheDocument()
  expect(screen.queryByText('Học viên đang hoạt động')).not.toBeInTheDocument()
  await waitFor(() => expect(api).not.toHaveBeenCalled())
})

it('marks unavailable figures as missing instead of showing invented zeros', async () => {
  vi.mocked(api).mockRejectedValue(new Error('offline'))
  render(<MemoryRouter><Dashboard profile={profile} language="vi" support={false}><p>Account</p></Dashboard></MemoryRouter>)
  expect(await screen.findByText(/Một số số liệu chưa tải được/)).toBeInTheDocument()
  expect(screen.getAllByText('—')).toHaveLength(4)
})

it.each([
  ['student', 'Hôm nay mình cùng học gì?', '/practice'],
  ['teacher', 'Sẵn sàng cho buổi dạy tiếp theo?', '/teaching-sessions'],
] as const)('offers existing actions for %s without requesting center administration data', async (role, heading, path) => {
  render(<MemoryRouter><Dashboard profile={{ ...profile, membership: { ...profile.membership!, role } }} language="vi" support={false}><p>Account</p></Dashboard></MemoryRouter>)
  expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
  expect(screen.getAllByRole('link').some(link => link.getAttribute('href') === path)).toBe(true)
  if (role === 'student') expect(screen.getByRole('link', { name: 'Nhận xét & bước tiếp theo' })).toHaveAttribute('href', '/ai-progress')
  await waitFor(() => expect(api).not.toHaveBeenCalled())
})
