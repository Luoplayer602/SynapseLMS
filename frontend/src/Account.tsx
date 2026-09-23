import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError, clearSession } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import { useEmailLink } from './useEmailLink'

function errorCode(error: unknown) {
  return error instanceof ApiError ? error.code : 'REQUEST_FAILED'
}

export function EmailRequestForm({ language, onBack }: { language: Language; onBack: () => void }) {
  const t = (key: string) => translate(language, key)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const email = new FormData(event.currentTarget).get('email')
    setBusy(true); setError(''); setSent(false)
    try { await api('/auth/forgot-password', 'POST', { email }); setSent(true) }
    catch (e) { setError(errorCode(e)) } finally { setBusy(false) }
  }
  return <section className="card auth-card"><h1>{t('forgotPassword')}</h1>
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}
    {sent && <p role="status">{t('emailRequested')}</p>}
    <form onSubmit={submit}><label>{t('email')}<input name="email" type="email" autoComplete="email" required /></label>
      <button className="primary" disabled={busy}>{t(busy ? 'loading' : 'sendRecovery')}</button></form>
    <button onClick={onBack}>{t('backToLogin')}</button></section>
}

export function AccountAction({ language, reset }: { language: Language; reset: boolean }) {
  const link = useEmailLink()
  return <AccountActionForm key={link.version} language={language} reset={reset} token={link.token} />
}

function AccountActionForm({ language, reset, token }: { language: Language; reset: boolean; token: string }) {
  const t = (key: string) => translate(language, key)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    if (reset && form.get('password') !== form.get('confirmPassword')) { setError('PASSWORD_MISMATCH'); return }
    setBusy(true); setError('')
    try {
      await api(reset ? '/auth/reset-password' : '/auth/verify-email', 'POST',
        { token, ...(reset ? { password: form.get('password') } : {}) })
      if (reset) clearSession()
      setDone(true)
    } catch (e) { setError(errorCode(e)) } finally { setBusy(false) }
  }
  return <section className="card auth-card"><h1>{t(reset ? 'resetPassword' : 'verifyEmail')}</h1>
    {(error || !token) && <p role="alert" className="error">{errorMessage(language, error || 'INVALID_ACCOUNT_LINK')}</p>}
    {done ? <p role="status">{t(reset ? 'passwordChanged' : 'emailVerified')}</p> : <form onSubmit={submit}>
      <p>{t(reset ? 'resetHint' : 'verifyHint')}</p>
      {reset && <><label>{t('newPassword')}<input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label>
        <label>{t('confirmPassword')}<input name="confirmPassword" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label></>}
      <button className="primary" disabled={busy || !token}>{t(busy ? 'loading' : reset ? 'resetPassword' : 'verifyEmail')}</button></form>}
    <p><a href="/">{t('backToLogin')}</a></p></section>
}

export function VerificationStatus({ language, email, verified }: { language: Language; email: string; verified: boolean }) {
  const t = (key: string) => translate(language, key)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  return <div className="verification-status"><p>{t(verified ? 'emailVerified' : 'emailUnverified')}</p>
    {!verified && <button disabled={busy} onClick={async () => {
      setBusy(true); setError(''); setSent(false)
      try { await api('/auth/request-verification', 'POST', { email }); setSent(true) }
      catch (e) { setError(errorCode(e)) } finally { setBusy(false) }
    }}>{t(busy ? 'loading' : 'resendVerification')}</button>}
    {sent && <p role="status">{t('emailRequested')}</p>}
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}</div>
}

interface LoginSession { id: string; created_at: string; expires_at: string; user_agent: string | null; is_current: boolean }

export function Sessions({ language }: { language: Language }) {
  const t = (key: string) => translate(language, key)
  const [sessions, setSessions] = useState<LoginSession[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(false)
  const [reload, setReload] = useState(0)
  const [confirmation, setConfirmation] = useState<{ scope?: 'all' | 'others'; id?: string; current?: boolean } | null>(null)
  useEffect(() => {
    let cancelled = false
    api<LoginSession[]>('/auth/sessions').then(data => { if (!cancelled) setSessions(data) })
      .catch(e => { if (!cancelled) setError(errorCode(e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [reload])
  async function revoke() {
    if (!confirmation) return
    setBusy(true); setError(''); setNotice(false)
    try {
      if (confirmation.scope) await api('/auth/sessions/revoke', 'POST', { scope: confirmation.scope })
      else await api(`/auth/sessions/${confirmation.id}`, 'DELETE')
      if (confirmation.scope === 'all' || confirmation.current) clearSession()
      else { setReload(value => value + 1); setNotice(true) }
      setConfirmation(null)
    } catch (e) { setError(errorCode(e)) } finally { setBusy(false) }
  }
  const date = (value: string) => new Date(value).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US')
  return <><h1>{t('sessions')}</h1><p>{t('sessionsHint')}</p>
    {error && <p role="alert" className="error">{errorMessage(language, error)} <button onClick={() => { setError(''); setLoading(true); setReload(value => value + 1) }}>{t('retry')}</button></p>}
    {notice && <p role="status">{t('sessionsRevoked')}</p>}
    {loading ? <p role="status">{t('loading')}</p> : <>
      <div className="session-actions"><button disabled={busy || !!confirmation} onClick={() => setConfirmation({ scope: 'others' })}>{t('revokeOthers')}</button>
        <button disabled={busy || !!confirmation} onClick={() => setConfirmation({ scope: 'all' })}>{t('revokeAll')}</button></div>
      {confirmation && <section className="card management-card" aria-label={t('confirmRevocation')}><p>{t('confirmRevocation')}</p>
        <div className="session-actions"><button disabled={busy} onClick={() => void revoke()}>{t('confirm')}</button>
          <button disabled={busy} onClick={() => setConfirmation(null)}>{t('cancel')}</button></div></section>}
      {!sessions.length && <p>{t('empty')}</p>}
      {sessions.map(session => <article key={session.id} className="card management-card session-card">
        <h2>{t(session.is_current ? 'currentSession' : 'otherSession')}</h2><p className="device-label">{session.user_agent || t('unknownDevice')}</p>
        <p>{t('signedInAt')}: {date(session.created_at)}</p><p>{t('expiresAt')}: {date(session.expires_at)}</p>
        <button disabled={busy || !!confirmation} onClick={() => setConfirmation({ id: session.id, current: session.is_current })}>{t('revokeSession')}</button>
      </article>)}</> }</>
}
