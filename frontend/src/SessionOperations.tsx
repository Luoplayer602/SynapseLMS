import { useEffect, useState } from 'react'
import { api, ApiError } from './api'
import { optionalRequestKey } from './requestKey'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import { BusinessPage } from './ui/BusinessPage'
import type { FoundationRecord } from './Classrooms'

export interface SessionRow { id: string; version: number; status: string; class_code: string; class_name: string; branch_id: string; branch_name: string; room_id: string | null; room_name: string | null; starts_at: string; ends_at: string; timezone: string; format: string; teachers: { id: string; name: string }[] }
interface Detail { session: SessionRow; class: FoundationRecord; rooms: FoundationRecord[]; teachers: { id: string; name: string; active: boolean; qualified: boolean }[]; override_reason: string; can_edit: boolean }
interface History { id: string; actor_id: string; created_at: string; action: string; reason: string; before: SessionRow; after: SessionRow }
interface Page<T> { items: T[]; total: number }
interface Preview { before: SessionRow; after: { status: string; starts_at: string; ends_at: string; room_id: string | null; teacher_ids: string[]; can_apply: boolean; issues: string[]; conflicts: { type: string; class_code: string; starts_at: string; ends_at: string }[] } }
type Action = 'reschedule' | 'substitute' | 'cancel' | 'restore'
const failure = (e: unknown) => e instanceof ApiError ? e.code : 'REQUEST_FAILED'
const sessionStamp = (value: string, zone: string, language: Language) => new Date(value).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB', { timeZone: zone, hour12: false })
const localDay = (value: string, zone: string) => new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value))
const localTime = (value: string, zone: string) => new Intl.DateTimeFormat('en-GB', { timeZone: zone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value))

export function SessionSummary({ row, language }: { row: SessionRow; language: Language }) {
  const t = (key: string) => translate(language, key)
  return <><h3>{row.class_name} ({row.class_code})</h3><p>{t(`session_${row.status}`)} · {sessionStamp(row.starts_at, row.timezone, language)} → {sessionStamp(row.ends_at, row.timezone, language)}</p><p>{row.timezone} · {row.branch_name} · {row.room_name || t('format_online')}</p><p>{row.teachers.map(x => x.name).join(', ')}</p></>
}

export function SessionPanel({ id, language, onChanged }: { id: string; language: Language; onChanged?: (row: SessionRow) => void }) {
  const t = (key: string) => translate(language, key)
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState<Detail | null>(null)
  const [history, setHistory] = useState<Page<History> | null>(null)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    if (!open) return
    let cancelled = false
    Promise.all([api<Detail>(`/class-sessions/${id}`), api<Page<History>>(`/class-sessions/${id}/history?offset=${offset}`)])
      .then(([d, h]) => { if (!cancelled) { setDetail(d); setHistory(h) } }).catch(e => { if (!cancelled) setError(failure(e)) })
    return () => { cancelled = true }
  }, [id, open, revision, offset])
  const reload = () => { setDetail(null); setHistory(null); setError(''); setRevision(x => x + 1) }
  if (!open) return <button onClick={() => setOpen(true)}>{t('manageSession')}</button>
  return <section className="session-detail"><button onClick={() => setOpen(false)}>{t('closeSession')}</button><button onClick={reload}>{t('refreshList')}</button>
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}{!detail && !error && <p role="status">{t('loading')}</p>}
    {detail && !error && <SessionEditor key={`${detail.session.version}:${revision}`} detail={detail} language={language} onApplied={row => { onChanged?.(row); reload() }} />}
    {history && !error && <section><h4>{t('sessionHistory')}</h4>{!history.items.length && <p>{t('noSessionHistory')}</p>}{history.items.map(h => <article className="card" key={h.id}><h4>{t(`operation_${h.action}`)}</h4><p>{sessionStamp(h.created_at, 'UTC', language)} UTC · {h.actor_id}</p><p>{h.reason}</p><p>{t('sessionBefore')}</p><SessionSummary row={h.before} language={language} /><p>{t('sessionAfter')}</p><SessionSummary row={h.after} language={language} /></article>)}<button disabled={!offset} onClick={() => { setHistory(null); setOffset(Math.max(0, offset - 20)) }}>{t('previousPage')}</button><span> {history.total ? offset + 1 : 0}–{Math.min(offset + 20, history.total)} / {history.total} </span><button disabled={offset + 20 >= history.total} onClick={() => { setHistory(null); setOffset(offset + 20) }}>{t('nextPage')}</button></section>}
  </section>
}

