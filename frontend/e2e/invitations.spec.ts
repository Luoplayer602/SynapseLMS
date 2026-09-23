import { test, expect } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'

const server = 'http://127.0.0.1:8011'
test.beforeEach(async ({ request }) => { expect((await request.post(server + '/__test/reset-rate')).status()).toBe(204) })

async function openInvitations(page: Page) {
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.getByLabel('Email', { exact: true }).fill('root@example.com')
  await page.getByLabel('Mật khẩu', { exact: true }).fill('e2e-root-password-2026!')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await page.getByRole('link', { name: 'Trung tâm', exact: true }).click()
  const center = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Trung tâm Demo A' }) })
  await center.getByLabel('Mở phiên hỗ trợ Trung tâm Demo A').fill('E2E invitation support')
  await center.getByRole('button', { name: 'Mở phiên hỗ trợ' }).click()
  await page.getByRole('link', { name: 'Lời mời thành viên' }).click()
}

async function invite(page: Page, email: string, name: string) {
  const form = page.locator('form').filter({ has: page.getByRole('heading', { name: 'Mời thành viên qua email' }) })
  await form.getByLabel('Email', { exact: true }).fill(email)
  await form.getByLabel('Họ và tên').fill(name)
  await form.getByLabel('Vai trò').selectOption('teacher')
  await form.getByLabel('Lý do').fill('E2E invite teacher')
  await form.getByRole('button', { name: 'Gửi lời mời', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Đã tạo lời mời' })).toBeVisible()
}

async function mailLink(request: APIRequestContext, email: string) {
  await expect.poll(async () => (await (await request.get(server + '/__test/mail', { params: { email } })).json()).length).toBe(1)
  const messages: string[] = await (await request.get(server + '/__test/mail', { params: { email } })).json()
  return messages[0].match(/http:\/\/[^\s]+/)![0]
}

test('new teacher joins only after accepting email; revocation disables another invitation', async ({ page, browser, request }) => {
  await openInvitations(page)
  await invite(page, 'new-invite@example.com', 'New invited teacher')
  const link = await mailLink(request, 'new-invite@example.com')
  await page.getByRole('link', { name: 'Thành viên', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New invited teacher' })).toHaveCount(0)
  await page.getByRole('link', { name: 'Lời mời thành viên' }).click()
  const card = page.locator('article').filter({ hasText: 'new-invite@example.com' })
  await expect(card).toContainText('Chờ tiếp nhận')
  const recipientContext = await browser.newContext()
  const recipient = await recipientContext.newPage()
  await recipient.goto(link, { waitUntil: 'domcontentloaded' })
  await expect(recipient.getByRole('heading', { name: 'Tiếp nhận lời mời' })).toBeVisible()
  await expect.poll(() => new URL(recipient.url()).hash).toBe('')
  await recipient.getByLabel('Mật khẩu mới', { exact: true }).fill('new-invite-password!')
  await recipient.getByLabel('Nhập lại mật khẩu mới').fill('new-invite-password!')
  await recipient.getByRole('button', { name: 'Tiếp nhận lời mời' }).click()
  await expect(recipient.getByRole('status')).toContainText('Đã tiếp nhận lời mời')
  await page.getByRole('button', { name: 'Làm mới danh sách' }).click()
  await expect(card).toContainText('Đã tiếp nhận')
  await recipient.getByRole('link', { name: 'Về trang đăng nhập' }).click()
  await recipient.getByLabel('Email', { exact: true }).fill('new-invite@example.com')
  await recipient.getByLabel('Mật khẩu', { exact: true }).fill('new-invite-password!')
  await recipient.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(recipient.getByText('Email đã xác minh.', { exact: true })).toBeVisible()
  await expect(recipient.getByRole('link', { name: 'Lời mời thành viên' })).toHaveCount(0)

  await invite(page, 'revoked-invite@example.com', 'Revoked invitation')
  const revokedLink = await mailLink(request, 'revoked-invite@example.com')
  const revoked = page.locator('article').filter({ hasText: 'revoked-invite@example.com' })
  await revoked.getByRole('button', { name: 'Thu hồi lời mời' }).click()
  const confirmation = page.locator('form').filter({ has: page.getByRole('heading', { name: 'Thu hồi lời mời' }) })
  await confirmation.getByLabel('Lý do').fill('E2E no longer needed')
  await confirmation.getByRole('button', { name: 'Xác nhận' }).click()
  await expect(revoked).toContainText('Đã thu hồi')
  await recipient.goto(revokedLink, { waitUntil: 'domcontentloaded' })
  await expect(recipient.getByRole('alert')).toContainText('Lời mời không hợp lệ')
  await recipientContext.close()
})

test('existing account signs in with its password before confirming membership', async ({ page, browser, request }) => {
  await openInvitations(page)
  await invite(page, 'existing-invite@example.com', 'Keep existing account')
  const link = await mailLink(request, 'existing-invite@example.com')
  const recipientContext = await browser.newContext()
  const recipient = await recipientContext.newPage()
  await recipient.goto(link, { waitUntil: 'domcontentloaded' })
  await recipient.getByLabel('Mật khẩu', { exact: true }).fill('e2e-existing-password!')
  await recipient.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(recipient.getByRole('button', { name: 'Tiếp nhận lời mời' })).toBeVisible()
  const card = page.locator('article').filter({ hasText: 'existing-invite@example.com' })
  await page.getByRole('button', { name: 'Làm mới danh sách' }).click()
  await expect(card).toContainText('Chờ tiếp nhận')
  await recipient.getByRole('button', { name: 'Tiếp nhận lời mời' }).click()
  await expect(recipient.getByRole('status')).toContainText('Đã tiếp nhận lời mời')
  await recipient.getByRole('link', { name: 'Về trang đăng nhập' }).click()
  await expect(recipient.getByRole('heading', { name: 'Chào mừng đến SynapseLMS' })).toBeVisible()
  await expect(recipient.locator('.profile-card')).toContainText('Existing invite user')
  await expect(recipient.locator('.profile-card')).toContainText('Giáo viên')
  await recipientContext.close()
})
