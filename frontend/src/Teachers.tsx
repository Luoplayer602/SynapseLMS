import { useEffect, useState } from 'react'
import { api, ApiError } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import type { Metadata } from './Courses'

interface Page<T> { items: T[]; total: number }
export interface TeacherProfile { id: string; user_id: string; full_name: string; email: string; phone: string; introduction: string; internal_notes?: string; version: number; archived: boolean }
interface Candidate { id: string; email: string; display_name: string | null }
export interface TeacherRecord { id: string; version: number; revoked_at: string | null; language_id?: string; language?: Metadata; levels?: (Metadata & { framework: Metadata })[]; name?: string; issuer?: string; issued_on?: string | null; expires_on?: string | null; expired?: boolean; internal_notes?: string }
interface HistoryRecord extends TeacherRecord { kind: string; action: string; actor_name: string | null; actor_role: string; occurred_at: string; internal?: { reason: string; internal_notes: string } }
type RecordKind = 'capabilities' | 'credentials'
type Options = { languages: Metadata[]; frameworks: Metadata[]; levels: Metadata[] }
const failure = (e: unknown) => e instanceof ApiError ? e.code : 'REQUEST_FAILED'
const blocked = (code: string) => ['TEACHER_CONFLICT', 'TEACHER_ARCHIVED', 'TEACHER_RECORD_REVOKED'].includes(code)

function Failure({ code, language, mutation = false }: { code: string; language: Language; mutation?: boolean }) {
  return code ? <p role="alert" className="error">{mutation && code === 'REQUEST_FAILED' ? translate(language, 'mutationUncertain') : errorMessage(language, code)}</p> : null
}
function Pager({ offset, total, language, onPage }: { offset: number; total: number; language: Language; onPage: (offset: number) => void }) {
  const t = (key: string) => translate(language, key)
  return <div className="session-actions"><button disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - 20))}>{t('previousPage')}</button><span>{total ? offset + 1 : 0}–{Math.min(offset + 20, total)} / {total}</span><button disabled={offset + 20 >= total} onClick={() => onPage(offset + 20)}>{t('nextPage')}</button></div>
}

export function Teachers({ language, personal = false }: { language: Language; personal?: boolean }) {
  const t = (key: string) => translate(language, key)
  const [selected, setSelected] = useState('')
  const [creating, setCreating] = useState(false)
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  return <><h1>{t(personal ? 'myTeacherProfile' : 'teachers')}</h1>
    {!personal && (selected || creating) && <button onClick={() => { setSelected(''); setCreating(false); setCandidate(null) }}>{t('backToTeachers')}</button>}
    {personal || selected ? <TeacherDetail key={personal ? 'me' : selected} language={language} personal={personal} profileRef={personal ? 'me' : selected} /> : <>
      {!creating && <button onClick={() => setCreating(true)}>{t('newTeacherProfile')}</button>}
      {candidate ? <TeacherProfileEditor language={language} personal={false} detail={null} candidate={candidate} onSaved={item => { setSelected(item.id); setCreating(false); setCandidate(null) }} /> : <TeacherList key={String(creating)} language={language} candidates={creating} onSelect={row => creating ? setCandidate(row as Candidate) : setSelected(row.id)} />}
    </>}
  </>
}

