import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router'
import { api, ApiError } from './api'
import type { Member, Organization } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'

function useManagement<T>(path: string, language: Language) {
  const [rows, setRows] = useState<T[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(true)
  const reload = useCallback(async () => { setRows(await api<T[]>(path)) }, [path])
  useEffect(() => {
    let stopped = false
    api<T[]>(path).then(data => { if (!stopped) setRows(data) })
      .catch(e => { if (!stopped) setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED') })
      .finally(() => { if (!stopped) setBusy(false) })
    return () => { stopped = true }
  }, [path])
  async function run(action: () => Promise<unknown>) {
    setBusy(true); setError('')
    try { await action(); await reload() }
    catch (e) { setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED') }
    finally { setBusy(false) }
  }
  return { rows, busy, run, message: error ? <p className="error" role="alert">{errorMessage(language, error)}</p> : null }
}

export function Centers({ language, onSupport }: { language: Language; onSupport: (id: string, name: string) => void }) {
  const t = (key: string) => translate(language, key)
  const { rows, busy, run, message } = useManagement<Organization>('/admin/organizations', language)
  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form)
    void run(async () => { await api('/admin/organizations', 'POST', {
      name: values.get('name'), slug: values.get('slug'), is_public: values.has('public'), registration_enabled: values.has('registration'),
    }); form.reset() })
  }
  return <><h1>{t('centers')}</h1><p>{t('rootSupportHint')}</p>{message}{busy && <p role="status">{t('loading')}</p>}
    <form className="card compact-form" onSubmit={create}><h2>{t('newCenter')}</h2>
      <label>{t('centerName')}<input name="name" required maxLength={200} /></label><label>{t('slug')}<input name="slug" required pattern="[a-z0-9][a-z0-9-]{1,79}" /></label>
      <label className="check"><input type="checkbox" name="public" />{t('public')}</label><label className="check"><input type="checkbox" name="registration" />{t('registration')}</label><button disabled={busy}>{t('create')}</button>
    </form>{!rows.length && !busy && <p>{t('empty')}</p>}
    {rows.map(org => <article className="card management-card" key={org.id}><h2>{org.name}</h2><p>{org.slug}</p>
      <form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void run(() => api(`/admin/organizations/${org.id}`, 'PATCH', {
        is_active: f.has('active'), is_public: f.has('public'), registration_enabled: f.has('registration'), reason: f.get('reason'),
      })) }}>
        <label className="check"><input type="checkbox" name="active" defaultChecked={org.is_active} />{t('active')}</label><label className="check"><input type="checkbox" name="public" defaultChecked={org.is_public} />{t('public')}</label><label className="check"><input type="checkbox" name="registration" defaultChecked={org.registration_enabled} />{t('registration')}</label>
        <label>{t('reason')}<input name="reason" minLength={3} maxLength={500} required /></label><button disabled={busy}>{t('save')}</button>
      </form>
      <form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void run(async () => {
        const support = await api<{ id: string }>('/admin/support-sessions', 'POST', { organization_id: org.id, reason: f.get('reason') })
        onSupport(support.id, org.name)
      }) }}><label>{t('reason')}<input name="reason" aria-label={`${t('support')} ${org.name}`} minLength={3} maxLength={500} required /></label><button disabled={busy || !org.is_active}>{t('support')}</button></form>
    </article>)}</>
}

export function Members({ language, root, actorId }: { language: Language; root: boolean; actorId: string }) {
  const t = (key: string) => translate(language, key)
  const { rows, busy, run, message } = useManagement<Member>('/members', language)
  const [invite, setInvite] = useState('')
  const roles = [...(root ? ['organization_manager'] : []), 'staff', 'teacher', 'student']
  return <><h1>{t('members')}</h1>{message}{busy && <p role="status">{t('loading')}</p>}
    <p><Link to="/invitations">{t('inviteMember')}</Link></p>
    <button disabled={busy} onClick={() => void run(async () => { const result = await api<{ code: string }>('/organization/invites', 'POST', {}); setInvite(result.code) })}>{t('createInvite')}</button>
    {invite && <p role="status">{t('invite')}: <code>{invite}</code></p>}
    <form className="card compact-form" onSubmit={e => { e.preventDefault(); const form = e.currentTarget; const f = new FormData(form); void run(async () => {
      await api('/members', 'POST', { email: f.get('email'), password: f.get('password'), display_name: f.get('name'), role: f.get('role'), reason: f.get('reason') }); form.reset()
    }) }}><h2>{t('newMember')}</h2>
      <label>{t('name')}<input name="name" maxLength={200} required /></label><label>{t('email')}<input name="email" type="email" required /></label><label>{t('password')}<input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label>
      <label>{t('role')}<select name="role">{roles.map(role => <option key={role} value={role}>{t(role)}</option>)}</select></label><label>{t('reason')}<input name="reason" minLength={3} maxLength={500} required /></label><button disabled={busy}>{t('create')}</button>
    </form>
    {!rows.length && !busy && <p>{t('empty')}</p>}{rows.map(member => <article className="card management-card" key={`${member.id}:${member.role}:${member.is_active}`}><h2>{member.display_name || member.email}</h2><p>{member.email} · {t(member.role)} · {t(member.is_active ? 'active' : 'inactive')}</p>
      {member.user_id !== actorId && (root || member.role !== 'organization_manager') && <form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void run(() => api(`/members/${member.id}`, 'PATCH', { role: f.get('role'), is_active: f.has('active'), reason: f.get('reason') })) }}>
        <label>{t('role')}<select name="role" defaultValue={member.role}>{roles.map(role => <option key={role} value={role}>{t(role)}</option>)}</select></label><label className="check"><input name="active" type="checkbox" defaultChecked={member.is_active} />{t('active')}</label><label>{t('reason')}<input name="reason" minLength={3} maxLength={500} required /></label><button disabled={busy}>{t('save')}</button>
      </form>}
      {root && <form onSubmit={e => { e.preventDefault(); const f = new FormData(e.currentTarget); void run(() => api(`/admin/users/${member.user_id}`, 'PATCH', { is_active: f.get('status') === 'true', reason: f.get('reason') })) }}>
        <select name="status" aria-label={t('active')}><option value="false">{t('lockUser')}</option><option value="true">{t('unlockUser')}</option></select><label>{t('reason')}<input name="reason" minLength={3} maxLength={500} required /></label><button disabled={busy}>{t('save')}</button>
      </form>}
    </article>)}</>
}
