import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { api } from './api'
import type { Organization, Profile } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import './auth.css'

type LanguageProps = { language: Language; onLanguage: () => void }

function Orbit({ compact = false }: { compact?: boolean }) {
  return <div className={`auth-orbit ${compact ? 'auth-orbit-small' : ''}`} aria-hidden="true">
    <div className="auth-orbit-ring ring-one" /><div className="auth-orbit-ring ring-two" />
    <span className="auth-orbit-dot dot-one" /><span className="auth-orbit-dot dot-two" />
    <div className="auth-orbit-core">S</div><span className="auth-orbit-spark">+</span>
  </div>
}

export function AuthLayout({ language, onLanguage, children, welcome = false }: LanguageProps & { children: ReactNode; welcome?: boolean }) {
  const t = (key: string) => translate(language, key)
  return <main className={`auth-experience ${welcome ? 'auth-welcome-layout' : ''}`}>
    <header className="auth-header"><a className="auth-brand" href="/" aria-label="SynapseLMS"><span aria-hidden="true">S</span><strong>SynapseLMS</strong></a>
      <button type="button" className="auth-language" onClick={onLanguage}>{language === 'vi' ? 'English' : 'Tiếng Việt'}</button></header>
    {welcome ? children : <div className="auth-columns"><aside className="auth-art"><span className="auth-art-chip">SYNAPSE SOFT</span><div className="auth-art-copy"><h2>{t('authVisualHeading')}<br /><span>{t('authVisualHeadingAccent')}</span></h2><p>{t('authVisualCopy')}</p></div><Orbit /><p className="auth-art-footnote">{t('authTagline')} <span aria-hidden="true">✦</span></p></aside>
      <div className="auth-form-region"><div className="auth-mobile-mark" aria-hidden="true">✦</div>{children}</div></div>}
    <footer className="auth-footer">SynapseLMS <span aria-hidden="true">·</span> {t('authFooter')}</footer>
  </main>
}

function Password({ language, name, label, registering }: { language: Language; name: string; label: string; registering: boolean }) {
  const [visible, setVisible] = useState(false)
  const t = (key: string) => translate(language, key)
  return <div className="auth-field"><label htmlFor={`auth-${name}`}>{label}</label><div className="auth-password">
    <input id={`auth-${name}`} name={name} type={visible ? 'text' : 'password'} autoComplete={registering ? 'new-password' : 'current-password'} required minLength={registering ? 12 : 1} maxLength={128} />
    <button type="button" aria-label={`${t(visible ? 'hidePassword' : 'showPassword')}: ${label}`} aria-pressed={visible} onClick={() => setVisible(!visible)}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" />{visible && <path d="m3 3 18 18" />}</svg>
    </button></div></div>
}

