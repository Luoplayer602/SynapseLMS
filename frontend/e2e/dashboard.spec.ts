import { test, expect } from '@playwright/test'

for (const role of ['root', 'organization_manager', 'staff', 'teacher', 'student']) {
  test(`dashboard ${role} keeps role navigation and fits desktop/mobile`, async ({ page }, testInfo) => {
    const requests: string[] = []
    await page.route('**/api/v1/**', async route => {
      const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
      requests.push(path)
      const body = path === '/auth/me' ? {
        id: 'visual-user', email: 'visual@example.test', display_name: 'Minh Anh', is_root_admin: role === 'root', email_verified_at: null,
        membership: role === 'root' ? null : { id: 'visual-member', organization_id: 'visual-center', organization_name: 'Synapse Academy', role, tenant_available: true },
      } : path === '/practice/rewards/mine' ? { selected: 'synapse-soft' } : { items: [], total: 0, unread_count: 0 }
      await route.fulfill({ json: body })
    })
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Chào mừng trở lại/ })).toBeVisible()
    const operations = role === 'organization_manager' || role === 'staff'
    await expect(page.locator('.dashboard-metrics')).toHaveCount(operations ? 1 : 0)
    if (role === 'student') await expect(page.getByRole('link', { name: 'Nhận xét & bước tiếp theo' })).toHaveAttribute('href', '/ai-progress')
    if (!operations) expect(requests.some(path => /^\/(students|classes|admissions)/.test(path))).toBe(false)
    await page.screenshot({ path: testInfo.outputPath(`dashboard-${role}-desktop.png`), fullPage: true })
    for (const width of [768, 390, 320]) {
      await page.setViewportSize({ width, height: 844 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      if (width === 390) {
        await page.getByRole('button', { name: 'Mở menu', exact: true }).click()
        await expect(page.getByRole('link', { name: 'Tổng quan', exact: true })).toBeVisible()
        await page.keyboard.press('Escape')
        await expect(page.getByRole('button', { name: 'Mở menu', exact: true })).toHaveAttribute('aria-expanded', 'false')
        await expect(page.locator('#main-navigation')).toBeHidden()
        await page.screenshot({ path: testInfo.outputPath(`dashboard-${role}-mobile.png`), fullPage: true })
      }
    }
    await page.emulateMedia({ reducedMotion: 'reduce' })
    expect(await page.locator('.dashboard-shortcut').first().evaluate(el => getComputedStyle(el).transitionDuration)).toBe('0s')
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.locator('.dashboard-account summary').click()
    await expect(page.locator('.dashboard-account .profile-card')).toBeVisible()
    await expect(page.locator('.dashboard-account .profile-card')).toHaveCSS('background-color', 'rgb(255, 255, 255)')
  })
}

test('student AI hub shows existing tasks on desktop and mobile', async ({ page }, testInfo) => {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
    await route.fulfill({ json: path === '/auth/me' ? {
      id: 'visual-student', email: 'student@example.test', display_name: 'Minh Anh', is_root_admin: false, email_verified_at: null,
      membership: { id: 'visual-member', organization_id: 'visual-center', organization_name: 'Synapse Academy', role: 'student', tenant_available: true },
    } : path === '/practice/rewards/mine' ? { selected: 'synapse-soft' } : { items: [], total: 0 } })
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/ai-hub')
  await expect(page.getByRole('heading', { name: 'Góc học tập của bạn' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Mở bài luyện AI' })).toHaveAttribute('href', '/practice')
  await expect(page.getByRole('link', { name: /Nhận xét & bước tiếp/ })).toHaveAttribute('href', '/ai-progress')
  await page.screenshot({ path: testInfo.outputPath('ai-hub-desktop.png'), fullPage: true })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 })
    await expect(page.locator('#main-navigation')).toBeHidden()
    await page.waitForTimeout(300)
    expect(await page.locator('#main-navigation').evaluate(el => getComputedStyle(el).visibility === 'hidden')).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
  await page.screenshot({ path: testInfo.outputPath('ai-hub-mobile-reduced.png'), fullPage: true })
  expect(await page.locator('.ai-hub-bubble').evaluate(el => getComputedStyle(el).transitionDuration)).toBe('0s')
})

test('business cards stay readable when the operating system uses dark mode', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '')
    const body = path === '/auth/me' ? {
      id: 'root-user', email: 'root@example.test', display_name: 'Root', is_root_admin: true, email_verified_at: null, membership: null,
    } : path === '/admin/organizations' ? [{ id: 'center-1', name: 'Demo center', slug: 'demo', is_active: true, is_public: true, registration_enabled: true }]
      : path === '/ai/providers' ? { items: [{ id: 'provider-1', code: 'demo', name: 'AI provider', kind: 'gemini', model_id: 'flash', enabled: true, has_key: true, allowed_tasks: [], version: 1 }] }
      : path === '/ai/prompts' ? { items: [{ id: 'prompt-1', task: 'class_recommendation', locale: 'vi', revision: 1, status: 'published', active: true, body: 'Helpful instructions for the selected task.' }] }
      : { items: [], total: 0 }
    await route.fulfill({ json: body })
  })

  for (const path of ['/centers', '/ai-settings', '/ai-prompts']) {
    await page.goto(path)
    await expect(page.locator('.content .card').first()).toBeVisible()
    const cardStyles = await page.locator('.content .card').evaluateAll(cards => cards.map(card => {
      const background = getComputedStyle(card).backgroundColor
      const title = card.querySelector('h2')
      const textColors = [...card.querySelectorAll('h2, p, pre, label')].map(node => getComputedStyle(node).color)
      return { background, titleColor: title ? getComputedStyle(title).color : '', textColors }
    }))
    expect(cardStyles.length, path).toBeGreaterThan(1)
    for (const style of cardStyles) {
      expect(style.background, `${path}: card background`).toMatch(/^rgba?\(255, 255, 255(?:, 0\.9)?\)$/)
      expect(style.titleColor, `${path}: card title`).toBe('rgb(32, 45, 53)')
      for (const color of style.textColors) {
        const channels = color.match(/[\d.]+/g)?.slice(0, 3).map(Number) ?? []
        const luminance = channels.map(value => {
          const channel = value / 255
          return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
        }).reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0)
        expect((1.05) / (luminance + 0.05), `${path}: text ${color} on light card`).toBeGreaterThanOrEqual(4.5)
      }
    }
  }
})
