import type { IconName } from './Icon'

export function routeIcon(path: string): IconName {
  if (path === '/') return 'overview'
  if (/practice|ai-progress|ai-hub/.test(path)) return 'chat'
  if (/ai-|settings|facilities/.test(path)) return 'settings'
  if (/calendar|learning|sessions|attendance/.test(path)) return 'calendar'
  if (/finances|enrollments/.test(path)) return 'fees'
  if (/courses|materials|gradebook|results/.test(path)) return 'book'
  if (/classes|centers/.test(path)) return 'class'
  if (/members|students|teachers|admissions|invitations|profile/.test(path)) return 'users'
  return 'shield'
}
