import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError, signIn, signOut } from './api'
import type { Profile } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import { useEmailLink } from './useEmailLink'

interface Invitation {
  id: string; email: string; display_name: string; role: string; status: string;
  expires_at: string; delivery_status: string; sent_at: string | null; can_manage: boolean;
}
interface InvitationPage { items: Invitation[]; total: number; offset: number; limit: number }
const base = '/organization/membership-invitations'
const code = (e: unknown) => e instanceof ApiError ? e.code : 'REQUEST_FAILED'

export function Invitations({ language, root }: { language: Language; root: boolean }) {
  const t = (key: string) => translate(language, key)
  const [page, setPage] = useState<InvitationPage | null>(null)
  const [offset, setOffset] = useState(0)
  const [filter, setFilter] = useState('')
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [action, setAction] = useState<{ item: Invitation; type: 'resend' | 'revoke' } | null>(null)
  const roles = [...(root ? ['organization_manager'] : []), 'teacher', 'staff', 'student']
  useEffect(() => {
    let cancelled = false
    api<InvitationPage>(`${base}?limit=20&offset=${offset}${filter ? `&status=${filter}` : ''}`)
      .then(data => { if (!cancelled) setPage(data) })
      .catch(e => { if (!cancelled) setError(code(e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [offset, filter, reload])
  function refresh() { setLoading(true); setError(''); setReload(value => value + 1) }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget, values = new FormData(form)
    setBusy(true); setError(''); setNotice('')
    try {
      await api(base, 'POST', { email: values.get('email'), display_name: values.get('name'),
        role: values.get('role'), reason: values.get('reason'), expires_days: Number(values.get('days')) })
      form.reset(); setOffset(0); setFilter(''); setNotice('invitationCreated'); refresh()
    } catch (e) { setError(code(e)) } finally { setBusy(false) }
  }
  async function change(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!action) return
    const values = new FormData(event.currentTarget)
    setBusy(true); setError(''); setNotice('')
    try {
      await api(`${base}/${action.item.id}/${action.type}`, 'POST', { reason: values.get('reason'),
        ...(action.type === 'resend' ? { expires_days: Number(values.get('days')) } : {}) })
      setNotice(action.type === 'resend' ? 'invitationResent' : 'invitationRevoked')
      setAction(null); refresh()
    } catch (e) { setError(code(e)) } finally { setBusy(false) }
  }
  return <><h1>{t('invitations')}</h1><p>{t('invitationsHint')}</p>
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}
    {notice && <p role="status">{t(notice)}</p>}
    <form className="card compact-form" onSubmit={create}><h2>{t('inviteMember')}</h2>
      <label>{t('email')}<input type="email" name="email" required /></label>
      <label>{t('name')}<input name="name" maxLength={200} required /></label>
      <label>{t('role')}<select name="role" defaultValue="teacher">{roles.map(role => <option key={role} value={role}>{t(role)}</option>)}</select></label>
      <label>{t('inviteDays')}<input name="days" type="number" min={1} max={30} defaultValue={7} required /></label>
      <label>{t('reason')}<input name="reason" minLength={3} maxLength={500} required /></label>
      <button className="primary" disabled={busy}>{t('sendInvitation')}</button>
    </form>
    <div className="session-actions"><label>{t('invitationFilter')}<select value={filter} onChange={e => { setFilter(e.target.value); setOffset(0); setLoading(true); setAction(null) }}>
      <option value="">{t('allStatuses')}</option>{['pending', 'accepted', 'expired', 'revoked'].map(status => <option key={status} value={status}>{t(`invitation_${status}`)}</option>)}</select></label>
      <button disabled={busy || loading} onClick={refresh}>{t('refreshList')}</button></div>
    {loading && <p role="status">{t('loading')}</p>}
    {action && <form key={`${action.type}:${action.item.id}`} className="card compact-form" onSubmit={change}>
      <h2>{t(action.type === 'resend' ? 'resendInvitation' : 'revokeInvitation')}</h2><p>{action.item.email}</p>
      <p>{t(action.type === 'resend' ? 'resendInvitationHint' : 'revokeInvitationHint')}</p>
      <label>{t('reason')}<input name="reason" minLength={3} maxLength={500} required /></label>
      {action.type === 'resend' && <label>{t('inviteDays')}<input name="days" type="number" min={1} max={30} defaultValue={7} required /></label>}
      <div className="session-actions"><button disabled={busy}>{t('confirm')}</button><button type="button" disabled={busy} onClick={() => setAction(null)}>{t('cancel')}</button></div>
    </form>}
    {!loading && page?.items.length === 0 && <p>{t('empty')}</p>}
    {page?.items.map(item => <article className="card management-card" key={item.id}><h2>{item.display_name}</h2><p>{item.email}</p>
      <p>{t(item.role)} · {t(`invitation_${item.status}`)}</p><p>{t('expiresAt')}: {new Date(item.expires_at).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US')}</p>
      <p>{t(`delivery_${item.delivery_status}`)}</p>
      {item.can_manage && ['pending', 'expired'].includes(item.status) && <div className="session-actions">
        <button disabled={busy || !!action} onClick={() => setAction({ item, type: 'resend' })}>{t('resendInvitation')}</button>
        <button disabled={busy || !!action} onClick={() => setAction({ item, type: 'revoke' })}>{t('revokeInvitation')}</button></div>}
    </article>)}
    {page && <div className="session-actions"><button disabled={busy || loading || offset === 0} onClick={() => { setOffset(Math.max(0, offset - 20)); setLoading(true) }}>{t('previousPage')}</button>
      <span>{page.items.length ? offset + 1 : 0}–{page.items.length ? offset + page.items.length : 0} / {page.total}</span>
      <button disabled={busy || loading || offset + 20 >= page.total} onClick={() => { setOffset(offset + 20); setLoading(true) }}>{t('nextPage')}</button></div>}
  </>
}

interface Preview { email: string; display_name: string; role: string; organization_name: string; expires_at: string; existing_account: boolean }
interface AcceptanceProps { language: Language; profile: Profile | null; restoring: boolean; onProfile: (profile: Profile | null) => void }

export function InvitationAcceptance(props: AcceptanceProps) {
  const link = useEmailLink()
  return <AcceptInvitation key={link.version} {...props} token={link.token} />
}

function AcceptInvitation({ language, profile, restoring, onProfile, token }: AcceptanceProps & { token: string }) {
  const t = (key: string) => translate(language, key)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [existing, setExisting] = useState(false)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    let cancelled = false
    if (!token) return
    api<Preview>('/membership-invitations/preview', 'POST', { token })
      .then(data => { if (!cancelled) { setPreview(data); setExisting(data.existing_account) } })
      .catch(e => { if (!cancelled) setError(code(e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [token, reload])
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!preview) return
    const form = new FormData(event.currentTarget)
    if (!existing && form.get('password') !== form.get('confirmPassword')) { setError('PASSWORD_MISMATCH'); return }
    setBusy(true); setError('')
    try {
      if (existing && !profile) {
        await signIn(preview.email, String(form.get('password')))
        onProfile(await api<Profile>('/auth/me'))
      } else {
        await api(existing ? '/membership-invitations/accept' : '/membership-invitations/accept-new', 'POST',
          { token, ...(!existing ? { display_name: form.get('name'), password: form.get('password') } : {}) })
        setDone(true)
      }
    } catch (e) {
      const failure = code(e)
      if (failure === 'INVITATION_LOGIN_REQUIRED') setExisting(true)
      setError(failure)
    } finally { setBusy(false) }
  }
  const wrongAccount = profile && preview && profile.email.trim().toLowerCase() !== preview.email
  return <section className="card auth-card"><h1>{t('acceptInvitation')}</h1>
    {(error || !token) && <p role="alert" className="error">{errorMessage(language, error || 'INVALID_INVITATION')}</p>}
    {token && (loading || restoring) && <p role="status">{t('loading')}</p>}
    {error && !preview && token && <button onClick={() => { setError(''); setLoading(true); setReload(value => value + 1) }}>{t('retry')}</button>}
    {done ? <p role="status">{t('invitationAccepted')}</p> : preview && !restoring && <>
      <p>{preview.organization_name} · {t(preview.role)}</p><p>{preview.email}</p>
      {wrongAccount ? <><p>{t('invitationWrongAccount')}</p><button disabled={busy} onClick={async () => {
        setBusy(true); setError('')
        try { await signOut(); onProfile(null) } catch (e) { setError(code(e)) } finally { setBusy(false) }
      }}>{t('logout')}</button></> : <form onSubmit={submit}>
        {!existing && <label>{t('name')}<input name="name" defaultValue={preview.display_name} maxLength={200} required /></label>}
        {(!existing || !profile) && <label>{t(existing ? 'password' : 'newPassword')}<input name="password" type="password" autoComplete={existing ? 'current-password' : 'new-password'} minLength={existing ? 1 : 12} maxLength={128} required /></label>}
        {!existing && <label>{t('confirmPassword')}<input name="confirmPassword" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label>}
        <p>{t(existing && !profile ? 'invitationSignInHint' : 'invitationAcceptHint')}</p>
        <button className="primary" disabled={busy}>{t(busy ? 'loading' : existing && !profile ? 'login' : 'acceptInvitation')}</button>
      </form>}
    </>}
    <p><a href="/">{t('backToLogin')}</a></p>
  </section>
}