function TeacherList({ language, candidates, onSelect }: { language: Language; candidates: boolean; onSelect: (row: Candidate | TeacherProfile) => void }) {
  const t = (key: string) => translate(language, key)
  const [data, setData] = useState<Page<Candidate | TeacherProfile> | null>(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('active')
  const [offset, setOffset] = useState(0)
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    api<Page<Candidate | TeacherProfile>>(`/teachers${candidates ? '/candidates' : ''}?q=${encodeURIComponent(query)}&offset=${offset}${candidates ? '' : `&status=${status}`}`).then(result => { if (!cancelled) setData(result) }).catch(e => { if (!cancelled) setError(failure(e)) })
    return () => { cancelled = true }
  }, [candidates, query, status, offset, revision])
  function reload() { setError(''); setData(null); setRevision(n => n + 1) }
  return <section><h2>{t(candidates ? 'chooseTeacherAccount' : 'teacherList')}</h2>{candidates && <p>{t('teacherCandidateHint')}</p>}
    <form className="compact-form" onSubmit={e => { e.preventDefault(); const values = new FormData(e.currentTarget); setQuery(String(values.get('query'))); if (!candidates) setStatus(String(values.get('status'))); setOffset(0); reload() }}>
      <label>{t('teacherSearch')}<input name="query" maxLength={100} /></label>{!candidates && <label>{t('profileStatus')}<select name="status" defaultValue="active"><option value="active">{t('profileActive')}</option><option value="archived">{t('profileArchived')}</option><option value="all">{t('allStatuses')}</option></select></label>}<button>{t('search')}</button></form>
    <button onClick={reload}>{t('refreshList')}</button><Failure code={error} language={language} />
    {!data && !error && <p role="status">{t('loading')}</p>}
    {!error && data && <>{!data.items.length && <p>{t('empty')}</p>}{data.items.map(row => <article className="card" key={row.id}><h3>{'full_name' in row ? row.full_name : row.display_name || row.email}</h3><p>{row.email}</p>{'archived' in row && <p>{t(row.archived ? 'profileArchived' : 'profileActive')}</p>}<button onClick={() => onSelect(row)}>{t(candidates ? 'chooseAccount' : 'viewProfile')}</button></article>)}<Pager language={language} total={data.total} offset={offset} onPage={n => { setOffset(n); setData(null) }} /></>}
  </section>
}

function TeacherDetail({ language, personal, profileRef }: { language: Language; personal: boolean; profileRef: string }) {
  const t = (key: string) => translate(language, key)
  const [detail, setDetail] = useState<TeacherProfile | null>(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [tab, setTab] = useState('profile')
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    let cancelled = false
    api<TeacherProfile>(`/teachers/${profileRef}`).then(result => { if (!cancelled) setDetail(result) }).catch(e => { if (!cancelled) setError(failure(e)) })
    return () => { cancelled = true }
  }, [profileRef, revision])
  return <section><button onClick={() => { setError(''); setDetail(null); setSaved(false); setRevision(n => n + 1) }}>{t('refreshTeacher')}</button>
    {personal && error === 'TEACHER_NOT_FOUND' ? <p>{t('teacherProfileMissing')}</p> : <Failure code={error} language={language} />}
    {!detail && !error && <p role="status">{t('loading')}</p>}{saved && <p role="status">{t('updated')}</p>}
    {detail && !error && <><h2>{detail.full_name}</h2>{detail.archived && <p>{t('teacherArchivedHint')}</p>}
      <div className="session-actions">{['profile', 'capabilities', 'credentials', 'teacherHistory'].map(key => <button key={key} aria-pressed={tab === key} onClick={() => { setTab(key); setSaved(false) }}>{t(key)}</button>)}</div>
      {tab === 'profile' ? <TeacherProfileEditor key={`${detail.version}:${revision}`} language={language} personal={personal} detail={detail} candidate={null} onSaved={value => { setDetail(value); setSaved(true) }} /> : <TeacherRecords key={`${tab}:${revision}`} kind={tab} language={language} personal={personal} archived={detail.archived} base={`/teachers/${profileRef}`} />}
    </>}
  </section>
}

