import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'

interface Guardian { full_name: string; relationship: string; phone: string; email: string | null; is_primary: boolean }
interface StudentRow { id: string; code: string; full_name: string; archived: boolean; version: number }
export interface StudentDetail extends StudentRow {
  user_id: string; email: string; date_of_birth: string | null; phone: string | null;
  address: string | null; internal_notes?: string; guardians: Guardian[]; missing_fields: string[];
}
interface Page<T> { items: T[]; total: number; limit: number; offset: number }
interface Candidate { id: string; email: string; display_name: string | null }
const failure = (e: unknown) => e instanceof ApiError ? e.code : 'REQUEST_FAILED'

function Pager({ offset, total, count, busy, language, onPage }: {
  offset: number; total: number; count: number; busy: boolean; language: Language; onPage: (n: number) => void;
}) {
  const t = (key: string) => translate(language, key)
  return <div className="session-actions"><button disabled={busy || offset === 0} onClick={() => onPage(Math.max(0, offset - 20))}>{t('previousPage')}</button>
    <span>{count ? offset + 1 : 0}–{count ? offset + count : 0} / {total}</span>
    <button disabled={busy || offset + 20 >= total} onClick={() => onPage(offset + 20)}>{t('nextPage')}</button></div>
}

export function Students({ language, personal = false, displayName = '' }: { language: Language; personal?: boolean; displayName?: string }) {
  const t = (key: string) => translate(language, key)
  const [rows, setRows] = useState<Page<StudentRow> | null>(null)
  const [detail, setDetail] = useState<StudentDetail | null>(null)
  const [selection, setSelection] = useState('')
  const [creating, setCreating] = useState(false)
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [offset, setOffset] = useState(0)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('active')
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => {
    let cancelled = false
    const path = personal ? '/students/me' : selection ? `/students/${selection}` : `/students?offset=${offset}&q=${encodeURIComponent(query)}&status=${status}`
    api<StudentDetail | Page<StudentRow>>(path).then(result => {
      if (cancelled) return
      if ('items' in result) setRows(result)
      else { setDetail(result); setCreating(false) }
    }).catch(e => {
      if (cancelled) return
      if (personal && failure(e) === 'STUDENT_NOT_FOUND') { setDetail(null); setCreating(true) }
      else setError(failure(e))
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [personal, selection, offset, query, status, revision])
  function reload() { setLoading(true); setError(''); setRevision(n => n + 1) }
  function back() { setSelection(''); setDetail(null); setCreating(false); setCandidate(null); setNotice(''); reload() }
  function saved(result: StudentDetail) {
    setDetail(result); setCreating(false); setCandidate(null); setNotice('updated'); setError('')
    if (!personal) setSelection(result.id)
  }
  const showEditor = !loading && (personal || !!selection || (creating && !!candidate)) && !error
  return <><h1>{t(personal ? 'myStudentProfile' : 'students')}</h1>
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}
    {notice && <p role="status">{t(notice)}</p>}
    {loading && <p role="status">{t('loading')}</p>}
    <div className="session-actions">
      {!personal && (selection || creating) && <button onClick={back}>{t('backToStudents')}</button>}
      <button disabled={loading} onClick={reload}>{t('refreshList')}</button>
    </div>
    {!personal && !selection && !creating && <>
      <form className="compact-form" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); setOffset(0); setQuery(String(data.get('query'))); setStatus(String(data.get('status'))); reload() }}>
        <label>{t('studentSearch')}<input name="query" maxLength={100} defaultValue={query} /></label>
        <label>{t('profileStatus')}<select name="status" defaultValue={status}><option value="active">{t('profileActive')}</option><option value="archived">{t('profileArchived')}</option><option value="all">{t('allStatuses')}</option></select></label>
        <button disabled={loading}>{t('search')}</button>
      </form>
      <button onClick={() => { setCreating(true); setNotice('') }}>{t('newStudentProfile')}</button>
      {!loading && rows?.items.length === 0 && <p>{t('empty')}</p>}
      {rows?.items.map(row => <article className="card management-card" key={row.id}><h2>{row.full_name}</h2><p>{row.code} · {t(row.archived ? 'profileArchived' : 'profileActive')}</p>
        <button disabled={loading} onClick={() => { setSelection(row.id); setDetail(null); setNotice(''); setError(''); setLoading(true) }}>{t('viewProfile')}</button></article>)}
      {rows && <Pager language={language} offset={offset} total={rows.total} count={rows.items.length} busy={loading} onPage={n => { setOffset(n); setLoading(true) }} />}
    </>}
    {!personal && creating && !candidate && <Candidates language={language} onChoose={item => { setCandidate(item); setDetail(null); setError('') }} />}
    {showEditor && (detail || creating) && <ProfileEditor key={detail ? `${detail.id}:${detail.version}:${revision}` : `new:${candidate?.id || 'me'}`} language={language} personal={personal} detail={detail}
      candidate={candidate} defaultName={displayName} onSaved={saved} />}
  </>
}

