import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const base = 'http://127.0.0.1:8011/api/v1'
const password = 'materials-module-password!'
async function signIn(page: Page, email: string) {
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Chào mừng trở lại/ })).toBeVisible()
  await page.getByRole('button', { name: 'English', exact: true }).click()
}

test('manager publishes class material, learner reads, withdrawal removes access', async ({ page, browser, request }) => {
  await request.post('http://127.0.0.1:8011/__test/reset-rate')
  const common = { 'X-Synapse-Client': 'web', Origin: 'http://127.0.0.1:5180' }
  const login = await request.post(base + '/auth/login', { headers: common,
    data: { email: 'root@example.com', password: 'e2e-root-password-2026!' } })
  const rootHeaders = { ...common, Authorization: `Bearer ${(await login.json()).access_token}` }
  const center = await (await request.post(base + '/admin/organizations', { headers: rootHeaders,
    data: { name: 'Materials E2E center', slug: `materials-${randomUUID().slice(0, 8)}` } })).json()
  const support = await (await request.post(base + '/admin/support-sessions', { headers: rootHeaders,
    data: { organization_id: center.id, reason: 'Materials E2E fixture' } })).json()
  const headers = { ...rootHeaders, 'X-Support-Session': support.id }
  async function send(path: string, data: object, method = 'POST') {
    const result = await request.fetch(base + path, { headers, method, data })
    expect(result.ok(), `${path}: ${await result.text()}`).toBe(true)
    return result.json()
  }
  const language = await send('/course-settings/languages', { code: 'MAT-EN', name: 'Materials English' })
  const scale = await send('/course-settings/frameworks', { code: 'MAT-S', name: 'Materials scale', language_id: language.id })
  const level = await send('/course-settings/levels', { code: 'MAT-L1', name: 'Materials level', framework_id: scale.id, rank: 1 })
  const course = await send('/courses', { code: 'MAT-COURSE', name: 'Materials course', language_id: language.id,
    framework_id: scale.id, exit_level_id: level.id, objectives: 'Materials E2E' })
  await send(`/courses/${course.id}/state`, { version: 1, status: 'published', reason: 'E2E course' })
  const branch = await send('/facilities/branches', { code: 'MAT-B', name: 'Materials branch' })
  const room = await send('/facilities/rooms', { branch_id: branch.id, code: 'MAT-R', name: 'Materials room', capacity: 20 })
  for (const role of ['organization_manager', 'teacher', 'student']) {
    await send('/members', { email: `mat-${role}@example.com`, role, display_name: role, password, reason: 'Materials fixture' })
  }
  const members = await (await request.get(base + '/members', { headers })).json()
  const teacherAccount = members.find((x: { email: string }) => x.email === 'mat-teacher@example.com')
  const studentAccount = members.find((x: { email: string }) => x.email === 'mat-student@example.com')
  const teacher = await send('/teachers', { user_id: teacherAccount.user_id, full_name: 'Materials Teacher' })
  await send(`/teachers/${teacher.id}/capabilities`, { language_id: language.id, level_ids: [level.id], reason: 'Verified' })
  const student = await send('/students', { user_id: studentAccount.user_id, full_name: 'Materials Student',
    phone: '0900000000', date_of_birth: '2000-01-01' })
  const future = new Date(Date.now() + 7 * 86400000)
  const day = future.toISOString().slice(0, 10), weekday = (future.getUTCDay() + 6) % 7
  const cls = await send('/classes', { code: 'MAT-A', name: 'Materials Class', course_id: course.id,
    branch_id: branch.id, room_id: room.id, capacity: 15, starts_on: day, ends_on: day, format: 'offline' })
  await send(`/classes/${cls.id}/teachers`, { version: 1, teacher_ids: [teacher.id] }, 'PUT')
  await send(`/classes/${cls.id}/schedule`, { version: 2, starts_on: day, ends_on: day,
    slots: [{ weekday, starts_at: '18:00', ends_at: '19:30', room_id: room.id, teacher_ids: [teacher.id] }] }, 'PUT')
  const preview = await (await request.get(base + `/classes/${cls.id}/schedule/preview`, { headers })).json()
  await send(`/classes/${cls.id}/schedule/confirm`, { version: preview.version,
    preview_digest: preview.preview_digest, confirmation_key: randomUUID() })
  await send(`/admissions/fees/${course.id}`, { request_key: randomUUID(), version: 0,
    amount: 100000, installments: [{ days: 0, percent: 100 }] }, 'PUT')
  await send(`/admissions/openings/${cls.id}`, { request_key: randomUUID(), version: 0, enabled: true }, 'PUT')
  const admission = await send('/admissions/requests', { request_key: randomUUID(), student_id: student.id,
    course_id: course.id, branch_id: branch.id, format: 'offline' })
  let placed = await send(`/admissions/requests/${admission.id}/decision`, { request_key: randomUUID(),
    version: admission.version, action: 'approve' })
  if (placed.status === 'waiting') placed = await send(`/admissions/requests/${admission.id}/placement`, {
    request_key: randomUUID(), version: placed.version, class_id: cls.id, reason: 'Schedule match' })
  expect(placed.status).toBe('placed')

  await signIn(page, 'mat-organization_manager@example.com')
  await page.getByRole('link', { name: 'Materials', exact: true }).click()
  await page.getByLabel('Title').fill('Welcome reading')
  await page.getByLabel('Author / source').fill('Center')
  await page.getByRole('button', { name: 'Create draft' }).click()
  await expect(page.locator('.material-row strong').getByText('Welcome reading')).toBeVisible()
  await page.getByRole('combobox', { name: 'Material', exact: true }).selectOption({ index: 1 })
  await page.getByLabel('Or HTTPS link').fill('https://example.org/welcome')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await page.getByRole('button', { name: 'Publish version' }).click()
  await page.getByRole('combobox', { name: 'Class', exact: true }).selectOption({ index: 1 })
  await page.getByRole('combobox', { name: 'Published material' }).selectOption({ index: 1 })
  await page.getByRole('button', { name: 'Assign material' }).click()
  await expect(page.getByRole('status').getByText('Saved.')).toBeVisible()

  const studentContext = await browser.newContext({ baseURL: 'http://127.0.0.1:5180' })
  const studentPage = await studentContext.newPage()
  await signIn(studentPage, 'mat-student@example.com')
  await studentPage.getByRole('link', { name: 'My materials' }).click()
  await expect(studentPage.getByRole('heading', { name: 'Welcome reading' })).toBeVisible()
  page.once('dialog', dialog => void dialog.accept('Source revoked'))
  await page.getByRole('button', { name: 'Withdraw' }).first().click()
  await studentPage.getByRole('button', { name: 'Refresh' }).click()
  await expect(studentPage.getByText('No published materials yet.')).toBeVisible()
  await studentPage.setViewportSize({ width: 390, height: 844 })
  expect(await studentPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await studentContext.close()
})
