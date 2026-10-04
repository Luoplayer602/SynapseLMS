import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const base = 'http://127.0.0.1:8011/api/v1'
const password = 'results-module-password!'

async function signIn(page: Page, email: string) {
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Chào mừng trở lại/ })).toBeVisible()
  await page.getByRole('button', { name: 'English', exact: true }).click()
}

test('manager scheme, teacher gradebook, published learner result and manager lock', async ({ page, browser, request }) => {
  await request.post('http://127.0.0.1:8011/__test/reset-rate')
  const common = { 'X-Synapse-Client': 'web', Origin: 'http://127.0.0.1:5180' }
  const login = await request.post(base + '/auth/login', { headers: common,
    data: { email: 'root@example.com', password: 'e2e-root-password-2026!' } })
  const rootHeaders = { ...common, Authorization: `Bearer ${(await login.json()).access_token}` }
  const centerResponse = await request.post(base + '/admin/organizations', { headers: rootHeaders,
    data: { name: 'Results E2E center', slug: `results-e2e-${randomUUID().slice(0, 8)}` } })
  expect(centerResponse.ok(), await centerResponse.text()).toBe(true)
  const center = await centerResponse.json()
  const support = await (await request.post(base + '/admin/support-sessions', { headers: rootHeaders,
    data: { organization_id: center.id, reason: 'Results E2E fixture' } })).json()
  const headers = { ...rootHeaders, 'X-Support-Session': support.id }
  async function send(path: string, data: object, method = 'POST') {
    const result = await request.fetch(base + path, { headers, method, data })
    expect(result.ok(), `${path}: ${await result.text()}`).toBe(true)
    return result.json()
  }
  const language = await send('/course-settings/languages', { code: 'RES-EN', name: 'Results English' })
  const scale = await send('/course-settings/frameworks', { code: 'RES-S', name: 'Results scale', language_id: language.id })
  const level = await send('/course-settings/levels', { code: 'RES-L1', name: 'Results level', framework_id: scale.id, rank: 1 })
  const course = await send('/courses', { code: 'RES-COURSE', name: 'Results course', language_id: language.id,
    framework_id: scale.id, exit_level_id: level.id, objectives: 'Results E2E' })
  await send(`/courses/${course.id}/state`, { version: 1, status: 'published', reason: 'E2E course' })
  const branch = await send('/facilities/branches', { code: 'RES-B', name: 'Results branch' })
  const room = await send('/facilities/rooms', { branch_id: branch.id, code: 'RES-R', name: 'Results room', capacity: 20 })
  for (const role of ['organization_manager', 'teacher', 'student']) {
    await send('/members', { email: `res-${role}@example.com`, role, display_name: role, password, reason: 'Results fixture' })
  }
  const members = await (await request.get(base + '/members', { headers })).json()
  const teacherAccount = members.find((x: { email: string }) => x.email === 'res-teacher@example.com')
  const studentAccount = members.find((x: { email: string }) => x.email === 'res-student@example.com')
  const teacher = await send('/teachers', { user_id: teacherAccount.user_id, full_name: 'Results Teacher' })
  await send(`/teachers/${teacher.id}/capabilities`, { language_id: language.id, level_ids: [level.id], reason: 'Verified' })
  const student = await send('/students', { user_id: studentAccount.user_id, full_name: 'Results Student',
    phone: '0900000000', date_of_birth: '2000-01-01' })
  const future = new Date(Date.now() + 7 * 86400000)
  const day = future.toISOString().slice(0, 10), weekday = (future.getUTCDay() + 6) % 7
  const cls = await send('/classes', { code: 'RES-A', name: 'Results Class', course_id: course.id,
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
  if (placed.status === 'waiting') {
    const candidates = await (await request.get(base + `/admissions/requests/${admission.id}/candidates`, { headers })).json()
    expect(candidates.items.some((x: { id: string }) => x.id === cls.id)).toBe(true)
    placed = await send(`/admissions/requests/${admission.id}/placement`, { request_key: randomUUID(),
      version: placed.version, class_id: cls.id, reason: 'Match the scheduled class' })
  }
  expect(placed.status).toBe('placed')

  await signIn(page, 'res-organization_manager@example.com')
  await page.getByRole('navigation', { name: 'Student operations' }).getByRole('link', { name: 'Grading settings' }).click()
  await page.getByRole('combobox', { name: 'Course', exact: true }).selectOption(course.id)
  await page.getByLabel('Scheme name').fill('Core results')
  await page.getByLabel('Item code').fill('listen')
  await page.getByLabel('Item name').fill('Listening')
  await page.getByRole('spinbutton', { name: 'Maximum score' }).fill('20')
  await page.getByRole('button', { name: 'Save draft' }).click()
  await expect(page.getByText('Core results · v1')).toBeVisible()
  await page.getByRole('button', { name: 'Publish scheme' }).click()
  await expect(page.getByText('Results course · Published')).toBeVisible()

  const teacherContext = await browser.newContext({ baseURL: 'http://127.0.0.1:5180' })
  const teacherPage = await teacherContext.newPage()
  await signIn(teacherPage, 'res-teacher@example.com')
  await teacherPage.getByRole('navigation', { name: 'Student operations' }).getByRole('link', { name: 'Gradebook' }).click()
  await teacherPage.getByRole('combobox', { name: 'Class', exact: true }).selectOption(cls.id)
  await teacherPage.getByRole('button', { name: 'Create gradebook' }).click()
  await expect(teacherPage.getByText('Listening · 100%')).toBeVisible()
  await teacherPage.getByLabel('Assessment time').fill(`${day}T18:05`)
  await teacherPage.getByRole('button', { name: 'Save assessment time' }).click()
  await teacherPage.getByLabel('Score').fill('15.50')
  await teacherPage.getByLabel('Comment visible to student').fill('Good progress')
  await teacherPage.getByRole('button', { name: 'Save scores' }).click()
  await expect(teacherPage.getByText('77.50', { exact: true })).toBeVisible()
  const past = new Date(Date.now() - 60_000)
  const local = new Date(past.getTime() - past.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
  await teacherPage.getByLabel('Publish from').fill(local)
  await teacherPage.getByRole('button', { name: 'Schedule / publish' }).click()

  const studentContext = await browser.newContext({ baseURL: 'http://127.0.0.1:5180' })
  const studentPage = await studentContext.newPage()
  await signIn(studentPage, 'res-student@example.com')
  await studentPage.getByRole('navigation', { name: 'Student operations' }).getByRole('link', { name: 'My results' }).click()
  await expect(studentPage.getByText('Results Class')).toBeVisible()
  await expect(studentPage.getByText('Listening: 15.50 / 20 · Good progress')).toBeVisible()
  await page.getByRole('navigation', { name: 'Student operations' }).getByRole('link', { name: 'Gradebook' }).click()
  await page.getByRole('combobox', { name: 'Class', exact: true }).selectOption(cls.id)
  await page.getByLabel('Reason (required after publication)').fill('Reviewed')
  await page.getByRole('button', { name: 'Lock gradebook' }).click()
  await expect(page.getByText('Gradebook locked')).toBeVisible()
  await studentPage.setViewportSize({ width: 390, height: 844 })
  expect(await studentPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await studentContext.close()
  await teacherContext.close()
})