function Candidates({ language, onChoose }: { language: Language; onChoose: (item: Candidate) => void }) {
  const t = (key: string) => translate(language, key)
  const [page, setPage] = useState<Page<Candidate> | null>(null)
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let cancelled = false
    api<Page<Candidate>>(`/students/candidates?offset=${offset}&q=${encodeURIComponent(query)}`).then(data => { if (!cancelled) setPage(data) })
      .catch(e => { if (!cancelled) setError(failure(e)) }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [query, offset, revision])
  return <section><h2>{t('chooseStudentAccount')}</h2><p>{t('candidateHint')}</p>
    {error && <p role="alert">{errorMessage(language, error)}</p>}
    <form className="compact-form" onSubmit={e => { e.preventDefault(); setQuery(String(new FormData(e.currentTarget).get('query'))); setOffset(0); setLoading(true); setError(''); setRevision(n => n + 1) }}>
      <label>{t('candidateSearch')}<input name="query" maxLength={100} /></label><button disabled={loading}>{t('search')}</button></form>
    {loading && <p role="status">{t('loading')}</p>}
    {!loading && page?.items.length === 0 && <p>{t('noStudentCandidates')}</p>}
    {page?.items.map(item => <article className="card management-card" key={item.id}><p>{item.display_name || item.email}</p><p>{item.email}</p><button disabled={loading} onClick={() => onChoose(item)}>{t('chooseAccount')}</button></article>)}
    {page && <Pager language={language} offset={offset} total={page.total} count={page.items.length} busy={loading} onPage={n => { setOffset(n); setLoading(true); setError('') }} />}
  </section>
}