export function SessionEditor({ detail, language, onApplied }: { detail: Detail; language: Language; onApplied: (row: SessionRow) => void }) {
  const t = (key: string) => translate(language, key)
  const row = detail.session
  const [action, setAction] = useState<Action>(row.status === 'cancelled' ? 'restore' : 'reschedule')
  const [day, setDay] = useState(localDay(row.starts_at, row.timezone))
  const [starts, setStarts] = useState(localTime(row.starts_at, row.timezone))
  const [ends, setEnds] = useState(localTime(row.ends_at, row.timezone))
  const [room, setRoom] = useState(row.room_id || '')
  const [teachers, setTeachers] = useState(row.teachers.map(x => x.id))
  const [reason, setReason] = useState('')
  const [override, setOverride] = useState(detail.override_reason)
  const [key, setKey] = useState(optionalRequestKey)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [pending, setPending] = useState<object | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [uncertain, setUncertain] = useState(false)
  const stale = ['CLASS_RESOURCE_CONFLICT', 'SESSION_REQUEST_REUSED', 'SESSION_STATE', 'SESSION_PAST'].includes(error)
  const disabled = busy || !detail.can_edit || stale || uncertain || !key
  const changed = () => { setPreview(null); setPending(null); setKey(optionalRequestKey()) }
  async function check() {
    if (!key) return
    const body = { version: row.version, action, reason, request_key: key,
      ...(action === 'reschedule' ? { day, starts_at: starts, ends_at: ends, room_id: room || null } : {}),
      ...(action === 'substitute' ? { teacher_ids: teachers, override_reason: override } : {}) }
    setBusy(true); setError(''); setPreview(null); setPending(null)
    try { setPreview(await api<Preview>(`/class-sessions/${row.id}/preview`, 'POST', body)); setPending(body) }
    catch (e) { setError(failure(e)) } finally { setBusy(false) }
  }
  async function apply() {
    if (!pending || disabled) return
    setBusy(true); setError('')
    try { const result = await api<{ session: SessionRow }>(`/class-sessions/${row.id}/operations`, 'POST', pending); onApplied(result.session) }
    catch (e) { setError(failure(e)); setPreview(null); setPending(null); if (!(e instanceof ApiError) || e.status >= 500) setUncertain(true) }
    finally { setBusy(false) }
  }
  return <section><h4>{t('sessionOperation')}</h4><p>{t('singleSessionHint')}</p><SessionSummary row={row} language={language} />
    {!detail.can_edit && <p>{t('sessionReadOnly')}</p>}{!key && <p role="alert" className="error">{errorMessage(language, 'REQUEST_KEY_UNAVAILABLE')}</p>}{error && <p role="alert" className="error">{uncertain ? t('mutationUncertain') : errorMessage(language, error)}</p>}
    <form className="compact-form" onSubmit={e => { e.preventDefault(); void check() }}><fieldset className="profile-fields" disabled={disabled}>
      <label>{t('sessionAction')}<select value={action} onChange={e => { setAction(e.target.value as Action); changed() }}>{(row.status === 'cancelled' ? ['restore'] : ['reschedule', 'substitute', 'cancel']).map(a => <option key={a} value={a}>{t(`operation_${a}`)}</option>)}</select></label>
      {action === 'reschedule' && <><label>{t('sessionDate')}<input type="date" min={detail.class.starts_on} max={detail.class.ends_on} required value={day} onChange={e => { setDay(e.target.value); changed() }} /></label><label>{t('startTime')}<input type="time" step={60} required value={starts} onChange={e => { setStarts(e.target.value); changed() }} /></label><label>{t('endTime')}<input type="time" step={60} required value={ends} onChange={e => { setEnds(e.target.value); changed() }} /></label><label>{t('sessionRoom')}<select disabled={row.format === 'online'} value={room} onChange={e => { setRoom(e.target.value); changed() }}><option value="">{t('noDefaultRoom')}</option>{detail.rooms.map(r => <option key={r.id} value={r.id} disabled={!!r.archived || (r.capacity || 0) < (detail.class.capacity || 0)}>{r.name} ({r.code})</option>)}</select></label></>}
      {action === 'substitute' && <><p>{t('qualificationHint')}</p>{detail.teachers.map(teacher => <label className="check" key={teacher.id}><input type="checkbox" checked={teachers.includes(teacher.id)} disabled={!teacher.active && !teachers.includes(teacher.id)} onChange={e => { setTeachers(e.target.checked ? [...teachers, teacher.id] : teachers.filter(id => id !== teacher.id)); changed() }} />{teacher.name} · {t(!teacher.active ? 'planningTeacherInactive' : teacher.qualified ? 'qualificationMatch' : 'qualificationWarning')}</label>)}<label>{t('qualificationReason')}<textarea value={override} maxLength={500} required={teachers.some(id => !detail.teachers.find(x => x.id === id)?.qualified)} onChange={e => { setOverride(e.target.value); changed() }} /></label></>}
      <label>{t('sessionReason')}<textarea required minLength={3} maxLength={500} value={reason} onChange={e => { setReason(e.target.value); changed() }} /></label><button>{t('previewOperation')}</button>
    </fieldset></form>
    {preview && <section className="card"><h4>{t('sessionAfter')}</h4><p>{t(`session_${preview.after.status}`)} · {sessionStamp(preview.after.starts_at, row.timezone, language)} → {sessionStamp(preview.after.ends_at, row.timezone, language)}</p><p>{detail.rooms.find(r => r.id === preview.after.room_id)?.name || t('noDefaultRoom')} · {preview.after.teacher_ids.map(id => detail.teachers.find(x => x.id === id)?.name || id).join(', ')}</p>{preview.after.issues.map(code => <p key={code} className="error">{errorMessage(language, code)}</p>)}{preview.after.conflicts.map((c, i) => <p className="error" key={i}>{t(`conflict_${c.type}`)} · {c.class_code} · {sessionStamp(c.starts_at, row.timezone, language)} → {sessionStamp(c.ends_at, row.timezone, language)}</p>)}<p>{t('manualScheduleNotice')}</p><button disabled={disabled || !preview.after.can_apply} onClick={() => void apply()}>{t('applyOperation')}</button></section>}
  </section>
}

const isoDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const shift = (day: string, count: number) => { const d = new Date(day + 'T12:00:00'); d.setDate(d.getDate() + count); return isoDay(d) }
const monday = () => { const d = new Date(); d.setDate(d.getDate() - (d.getDay() + 6) % 7); return isoDay(d) }
export function WeeklyAgenda({ language }: { language: Language }) {
  const t = (key: string) => translate(language, key)
  const [from, setFrom] = useState(monday)
  const [branch, setBranch] = useState(''), [room, setRoom] = useState(''), [teacher, setTeacher] = useState('')
  const [status, setStatus] = useState('scheduled')
  const [options, setOptions] = useState<Record<string, { id: string; name: string }[]> | null>(null)
  const [query, setQuery] = useState(() => `starts_on=${monday()}&ends_on=${shift(monday(), 6)}`)
  const [offset, setOffset] = useState(0), [revision, setRevision] = useState(0)
  const [data, setData] = useState<Page<SessionRow> | null>(null), [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    Promise.all([api<Page<SessionRow>>(`/class-sessions?${query}&offset=${offset}`), api<Record<string, { id: string; name: string }[]>>('/class-sessions/options')]).then(([d, o]) => { if (!cancelled) { setData(d); setOptions(o) } }).catch(e => { if (!cancelled) setError(failure(e)) })
    return () => { cancelled = true }
  }, [query, offset, revision])
  function load(day = from) { if (!day) return; setFrom(day); setData(null); setError(''); setOffset(0); setQuery(new URLSearchParams({ starts_on: day, ends_on: shift(day, 6), status, ...(branch ? { branch_id: branch } : {}), ...(room ? { room_id: room } : {}), ...(teacher ? { teacher_id: teacher } : {}) }).toString()); setRevision(x => x + 1) }
  const days = [...new Set(data?.items.map(row => localDay(row.starts_at, row.timezone)) || [])].sort()
  return <BusinessPage title={<>{t('weeklyAgenda')}</>} className="workflow-page"><p>{t('agendaHint')}</p><form className="card compact-form" onSubmit={e => { e.preventDefault(); load() }}><label>{t('weekFrom')}<input required type="date" value={from} onChange={e => setFrom(e.target.value)} /></label>{[['branches', branch, setBranch], ['rooms', room, setRoom], ['teachers', teacher, setTeacher]].map(([kind, value, setter]) => <label key={String(kind)}>{t(`agenda_${kind}`)}<select value={String(value)} onChange={e => (setter as (v: string) => void)(e.target.value)}><option value="">{t('agendaAll')}</option>{options?.[String(kind)]?.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>)}<label>{t('sessionStatus')}<select value={status} onChange={e => setStatus(e.target.value)}>{['scheduled', 'cancelled', 'all'].map(s => <option key={s} value={s}>{t(`session_${s}`)}</option>)}</select></label><button>{t('loadAgenda')}</button></form><button onClick={() => load(shift(from, -7))} disabled={!from}>{t('previousWeek')}</button><button onClick={() => load(shift(from, 7))} disabled={!from}>{t('nextWeek')}</button>
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}{!data && !error && <p role="status">{t('loading')}</p>}{data && !error && <>{!data.items.length && <p>{t('noConfirmedSessions')}</p>}{days.map(day => <section key={day}><h2>{day}</h2>{data.items.filter(row => localDay(row.starts_at, row.timezone) === day).map(row => <article className="card" key={row.id}><SessionSummary row={row} language={language} /><SessionPanel id={row.id} language={language} onChanged={() => load()} /></article>)}</section>)}<button disabled={!offset} onClick={() => { setData(null); setError(''); setOffset(Math.max(0, offset - 20)) }}>{t('previousPage')}</button><span> {data.total ? offset + 1 : 0}–{Math.min(offset + 20, data.total)} / {data.total} </span><button disabled={offset + 20 >= data.total} onClick={() => { setData(null); setError(''); setOffset(offset + 20) }}>{t('nextPage')}</button></>}
  </BusinessPage>
}