export function TeacherProfileEditor({ language, personal, detail, candidate, onSaved }: { language: Language; personal: boolean; detail: TeacherProfile | null; candidate: Candidate | null; onSaved: (value: TeacherProfile) => void }) {
  const t = (key: string) => translate(language, key)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [archive, setArchive] = useState(false)
  const disabled = busy || blocked(error)
  const path = personal ? '/teachers/me' : detail ? `/teachers/${detail.id}` : '/teachers'
  async function save(method: string, payload: object, suffix = '') {
    if (disabled) return
    setBusy(true); setError('')
    try { onSaved(await api<TeacherProfile>(path + suffix, method, payload)); setArchive(false) }
    catch (e) { setError(failure(e)) } finally { setBusy(false) }
  }
  return <article className="card"><Failure code={error} language={language} mutation /><p>{detail?.email || candidate?.email}</p>
    <form className="compact-form" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void save(detail ? 'PATCH' : 'POST', { phone: data.get('phone'), introduction: data.get('introduction'), ...(detail ? { version: detail.version } : { user_id: candidate?.id }), ...(!personal ? { full_name: data.get('full_name'), internal_notes: data.get('notes') } : {}) }) }}>
      <fieldset className="profile-fields" disabled={disabled || !!detail?.archived || archive}>
        {personal ? <p>{detail?.full_name}</p> : <label>{t('name')}<input name="full_name" required maxLength={200} defaultValue={detail?.full_name || candidate?.display_name || ''} /></label>}
        <label>{t('phone')}<input name="phone" maxLength={40} defaultValue={detail?.phone || ''} /></label><label>{t('teacherIntroduction')}<textarea name="introduction" maxLength={5000} defaultValue={detail?.introduction || ''} /></label>
        {!personal && <label>{t('teacherInternalNotes')}<textarea name="notes" maxLength={5000} defaultValue={detail?.internal_notes || ''} /></label>}<button>{t('save')}</button>
      </fieldset></form>
    {!personal && detail && <><button disabled={disabled || archive} onClick={() => setArchive(true)}>{t(detail.archived ? 'restoreProfile' : 'archiveProfile')}</button>
      {archive && <form className="compact-form" onSubmit={e => { e.preventDefault(); void save('POST', { version: detail.version, archived: !detail.archived, reason: new FormData(e.currentTarget).get('reason') }, '/archive') }}><fieldset className="profile-fields" disabled={disabled}><p>{t(detail.archived ? 'restoreProfile' : 'teacherArchiveConfirm')}</p><label>{t('reason')}<input name="reason" required minLength={3} maxLength={500} /></label><button>{t('confirm')}</button><button type="button" onClick={() => setArchive(false)}>{t('cancel')}</button></fieldset></form>}
    </>}
  </article>
}

