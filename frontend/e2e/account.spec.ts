import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const server = 'http://127.0.0.1:8011'
const headers = { 'X-Synapse-Client': 'web', Origin: 'http://127.0.0.1:5180' }

async function login(page: Page, email: string, password: string) {
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Chào mừng đến SynapseLMS' })).toBeVisible()
}

test('verification and recovery links complete the account lifecycle', async ({ page, browser, request }) => {
  const email = 'lifecycle-e2e@example.com', password = 'lifecycle-password-2026!'
  const centers = await (await request.get(server + '/api/v1/organizations/public')).json()
  const registered = await request.post(server + '/api/v1/auth/register', { headers,
    data: { email, password, display_name: 'Lifecycle Student', organization_id: centers[0].id } })
  expect(registered.status()).toBe(201)
  await login(page, email, password)
  await expect(page.getByText('Email chưa xác minh.', { exact: true })).toBeVisible()
  await expect.poll(async () => (await (await request.get(server + '/__test/mail', { params: { email } })).json()).length).toBe(1)
  let messages: string[] = await (await request.get(server + '/__test/mail', { params: { email } })).json()
  const verification = messages[0].match(/http:\/\/[^\s]+/)![0]
  await page.goto(verification, { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Xác minh email' })).toBeVisible()
  await expect.poll(() => new URL(page.url()).hash).toBe('')
  await page.getByRole('button', { name: 'Xác minh email' }).click()
  await expect(page.getByRole('status')).toHaveText('Email đã xác minh.')
  await page.goto('/')
  await expect(page.getByText('Email đã xác minh.', { exact: true })).toBeVisible()
  const recoveryContext = await browser.newContext()
  const recovery = await recoveryContext.newPage()
  await recovery.goto('http://127.0.0.1:5180/', { waitUntil: 'domcontentloaded' })
  await recovery.getByRole('button', { name: 'Quên mật khẩu' }).click()
  await recovery.getByLabel('Email', { exact: true }).fill(email)
  await recovery.getByRole('button', { name: 'Gửi liên kết khôi phục' }).click()
  await expect(recovery.getByRole('status')).toContainText('Nếu tài khoản đủ điều kiện')
  await expect.poll(async () => (await (await request.get(server + '/__test/mail', { params: { email } })).json()).length).toBe(2)
  messages = await (await request.get(server + '/__test/mail', { params: { email } })).json()
  const reset = messages[1].match(/http:\/\/[^\s]+/)![0]
  await recovery.goto(reset, { waitUntil: 'domcontentloaded' })
  await recovery.getByLabel('Mật khẩu mới', { exact: true }).fill('recovered-e2e-password!')
  await recovery.getByLabel('Nhập lại mật khẩu mới').fill('recovered-e2e-password!')
  await recovery.getByRole('button', { name: 'Đặt lại mật khẩu', exact: true }).click()
  await expect(recovery.getByRole('status')).toContainText('Đã đổi mật khẩu')
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Đăng nhập', exact: true })).toBeVisible()
  await login(page, email, 'recovered-e2e-password!')
  await recovery.goto(reset, { waitUntil: 'domcontentloaded' })
  await recovery.getByLabel('Mật khẩu mới', { exact: true }).fill('recovered-e2e-password!')
  await recovery.getByLabel('Nhập lại mật khẩu mới').fill('recovered-e2e-password!')
  await recovery.getByRole('button', { name: 'Đặt lại mật khẩu', exact: true }).click()
  await expect(recovery.getByRole('alert')).toContainText('Liên kết không hợp lệ')
  await recoveryContext.close()
})

test('session screen revokes other devices, then all sessions', async ({ page, browser, request }) => {
  const email = 'sessions-e2e@example.com', password = 'sessions-password-2026!'
  const centers = await (await request.get(server + '/api/v1/organizations/public')).json()
  expect((await request.post(server + '/api/v1/auth/register', { headers,
    data: { email, password, display_name: 'Sessions Student', organization_id: centers[0].id } })).status()).toBe(201)
  await login(page, email, password)
  const otherContext = await browser.newContext()
  const other = await otherContext.newPage()
  await login(other, email, password)
  await page.getByRole('link', { name: 'Phiên đăng nhập' }).click()
  await expect(page.getByRole('heading', { name: 'Phiên hiện tại', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Phiên khác', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Đăng xuất các phiên khác' }).click()
  await page.getByRole('button', { name: 'Xác nhận', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Phiên khác', exact: true })).toHaveCount(0)
  await other.reload()
  await expect(other.getByRole('heading', { name: 'Đăng nhập', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Đăng xuất toàn bộ' }).click()
  await page.getByRole('button', { name: 'Xác nhận', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Đăng nhập', exact: true })).toBeVisible()
  await otherContext.close()
})
