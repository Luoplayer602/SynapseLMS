import { test, expect } from '@playwright/test'

test('center labels and action buttons work across themes and languages', async ({ page, request }) => {
  await request.post('http://127.0.0.1:8011/__test/reset-rate')
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill('root@example.com')
  await page.getByLabel('Mật khẩu', { exact: true }).fill('e2e-root-password-2026!')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Đăng xuất' })).toBeVisible()
  for (const theme of ['dark', 'light'] as const) {
    await page.emulateMedia({ colorScheme: theme })
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 850 })
      for (const label of ['English', 'Đăng xuất']) {
        const button = page.getByRole('button', { name: label, exact: true })
        await expect(button).toBeVisible()
        const styles = await button.evaluate(element => ({
          text: getComputedStyle(element).color,
          inherited: getComputedStyle(element.parentElement!).color,
        }))
        expect(styles.text).toBe(styles.inherited)
        await page.keyboard.press('Tab')
        await button.focus()
        expect(await button.evaluate(e => getComputedStyle(e).outlineStyle)).not.toBe('none')
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      if (width === 390) await page.screenshot({ path: test.info().outputPath(`profile-${theme}-mobile.png`), fullPage: true })
    }
  }
  await page.getByRole('link', { name: 'Trung tâm', exact: true }).click()
  await expect(page.getByLabel('Tên trung tâm', { exact: true })).toBeVisible()
  await expect(page.getByText('Để quản lý thành viên và lời mời, hãy chọn trung tâm bên dưới và mở phiên hỗ trợ.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Lời mời thành viên' })).toHaveCount(0)
  await page.getByRole('button', { name: 'English', exact: true }).click()
  await expect(page.getByLabel('Center name', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible()
})