function RecordSummary({ item, language, personal }: { item: TeacherRecord; language: Language; personal: boolean }) {
  const t = (key: string) => translate(language, key)
  return <><h3>{item.language?.name || item.name}</h3><p>{t('teacherCenterRecorded')} · {t(item.revoked_at ? 'teacherRevoked' : 'profileActive')}</p>
    {item.language ? <><p>{item.language.code}</p>{item.levels?.length ? <ul>{item.levels.map(level => <li key={level.id}>{level.framework.name} ({level.framework.code}) · {level.name} ({level.code})</li>)}</ul> : <p>{t('teacherNoLevels')}</p>}</> : <><p>{t('credentialIssuer')}: {item.issuer || '—'}</p><p>{t('credentialIssued')}: {item.issued_on || '—'} · {t('credentialExpires')}: {item.expires_on || '—'}</p>{item.expired && <p>{t('credentialExpired')}</p>}{!personal && <p>{item.internal_notes}</p>}</>}
    {item.revoked_at && <p>{new Date(item.revoked_at).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB')}</p>}</>
}

function TeacherRecords({ kind, base, language, personal, archived }: { kind: string; base: string; language: Language; personal: boolean; archived: boolean }) {
  const t = (key: string) => translate(language, key)
  const history = kind === 'teacherHistory'
  const path = `${base}/${history ? 'history' : kind}`
  const [data, setData] = useState<Page<TeacherRecord | HistoryRecord> | null>(null)
  const [offset, setOffset] = useState(0)
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [editing, setEditing] = useState<TeacherRecord | 'new' | null>(null)
  const [options, setOptions] = useState<Options>({ languages: [], frameworks: [], levels: [] })
  const [optionError, setOptionError] = useState('')
  const [optionReady, setOptionReady] = useState(false)
  useEffect(() => {
    let cancelled = false
    api<Page<TeacherRecord | HistoryRecord>>(`${path}?offset=${offset}`).then(result => { if (!cancelled) setData(result) }).catch(e => { if (!cancelled) setError(failure(e)) })
    return () => { cancelled = true }
  }, [path, offset, revision])
  useEffect(() => {
    if (personal || archived || kind !== 'capabilities') return
    let cancelled = false
    async function all(kind: string) {
      const rows: Metadata[] = []; let total = 1
      while (rows.length < total) { const part = await api<Page<Metadata>>(`/teachers/options/${kind}?limit=100&offset=${rows.length}`); rows.push(...part.items); total = part.total; if (!part.items.length) break }
      return rows
    }
    Promise.all([all('languages'), all('frameworks'), all('levels')]).then(([languages, frameworks, levels]) => { if (!cancelled) { setOptions({ languages, frameworks, levels }); setOptionReady(true) } }).catch(e => { if (!cancelled) setOptionError(failure(e)) })
    return () => { cancelled = true }
  }, [personal, archived, kind, revision])
  function refresh() { setData(null); setError(''); setOptionError(''); setOptionReady(false); setEditing(null); setRevision(n => n + 1) }
  return <section><h2>{t(kind)}</h2>{history && <p>{t('teacherHistoryHint')}</p>}{saved && <p role="status">{t('updated')}</p>}{saved && error && <p>{t('savedReloadFailed')}</p>}
    <Failure code={error || optionError} language={language} /><button onClick={() => { setSaved(false); refresh() }}>{t('refreshTeacherRecords')}</button>
    {!data && !error && <p role="status">{t('loading')}</p>}
    {!history && !personal && !archived && !editing && <button disabled={!!error || (kind === 'capabilities' && !optionReady)} onClick={() => { setEditing('new'); setSaved(false) }}>{t(kind === 'capabilities' ? 'addCapability' : 'addCredential')}</button>}
    {editing && <TeacherRecordEditor key={editing === 'new' ? 'new' : `${editing.id}:${editing.version}`} kind={kind as RecordKind} item={editing === 'new' ? null : editing} language={language} path={path} options={options} onCancel={() => setEditing(null)} onSaved={() => { refresh(); setSaved(true) }} />}
    {!editing && !error && data && <>{!data.items.length && <p>{t('empty')}</p>}{data.items.map(item => <article className="card" key={item.id}>
      <RecordSummary item={item} language={language} personal={personal} />
      {'action' in item && <><h4>{t(`teacherAction_${item.action}`)} · v{item.version}</h4><p>{item.actor_name || t(item.actor_role)} · {t(item.actor_role)} · {new Date(item.occurred_at).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB')}</p>{!personal && item.internal && <><p>{t('reason')}: {item.internal.reason}</p><p>{item.internal.internal_notes}</p></>}</>}
      {!history && !personal && !archived && <button disabled={kind === 'capabilities' && !optionReady} onClick={() => setEditing(item)}>{t('editTeacherRecord')}</button>}
    </article>)}<Pager language={language} total={data.total} offset={offset} onPage={n => { setOffset(n); setData(null); setError('') }} /></>}
  </section>
}

export function TeacherRecordEditor({ kind, item, language, path, options, onSaved, onCancel }: { kind: RecordKind; item: TeacherRecord | null; language: Language; path: string; options: Options; onSaved: () => void; onCancel: () => void }) {
  const t = (key: string) => translate(language, key)
  const [languageId, setLanguageId] = useState(item?.language_id || '')
  const [selected, setSelected] = useState<string[]>(item?.levels?.map(x => x.id) || [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [changingState, setChangingState] = useState(false)
  const disabled = busy || blocked(error)
  async function save(method: string, payload: object, suffix = '') {
    if (disabled) return
    setBusy(true); setError('')
    try { await api(path + (item ? `/${item.id}` : '') + suffix, method, payload); onSaved() }
    catch (e) { setError(failure(e)) } finally { setBusy(false) }
  }
  return <article className="card"><h3>{t(item ? 'editTeacherRecord' : kind === 'capabilities' ? 'addCapability' : 'addCredential')}</h3><Failure code={error} language={language} mutation />
    {!item?.revoked_at && !changingState && <form className="compact-form" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void save(item ? 'PATCH' : 'POST', { ...(item ? { version: item.version } : {}), reason: data.get('reason'), ...(kind === 'capabilities' ? { level_ids: selected, ...(!item ? { language_id: languageId } : {}) } : { name: data.get('name'), issuer: data.get('issuer'), issued_on: data.get('issued_on') || null, expires_on: data.get('expires_on') || null, internal_notes: data.get('notes') }) }) }}>
      <fieldset className="profile-fields" disabled={disabled}>
        {kind === 'capabilities' ? <><p>{t('teacherCapabilityHint')}</p><label>{t('courseLanguage')}<select required disabled={!!item} value={languageId} onChange={e => { setLanguageId(e.target.value); setSelected([]) }}><option value="">{t('notSelected')}</option>{options.languages.map(x => <option key={x.id} value={x.id}>{x.name} ({x.code})</option>)}</select></label>
          <fieldset><legend>{t('teachableLevels')}</legend>{options.levels.filter(x => x.language_id === languageId).sort((a, b) => (a.rank || 0) - (b.rank || 0)).map(level => <label className="check" key={level.id}><input type="checkbox" checked={selected.includes(level.id)} onChange={e => setSelected(e.target.checked ? [...selected, level.id] : selected.filter(id => id !== level.id))} />{options.frameworks.find(x => x.id === level.framework_id)?.name} · {level.name} ({level.code})</label>)}</fieldset></> : <>
          <label>{t('credentialName')}<input name="name" required maxLength={200} defaultValue={item?.name || ''} /></label><label>{t('credentialIssuer')}<input name="issuer" maxLength={200} defaultValue={item?.issuer || ''} /></label><label>{t('credentialIssued')}<input name="issued_on" type="date" defaultValue={item?.issued_on || ''} /></label><label>{t('credentialExpires')}<input name="expires_on" type="date" defaultValue={item?.expires_on || ''} /></label><label>{t('teacherInternalNotes')}<textarea name="notes" maxLength={5000} defaultValue={item?.internal_notes || ''} /></label></>}
        <label>{t('reason')}<input name="reason" required minLength={3} maxLength={500} /></label><button>{t('save')}</button>
      </fieldset></form>}
    {item && !changingState && <button disabled={disabled} onClick={() => setChangingState(true)}>{t(item.revoked_at ? 'restoreTeacherRecord' : 'revokeTeacherRecord')}</button>}
    {changingState && item && <form className="compact-form" onSubmit={e => { e.preventDefault(); void save('POST', { version: item.version, revoked: !item.revoked_at, reason: new FormData(e.currentTarget).get('reason') }, '/state') }}><fieldset className="profile-fields" disabled={disabled}><p>{t(item.revoked_at ? 'restoreTeacherRecord' : 'revokeTeacherRecord')}: {item.language?.name || item.name}</p><label>{t('reason')}<input name="reason" required minLength={3} maxLength={500} /></label><button>{t('confirm')}</button><button type="button" onClick={() => setChangingState(false)}>{t('cancel')}</button></fieldset></form>}
    <button disabled={busy} onClick={onCancel}>{t('backToTeacherRecords')}</button>
  </article>
}