export function AuthForm({ language, registering, busy, error, notice, onSubmit, onMode, onRecovery }: {
  language: Language; registering: boolean; busy: boolean; error: string; notice: string
  onSubmit: (event: FormEvent<HTMLFormElement>) => void; onMode: () => void; onRecovery: () => void
}) {
  const t = (key: string) => translate(language, key)
  const [useInvite, setUseInvite] = useState(false), [mismatch, setMismatch] = useState(false)
  const [centers, setCenters] = useState<Organization[]>([]), [centerState, setCenterState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [attempt, setAttempt] = useState(0)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    if (!registering) return
    let active = true
    api<Organization[]>('/organizations/public').then(data => { if (active) { setCenters(data); setCenterState('ready') } })
      .catch(() => { if (active) setCenterState('error') })
    return () => { active = false }
  }, [registering, attempt])
  useEffect(() => { heading.current?.focus() }, [])
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const data = new FormData(event.currentTarget)
    if (registering && data.get('password') !== data.get('confirmPassword')) { setMismatch(true); return }
    setMismatch(false); onSubmit(event)
  }
  return <section className="auth-panel"><div className="auth-kicker">{t(registering ? 'authKickerRegister' : 'authKickerLogin')}</div>
    <h1 ref={heading} tabIndex={-1}>{t(registering ? 'register' : 'login')}</h1><p className="auth-intro">{t(registering ? 'authRegisterHint' : 'authLoginHint')}</p>
    {(error || mismatch) && <p role="alert" className="auth-feedback auth-error">{errorMessage(language, mismatch ? 'PASSWORD_MISMATCH' : error)}</p>}
    {notice && <p role="status" className="auth-feedback auth-success">{t(notice)}</p>}
    <form onSubmit={submit}><fieldset disabled={busy} className="auth-fields">
      {registering && <label>{t('name')}<input name="name" autoComplete="name" maxLength={200} required /></label>}
      <label>{t('email')}<input name="email" type="email" placeholder="tenban@example.com" autoComplete="username" inputMode="email" autoCapitalize="none" spellCheck={false} required /></label>
      <Password language={language} name="password" label={t('password')} registering={registering} />
      {registering ? <><small className="auth-muted">{t('authPasswordHint')}</small><Password language={language} name="confirmPassword" label={t('authConfirmPassword')} registering />
        <label className="auth-check"><input type="checkbox" name="useInvite" checked={useInvite} onChange={e => setUseInvite(e.target.checked)} />{t('useInvite')}</label>
        {useInvite ? <label>{t('invite')}<input name="invite" minLength={20} maxLength={128} autoComplete="off" required /></label> : <>
          <label>{t('center')}<select name="center" defaultValue="" disabled={centerState !== 'ready' || !centers.length} required><option value="" disabled>{t('choose')}</option>{centers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
          {centerState === 'loading' && <p role="status" className="auth-muted">{t('authCentersLoading')}</p>}
          {centerState === 'error' && <div><p role="alert" className="auth-error">{t('authCentersError')}</p><button type="button" onClick={() => { setCenterState('loading'); setAttempt(n => n + 1) }}>{t('authRetryCenters')}</button></div>}
          {centerState === 'ready' && !centers.length && <p className="auth-muted">{t('noCenters')}</p>}
        </>}</> : <button type="button" className="auth-forgot" onClick={onRecovery}>{t('forgotPassword')}</button>}
      <button className="auth-submit" disabled={busy || (registering && !useInvite && (centerState !== 'ready' || !centers.length))}>{t(busy ? 'loading' : registering ? 'register' : 'login')}<span aria-hidden="true">→</span></button>
    </fieldset></form>
    <div className="auth-switch"><span>{t(registering ? 'authHaveAccount' : 'authNewHere')}</span><button type="button" disabled={busy} onClick={onMode}>{t(registering ? 'login' : 'register')}</button></div>
    <p className="auth-registration-note">{t('authStudentOnly')}</p>
  </section>
}

export function AuthWelcome({ language, phase, profile, error, onRetry, onBack, onComplete }: {
  language: Language; phase: 'restoring' | 'profile' | 'ready' | 'failed'; profile: Profile | null; error: string
  onRetry: () => void; onBack: () => void; onComplete: () => void
}) {
  const t = (key: string) => translate(language, key)
  const [elapsed, setElapsed] = useState(0)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    if (phase === 'ready' || phase === 'failed') return
    const visible = window.setTimeout(() => setElapsed(1), 140)
    const slow = window.setTimeout(() => setElapsed(5), 5000)
    const timeout = window.setTimeout(() => setElapsed(15), 15000)
    return () => { clearTimeout(visible); clearTimeout(slow); clearTimeout(timeout) }
  }, [phase])
  useEffect(() => {
    if (phase !== 'ready') return
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const timer = window.setTimeout(onComplete, reduced ? 0 : 180)
    return () => clearTimeout(timer)
  }, [phase, onComplete])
  useEffect(() => { if (elapsed === 1 || phase === 'failed') heading.current?.focus() }, [elapsed, phase])
  const visible = elapsed > 0 || phase === 'ready' || phase === 'failed'
  const retry = phase === 'failed' || elapsed >= 15
  const role = profile?.is_root_admin ? 'root' : profile?.membership?.role || 'authNeutralAccount'
  return <section className={`auth-welcome ${visible ? 'is-visible' : ''} ${phase === 'ready' ? 'is-ready' : ''}`} aria-busy={!retry && phase !== 'ready'}>
    <Orbit compact />
    <h1 ref={heading} tabIndex={-1}>{phase === 'ready' && profile ? `${t('authHello')}, ${profile.display_name || profile.email}` : t('authPreparing')}</h1>
    {phase === 'ready' && profile && <p className="auth-welcome-identity">{t(role)}{profile.membership?.organization_name && ` · ${profile.membership.organization_name}`}</p>}
    <p role="status" className="auth-welcome-status">{phase === 'failed' ? errorMessage(language, error || 'REQUEST_FAILED') : phase === 'ready' ? t('authReady') : elapsed >= 15 ? t('authTimeout') : elapsed >= 5 ? t('authSlow') : t(phase === 'restoring' ? 'authRestoring' : 'authLoadingProfile')}</p>
    {profile?.membership?.tenant_available === false && <p>{t('authTenantUnavailable')}</p>}
    {!retry && phase !== 'ready' && <div className="auth-loading-line" aria-hidden="true"><span /></div>}
    {retry && <div className="auth-retry"><button className="auth-submit" onClick={onRetry}>{t('authRetry')}</button><button onClick={onBack}>{t('backToLogin')}</button></div>}
  </section>
}