export function ProfileEditor({ language, personal, detail, candidate, defaultName, onSaved }: {
  language: Language; personal: boolean; detail: StudentDetail | null; candidate: Candidate | null;
  defaultName: string; onSaved: (data: StudentDetail) => void;
}) {
  const t = (key: string) => translate(language, key)
  const [guardians, setGuardians] = useState<Guardian[]>(detail?.guardians || [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmArchive, setConfirmArchive] = useState(false)
  const archived = !!detail?.archived
  const conflict = error === 'STUDENT_CONFLICT'
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('')
    const values = new FormData(event.currentTarget)
    const payload = {
      full_name: values.get('full_name'), date_of_birth: values.get('date_of_birth') || null,
      phone: values.get('phone') || null, address: values.get('address') || null,
      guardians: guardians.map(item => ({ ...item, email: item.email || null })),
      ...(!personal ? { internal_notes: values.get('internal_notes') || '' } : {}),
      ...(detail ? { version: detail.version } : !personal ? { user_id: candidate?.id } : {}),
    }
    try { onSaved(await api<StudentDetail>(personal ? '/students/me' : detail ? `/students/${detail.id}` : '/students', detail ? 'PATCH' : 'POST', payload)) }
    catch (e) { setError(failure(e)) } finally { setBusy(false) }
  }
  function changeGuardian(index: number, field: keyof Guardian, value: string | boolean) {
    setGuardians(items => items.map((item, i) => i === index ? { ...item, [field]: value } : field === 'is_primary' && value ? { ...item, is_primary: false } : item))
  }
  return <section>
    <h2>{t(detail ? 'editStudentProfile' : 'newStudentProfile')}</h2>
    {detail && <p>{detail.code} · {t(archived ? 'profileArchived' : 'profileActive')}</p>}
    <p>{detail?.email || candidate?.email}</p>
    {detail?.missing_fields.includes('phone') && <p>{t('missingPhone')}</p>}
    {archived && <p role="status">{t('archivedHint')}</p>}
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}
    <form className="card compact-form" onSubmit={save}>
      <fieldset disabled={busy || archived || conflict} className="profile-fields">
        <label>{t('name')}<input name="full_name" defaultValue={detail?.full_name || candidate?.display_name || defaultName} maxLength={200} required /></label>
        <label>{t('birthDate')}<input name="date_of_birth" type="date" max={new Date().toISOString().slice(0, 10)} defaultValue={detail?.date_of_birth || ''} /></label>
        <label>{t('phone')}<input name="phone" type="tel" minLength={5} maxLength={30} defaultValue={detail?.phone || ''} /></label>
        <label>{t('address')}<input name="address" maxLength={500} defaultValue={detail?.address || ''} /></label>
        {!personal && <label>{t('internalNotes')}<textarea name="internal_notes" maxLength={5000} defaultValue={detail?.internal_notes || ''} /></label>}
        <h3>{t('guardianContacts')}</h3><p>{t('guardianHint')}</p>
        {guardians.map((item, index) => <fieldset className="guardian-fields" key={index}><legend>{t('guardianContact')} {index + 1}</legend>
          <label>{t('name')}<input value={item.full_name} maxLength={200} required onChange={e => changeGuardian(index, 'full_name', e.target.value)} /></label>
          <label>{t('relationship')}<input value={item.relationship} maxLength={100} required onChange={e => changeGuardian(index, 'relationship', e.target.value)} /></label>
          <label>{t('phone')}<input type="tel" value={item.phone} minLength={5} maxLength={30} required onChange={e => changeGuardian(index, 'phone', e.target.value)} /></label>
          <label>{t('email')}<input type="email" value={item.email || ''} maxLength={320} onChange={e => changeGuardian(index, 'email', e.target.value)} /></label>
          <label className="check"><input type="checkbox" checked={item.is_primary} onChange={e => changeGuardian(index, 'is_primary', e.target.checked)} />{t('primaryContact')}</label>
          <button type="button" onClick={() => setGuardians(items => items.filter((_, i) => i !== index))}>{t('removeContact')}</button>
        </fieldset>)}
        <button type="button" disabled={guardians.length >= 10} onClick={() => setGuardians(items => [...items, { full_name: '', relationship: '', phone: '', email: null, is_primary: items.length === 0 }])}>{t('addContact')}</button>
        <button className="primary" disabled={busy || archived || conflict}>{t('save')}</button>
      </fieldset>
    </form>
    {!personal && detail && <>
      <button disabled={busy || conflict} onClick={() => setConfirmArchive(true)}>{t(archived ? 'restoreProfile' : 'archiveProfile')}</button>
      {confirmArchive && <form className="card compact-form" onSubmit={async e => {
        e.preventDefault(); const reason = new FormData(e.currentTarget).get('reason'); setBusy(true); setError('')
        try { onSaved(await api<StudentDetail>(`/students/${detail.id}/archive`, 'POST', { version: detail.version, archived: !archived, reason })); setConfirmArchive(false) }
        catch (err) { setError(failure(err)) } finally { setBusy(false) }
      }}><p>{t('archiveConfirmation')}</p><label>{t('reason')}<input name="reason" minLength={3} maxLength={500} required /></label><div className="session-actions">
          <button disabled={busy || conflict}>{t('confirm')}</button><button type="button" disabled={busy} onClick={() => setConfirmArchive(false)}>{t('cancel')}</button></div></form>}
    </>}
  </section>
}
