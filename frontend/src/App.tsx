import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router'
import { AccountAction, EmailRequestForm, Sessions, VerificationStatus } from './Account'
import { api, ApiError, clearSession, setSupportSession, signIn, signOut } from './api'
import type { Profile } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import { Centers, Members } from './Management'
import { InvitationAcceptance, Invitations } from './Invitations'
import { Students } from './Students'
import { Courses } from './Courses'
import { Teachers } from './Teachers'
import { Classrooms } from './Classrooms'
import { TeachingSessions } from './Scheduling'
import { WeeklyAgenda } from './SessionOperations'
import { Admissions, AdmissionSettings, Attendance, Finances, MyLearning, NotificationBell, Notifications } from './Admissions'
import { EnrollmentLifecycle } from './EnrollmentLifecycle'

import { AuthForm, AuthLayout, AuthWelcome } from './AuthExperience'

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
  const [welcome, setWelcome] = useState<'restoring' | 'profile' | 'ready' | 'failed' | null>('restoring')
  const [readAttempt, setReadAttempt] = useState(0)
  const generation = useRef(0), operation = useRef(0), submitting = useRef(false)
  const [support, setSupport] = useState<{ id: string; name: string } | null>(null)
  const showError = (e: unknown) => setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED')
  const readProfile = useCallback(() => {
    const current = ++generation.current
    return api<Profile>('/auth/me').then(p => {
      if (current === generation.current) { setProfile(p); setWelcome('ready') }
    }).catch(e => {
      if (current !== generation.current) return
      setProfile(null)
      if (e instanceof ApiError && e.status === 401) setWelcome(null)
      else { setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED'); setWelcome('failed') }
    }).finally(() => { if (current === generation.current) setLoading(false) })
  }, [])
  const beginProfileRead = () => {
    setWelcome('profile'); setReadAttempt(n => n + 1); setLoading(true); setError('')
    void readProfile()
  }
  const completeWelcome = useCallback(() => setWelcome(null), [])
  const leaveWelcome = () => { generation.current += 1; setWelcome(null); setLoading(false); setProfile(null); setError('') }
  useEffect(() => {
    const signedOut = () => {
      generation.current += 1; operation.current += 1; submitting.current = false
      setProfile(null); setSupport(null); setWelcome(null); setLoading(false); setBusy(false)
    }
    window.addEventListener('synapse-signed-out', signedOut)
    void readProfile()
    return () => { generation.current += 1; operation.current += 1; window.removeEventListener('synapse-signed-out', signedOut) }
  }, [readProfile])
  useEffect(() => { document.documentElement.lang = language }, [language])

  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting.current) return
    const form = new FormData(event.currentTarget)
    const current = ++generation.current, mutation = ++operation.current
    submitting.current = true
    setBusy(true); setError(''); setNotice('')
    try {
      const email = String(form.get('email')), password = String(form.get('password'))
      if (registering) {
        await api('/auth/register', 'POST', { email, password, display_name: form.get('name'),
          ...(form.get('useInvite') ? { invite_code: form.get('invite') } : { organization_id: form.get('center') }) })
        if (current === generation.current) { setRegistering(false); setNotice('registered') }
      } else {
        await signIn(email, password)
        if (current === generation.current) beginProfileRead()
      }
    } catch (e) { if (current === generation.current) showError(e) }
    finally { if (mutation === operation.current) { submitting.current = false; setBusy(false) } }
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
  const authLayout = (children: ReactNode, isWelcome = false) => <AuthLayout language={language} onLanguage={() => setLanguage(language === 'vi' ? 'en' : 'vi')} welcome={isWelcome}>{children}</AuthLayout>
  const messages = <>{error && <p role="alert" className="error">{errorMessage(language, error)}</p>}{notice && <p role="status">{t(notice)}</p>}</>
  if (location.pathname === '/account/accept-invitation') {
    return authLayout(<InvitationAcceptance language={language} profile={profile} restoring={loading} onProfile={setProfile} />)
  }
  if (location.pathname === '/account/verify-email' || location.pathname === '/account/reset-password') {
    return authLayout(<AccountAction key={location.pathname} language={language} reset={location.pathname.endsWith('reset-password')} />)
  }
  if (welcome) return authLayout(<AuthWelcome key={readAttempt} language={language} phase={welcome} profile={profile} error={error} onRetry={beginProfileRead} onBack={leaveWelcome} onComplete={completeWelcome} />, true)
  if (!profile && recovering) return authLayout(<EmailRequestForm language={language} onBack={() => setRecovering(false)} />)
  if (!profile) return authLayout(<AuthForm key={registering ? 'register' : 'login'} language={language} registering={registering} busy={busy} error={error} notice={notice} onSubmit={authenticate}
    onMode={() => { setRegistering(!registering); setError(''); setNotice('') }} onRecovery={() => { setRecovering(true); setError(''); setNotice('') }} />)
  const manager = profile.membership?.tenant_available && profile.membership.role === 'organization_manager'
  const studentAdmin = profile.membership?.tenant_available && ['organization_manager', 'staff'].includes(profile.membership.role) || !!support
  const learner = profile.membership?.tenant_available && profile.membership.role === 'student'
  const teacher = profile.membership?.tenant_available && profile.membership.role === 'teacher'
  return <div className="app-shell"><aside className="sidebar"><div className="brand-mark">S</div><strong>SynapseLMS</strong><p>{support?.name || profile.membership?.organization_name || t('root')}</p>
    <nav aria-label="Navigation"><NavLink to="/" end>{t('profile')}</NavLink><NavLink to="/sessions">{t('sessions')}</NavLink>{profile.is_root_admin && <NavLink to="/centers">{t('centers')}</NavLink>}{(manager || support) && <><NavLink to="/members">{t('members')}</NavLink><NavLink to="/invitations">{t('invitations')}</NavLink></>}{studentAdmin && <><NavLink to="/students">{t('students')}</NavLink><NavLink to="/teachers">{t('teachers')}</NavLink><NavLink to="/courses">{t('courses')}</NavLink><NavLink to="/facilities">{t('facilities')}</NavLink><NavLink to="/classes">{t('classes')}</NavLink><NavLink to="/class-calendar">{t('weeklyAgenda')}</NavLink></>}{teacher && <><NavLink to="/teacher-profile">{t('myTeacherProfile')}</NavLink><NavLink to="/teaching-sessions">{t('myTeachingSessions')}</NavLink></>}{learner && <><NavLink to="/student-profile">{t('myStudentProfile')}</NavLink><NavLink to="/course-catalog">{t('courseCatalog')}</NavLink></>}</nav>
      <nav className="business-navigation" aria-label={language === 'vi' ? 'Nghiệp vụ học viên' : 'Student operations'}>{(studentAdmin || learner) && <><NavLink to="/admissions">{language === 'vi' ? 'Tuyển sinh' : 'Admissions'}</NavLink><NavLink to="/enrollments">{language === 'vi' ? 'Bảo lưu & hoàn phí' : 'Enrollment & refunds'}</NavLink><NavLink to="/finances">{language === 'vi' ? 'Học phí & thu tiền' : 'Fees & collections'}</NavLink></>}{studentAdmin && <NavLink to="/admission-settings">{language === 'vi' ? 'Thiết lập tuyển sinh' : 'Admission settings'}</NavLink>}{teacher && <NavLink to="/attendance">{language === 'vi' ? 'Điểm danh' : 'Attendance'}</NavLink>}{learner && <NavLink to="/my-learning">{language === 'vi' ? 'Học tập của tôi' : 'My learning'}</NavLink>}</nav></aside>
    <main><header className="topbar"><span>{profile.display_name || profile.email}</span><div className="topbar-actions">{(studentAdmin || learner || teacher) && <NotificationBell key={support?.id || profile.membership?.id} language={language} />}{languageButton}<button disabled={busy} onClick={() => void logout()}>{t('logout')}</button></div></header>
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
        <Route path="courses" element={studentAdmin ? <Courses key={support?.id || profile.membership?.id} language={language} manager={!!manager || !!support} /> : <Navigate to="/" replace />} />
        <Route path="facilities" element={studentAdmin ? <Classrooms key={support?.id || profile.membership?.id} language={language} facilities manager={!!manager || !!support} /> : <Navigate to="/" replace />} />
        <Route path="classes" element={studentAdmin ? <Classrooms key={support?.id || profile.membership?.id} language={language} /> : <Navigate to="/" replace />} />
        <Route path="class-calendar" element={studentAdmin ? <WeeklyAgenda key={support?.id || profile.membership?.id} language={language} /> : <Navigate to="/" replace />} />
        <Route path="admissions" element={studentAdmin || learner ? <Admissions key={support?.id || profile.membership?.id} language={language} staff={!!studentAdmin} /> : <Navigate to="/" replace />} />
        <Route path="admission-settings" element={studentAdmin ? <AdmissionSettings key={support?.id || profile.membership?.id} language={language} manager={!!manager || !!support} /> : <Navigate to="/" replace />} />
        <Route path="finances" element={studentAdmin || learner ? <Finances key={support?.id || profile.membership?.id} language={language} staff={!!studentAdmin} /> : <Navigate to="/" replace />} />
        <Route path="enrollments" element={studentAdmin || learner ? <EnrollmentLifecycle key={support?.id || profile.membership?.id} language={language} staff={!!studentAdmin} manager={!!manager || !!support} /> : <Navigate to="/" replace />} />
        <Route path="attendance" element={teacher ? <Attendance key={profile.membership?.id} language={language} /> : <Navigate to="/" replace />} />
        <Route path="my-learning" element={learner ? <MyLearning key={profile.membership?.id} language={language} /> : <Navigate to="/" replace />} />
        <Route path="notifications" element={studentAdmin || learner || teacher ? <Notifications key={support?.id || profile.membership?.id} language={language} role={teacher ? 'teacher' : learner ? 'student' : 'staff'} /> : <Navigate to="/" replace />} />
        <Route path="course-catalog" element={learner ? <Courses key={profile.membership?.id} language={language} catalog /> : <Navigate to="/" replace />} />
        <Route path="students" element={studentAdmin ? <Students key={support?.id || profile.membership?.id} language={language} /> : <Navigate to="/" replace />} />
        <Route path="teachers" element={studentAdmin ? <Teachers key={support?.id || profile.membership?.id} language={language} /> : <Navigate to="/" replace />} />
        <Route path="teacher-profile" element={teacher ? <Teachers key={profile.membership?.id} language={language} personal /> : <Navigate to="/" replace />} />
        <Route path="teaching-sessions" element={teacher ? <TeachingSessions key={profile.membership?.id} language={language} /> : <Navigate to="/" replace />} />
        <Route path="student-profile" element={learner ? <Students key={profile.membership?.id} language={language} personal displayName={profile.display_name || ''} /> : <Navigate to="/" replace />} />
        <Route path="invitations" element={manager || support ? <Invitations key={support?.id || profile.membership?.id} language={language} root={profile.is_root_admin} /> : <Navigate to="/" replace />} />
        <Route path="members" element={manager || support ? <Members key={support?.id || profile.membership?.id} language={language} root={profile.is_root_admin} actorId={profile.id} /> : <Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} /></Routes>
      </section></main></div>
}
