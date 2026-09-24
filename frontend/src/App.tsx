import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router'
import { AccountAction, EmailRequestForm, Sessions, VerificationStatus } from './Account'
import { api, ApiError, clearSession, setSupportSession, signIn, signOut } from './api'
import type { Organization, Profile } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import { Centers, Members } from './Management'
import { InvitationAcceptance, Invitations } from './Invitations'
import { Students } from './Students'

export default function App() {
  const location = useLocation()
  const [language, setLanguage] = useState<Language>('vi')
  const t = (key: string) => translate(language, key)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [registering, setRegistering] = useState(false)
  const [recovering, setRecovering] = useState(false)
  const [useInvite, setUseInvite] = useState(false)
  const [centers, setCenters] = useState<Organization[]>([])
  const [support, setSupport] = useState<{ id: string; name: string } | null>(null)
  const showError = (e: unknown) => setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED')
  useEffect(() => {
    let cancelled = false
    api<Profile>('/auth/me').then(p => { if (!cancelled) setProfile(p) })
      .catch(e => { if (!cancelled && !(e instanceof ApiError && e.status === 401)) setError('REQUEST_FAILED') })
      .finally(() => { if (!cancelled) setLoading(false) })
    const signedOut = () => { setProfile(null); setSupport(null) }
    window.addEventListener('synapse-signed-out', signedOut)
    return () => { cancelled = true; window.removeEventListener('synapse-signed-out', signedOut) }
  }, [])
  useEffect(() => { document.documentElement.lang = language }, [language])
  useEffect(() => {
    if (!registering) return
    let cancelled = false
    api<Organization[]>('/organizations/public').then(data => { if (!cancelled) setCenters(data) })
      .catch(() => { if (!cancelled) setError('REQUEST_FAILED') })
    return () => { cancelled = true }
  }, [registering])

  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setBusy(true); setError(''); setNotice('')
    try {
      const email = String(form.get('email')), password = String(form.get('password'))
      if (registering) {
        await api('/auth/register', 'POST', { email, password, display_name: form.get('name'),
          ...(useInvite ? { invite_code: form.get('invite') } : { organization_id: form.get('center') }) })
        setRegistering(false); setNotice('registered')
      } else { await signIn(email, password); setProfile(await api<Profile>('/auth/me')) }
    } catch (e) { showError(e) } finally { setBusy(false) }
  }
  async function logout() {
    setBusy(true); setError('')
    try { await signOut(); setProfile(null); setSupport(null) }
    catch (e) { showError(e) } finally { setBusy(false) }
  }
  async function passwordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setBusy(true); setError('')
    try {
      await api('/auth/password', 'POST', { current_password: form.get('currentPassword'), password: form.get('password') })
      clearSession(); setNotice('passwordChanged')
    } catch (e) { showError(e) } finally { setBusy(false) }
  }
  const languageButton = <button type="button" onClick={() => setLanguage(language === 'vi' ? 'en' : 'vi')}>{language === 'vi' ? 'English' : 'Tiếng Việt'}</button>
  const messages = <>{error && <p role="alert" className="error">{errorMessage(language, error)}</p>}{notice && <p role="status">{t(notice)}</p>}</>
  if (location.pathname === '/account/accept-invitation') {
    return <main className="auth-page"><header>{languageButton}</header><InvitationAcceptance language={language} profile={profile} restoring={loading} onProfile={setProfile} /></main>
  }
  if (location.pathname === '/account/verify-email' || location.pathname === '/account/reset-password') {
    return <main className="auth-page"><header>{languageButton}</header><AccountAction key={location.pathname} language={language} reset={location.pathname.endsWith('reset-password')} /></main>
  }
  if (loading) return <main className="auth-page"><p role="status">{t('loading')}</p></main>
  if (!profile && recovering) return <main className="auth-page"><header>{languageButton}</header><EmailRequestForm language={language} onBack={() => setRecovering(false)} /></main>
  if (!profile) return <main className="auth-page"><header>{languageButton}</header>
    <section className="card auth-card"><div className="brand-mark" aria-hidden="true">S</div><p className="eyebrow">SynapseLMS</p>
      <h1>{t(registering ? 'register' : 'login')}</h1><p>{t('intro')}</p>{messages}
      <form key={registering ? 'register' : 'login'} onSubmit={authenticate}>
        {registering && <label>{t('name')}<input name="name" autoComplete="name" maxLength={200} required /></label>}
        <label>{t('email')}<input name="email" type="email" autoComplete="username" required /></label>
        <label>{t('password')}<input name="password" type="password" autoComplete={registering ? 'new-password' : 'current-password'} minLength={registering ? 12 : 1} maxLength={128} required /></label>
        {registering && <><small>{t('passwordHint')}</small><label className="check"><input type="checkbox" checked={useInvite} onChange={e => setUseInvite(e.target.checked)} />{t('useInvite')}</label>
          {useInvite ? <label>{t('invite')}<input name="invite" minLength={20} required /></label> : <label>{t('center')}
            <select name="center" defaultValue="" required><option value="" disabled>{t('choose')}</option>{centers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
            {!centers.length && <small>{t('noCenters')}</small>}</label>}</>}
        <button className="primary" disabled={busy}>{t(busy ? 'loading' : registering ? 'register' : 'login')}</button>
      </form><button type="button" onClick={() => { setRegistering(!registering); setError(''); setNotice('') }}>{t(registering ? 'login' : 'register')}</button>
      {!registering && <button onClick={() => { setRecovering(true); setError(''); setNotice('') }}>{t('forgotPassword')}</button>}
    </section></main>
  const manager = profile.membership?.tenant_available && profile.membership.role === 'organization_manager'
  const studentAdmin = profile.membership?.tenant_available && ['organization_manager', 'staff'].includes(profile.membership.role) || !!support
  const learner = profile.membership?.tenant_available && profile.membership.role === 'student'
  return <div className="app-shell"><aside className="sidebar"><div className="brand-mark">S</div><strong>SynapseLMS</strong><p>{support?.name || profile.membership?.organization_name || t('root')}</p>
    <nav aria-label="Navigation"><NavLink to="/" end>{t('profile')}</NavLink><NavLink to="/sessions">{t('sessions')}</NavLink>{profile.is_root_admin && <NavLink to="/centers">{t('centers')}</NavLink>}{(manager || support) && <><NavLink to="/members">{t('members')}</NavLink><NavLink to="/invitations">{t('invitations')}</NavLink></>}{studentAdmin && <NavLink to="/students">{t('students')}</NavLink>}{learner && <NavLink to="/student-profile">{t('myStudentProfile')}</NavLink>}</nav></aside>
    <main><header className="topbar"><span>{profile.display_name || profile.email}</span><div className="topbar-actions">{languageButton}<button disabled={busy} onClick={() => void logout()}>{t('logout')}</button></div></header>
      <section className="content">{messages}{support && <div className="card support-banner"><span>{t('supporting')}: {support.name}</span><button onClick={async () => {
        try { await api(`/admin/support-sessions/${support.id}`, 'DELETE'); setSupportSession(null); setSupport(null) }
        catch (e) { showError(e) }
      }}>{t('endSupport')}</button></div>}
      <Routes><Route index element={<><h1>{t('welcome')}</h1><article className="card profile-card"><h2>{t('profile')}</h2><p>{profile.display_name}</p><p>{profile.email}</p><p>{t(profile.is_root_admin ? 'root' : profile.membership?.role || 'student')}</p>
        <VerificationStatus language={language} email={profile.email} verified={!!profile.email_verified_at} />
        {!profile.is_root_admin && !profile.membership?.tenant_available && <p role="status">{t('unavailable')}</p>}</article>
        <form className="card compact-form" onSubmit={passwordChange}><h2>{t('passwordChange')}</h2><label>{t('currentPassword')}<input name="currentPassword" type="password" autoComplete="current-password" required /></label><label>{t('newPassword')}<input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label><button className="primary" disabled={busy}>{t('save')}</button></form></>} />
        <Route path="centers" element={profile.is_root_admin ? <Centers language={language} onSupport={(id, name) => { setSupportSession(id); setSupport({ id, name }) }} /> : <Navigate to="/" replace />} />
        <Route path="sessions" element={<Sessions language={language} />} />
        <Route path="students" element={studentAdmin ? <Students key={support?.id || profile.membership?.id} language={language} /> : <Navigate to="/" replace />} />
        <Route path="student-profile" element={learner ? <Students key={profile.membership?.id} language={language} personal displayName={profile.display_name || ''} /> : <Navigate to="/" replace />} />
        <Route path="invitations" element={manager || support ? <Invitations key={support?.id || profile.membership?.id} language={language} root={profile.is_root_admin} /> : <Navigate to="/" replace />} />
        <Route path="members" element={manager || support ? <Members key={support?.id || profile.membership?.id} language={language} root={profile.is_root_admin} actorId={profile.id} /> : <Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} /></Routes>
      </section></main></div>
}
