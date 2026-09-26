import { useEffect, useState } from 'react'
import { api, ApiError } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import type { FoundationRecord } from './Classrooms'

interface TeacherOption { id: string; name: string; active: boolean; qualified: boolean }
export interface WeeklySlot { weekday: number; starts_at: string; ends_at: string; room_id: string | null; teacher_ids: string[] }
interface SessionRow { id: string; class_code: string; class_name: string; branch_name: string; room_name: string | null; starts_at: string; ends_at: string; timezone: string; format: string; teachers: { id: string; name: string }[] }
export interface PlanningContext { class: FoundationRecord; teachers: TeacherOption[]; rooms: FoundationRecord[]; assignments: { teacher_id: string; override_reason: string }[]; plan: { starts_on: string; ends_on: string; slots: WeeklySlot[]; confirmed_at: string | null } | null; sessions: SessionRow[] }
interface PreviewSession { slot: number; date: string; starts_at: string; ends_at: string; room_id: string | null; teacher_ids: string[] }
export interface SchedulePreview { version: number; timezone: string; can_confirm: boolean; preview_digest: string; sessions: PreviewSession[]; issues: { code: string; slot?: number; teacher_id?: string }[]; conflicts: { type: string; date: string; slot: number; class_code: string; starts_at: string; ends_at: string }[]; room_checks: { slot: number; unavailable_room_ids: string[] }[] }
const failure = (e: unknown) => e instanceof ApiError ? e.code : 'REQUEST_FAILED'
const stamp = (value: string, zone: string, language: Language) => new Date(value).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB', { timeZone: zone, hour12: false })

export function ClassPlanner({ classId, language, onBack }: { classId: string; language: Language; onBack: () => void }) {
  const t = (key: string) => translate(language, key)
  const [data, setData] = useState<PlanningContext | null>(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    let cancelled = false
    api<PlanningContext>(`/classes/${classId}/planning`).then(result => { if (!cancelled) setData(result) }).catch(e => { if (!cancelled) setError(failure(e)) })
    return () => { cancelled = true }
  }, [classId, revision])
  return <section><button onClick={onBack}>{t('foundationBack')}</button><button onClick={() => { setData(null); setError(''); setSaved(false); setRevision(x => x + 1) }}>{t('refreshPlanning')}</button>
    {saved && <p role="status">{t('updated')}</p>}{error && <p role="alert" className="error">{errorMessage(language, error)}</p>}{!data && !error && <p role="status">{t('loading')}</p>}
    {data && !error && <PlanningEditor key={`${data.class.version}:${revision}`} data={data} language={language} onSaved={value => { setData(value); setSaved(true) }} />}
  </section>
}

export function PlanningEditor({ data, language, onSaved }: { data: PlanningContext; language: Language; onSaved: (value: PlanningContext) => void }) {
  const t = (key: string) => translate(language, key)
  const [selected, setSelected] = useState(data.assignments.map(x => x.teacher_id))
  const [reason, setReason] = useState(data.assignments.find(x => x.override_reason)?.override_reason || '')
  const [starts, setStarts] = useState(data.plan?.starts_on || data.class.starts_on || '')
  const [ends, setEnds] = useState(data.plan?.ends_on || data.class.ends_on || '')
  const makeSlot = (): WeeklySlot => ({ weekday: 0, starts_at: '18:00', ends_at: '19:30', room_id: data.class.format === 'online' ? null : data.class.room_id || null, teacher_ids: data.assignments.map(x => x.teacher_id) })
  const [slots, setSlots] = useState<WeeklySlot[]>(data.plan?.slots.map(x => ({ ...x, room_id: data.class.format === 'online' ? null : x.room_id, teacher_ids: x.teacher_ids.filter(id => data.assignments.some(a => a.teacher_id === id)), starts_at: x.starts_at.slice(0, 5), ends_at: x.ends_at.slice(0, 5) })) || [makeSlot()])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<SchedulePreview | null>(null)
  const [dirty, setDirty] = useState(!!data.plan?.slots.some(x => (data.class.format === 'online' && x.room_id) || x.teacher_ids.some(id => !data.assignments.some(a => a.teacher_id === id))))
  const [assignmentDirty, setAssignmentDirty] = useState(false)
  const [confirmation, setConfirmation] = useState(false)
  const [confirmationKey] = useState(() => crypto.randomUUID())
  const confirmed = !!data.plan?.confirmed_at
  const locked = confirmed || data.class.status === 'archived'
  const stale = ['CLASS_RESOURCE_CONFLICT', 'SCHEDULE_LOCKED', 'SCHEDULE_PREVIEW_STALE'].includes(error)
  const disabled = busy || locked || stale
  const needsReason = selected.some(id => !data.teachers.find(x => x.id === id)?.qualified)
  const assignedIds = data.assignments.map(x => x.teacher_id)
  const path = `/classes/${data.class.id}`
  async function write(suffix: string, body: object, method = 'PUT') {
    if (disabled) return
    setBusy(true); setError('')
    try { onSaved(await api<PlanningContext>(path + suffix, method, body)) }
    catch (e) { setError(failure(e)); setConfirmation(false); setPreview(null) }
    finally { setBusy(false) }
  }
  function changed() { setDirty(true); setPreview(null); setConfirmation(false) }
  function updateSlot(index: number, fields: Partial<WeeklySlot>) { changed(); setSlots(rows => rows.map((row, i) => i === index ? { ...row, ...fields } : row)) }
  async function loadPreview() {
    setBusy(true); setError(''); setConfirmation(false); setPreview(null)
    try { setPreview(await api<SchedulePreview>(`${path}/schedule/preview?version=${data.class.version}`)) }
    catch (e) { setError(failure(e)) } finally { setBusy(false) }
  }
  return <><h2>{t('classPlanning')}: {data.class.name} ({data.class.code})</h2><p>{t('planningHint')}</p><p>{t('branchTimezone')}: {data.class.timezone}</p>
    {error && <p role="alert" className="error">{error === 'REQUEST_FAILED' ? t('mutationUncertain') : errorMessage(language, error)}</p>}
    {confirmed && <p role="status">{t('scheduleConfirmedHint')}</p>}
    <form className="card compact-form" onSubmit={e => { e.preventDefault(); void write('/teachers', { version: data.class.version, teacher_ids: selected, override_reason: reason }) }}>
      <h3>{t('classTeachers')}</h3><p>{t('qualificationHint')}</p><fieldset className="profile-fields" disabled={disabled || confirmation || dirty}>
        {!data.teachers.length && <p>{t('noPlanningTeachers')}</p>}{data.teachers.map(teacher => <label className="check" key={teacher.id}><input type="checkbox" checked={selected.includes(teacher.id)} disabled={!teacher.active && !selected.includes(teacher.id)} onChange={e => { setSelected(e.target.checked ? [...selected, teacher.id] : selected.filter(id => id !== teacher.id)); setAssignmentDirty(true); setPreview(null) }} />{teacher.name} · {t(!teacher.active ? 'planningTeacherInactive' : teacher.qualified ? 'qualificationMatch' : 'qualificationWarning')}</label>)}
        <label>{t('qualificationReason')}<textarea value={reason} required={needsReason} minLength={needsReason ? 3 : undefined} maxLength={500} onChange={e => { setReason(e.target.value); setAssignmentDirty(true); setPreview(null) }} /></label><button>{t('saveTeachers')}</button>
      </fieldset>
    </form>
    <form className="card compact-form" onSubmit={e => { e.preventDefault(); void write('/schedule', { version: data.class.version, starts_on: starts, ends_on: ends, slots }) }}>
      <h3>{t('weeklySchedule')}</h3><p>{t('weeklyScheduleLimits')}</p><fieldset className="profile-fields" disabled={disabled || confirmation || assignmentDirty}>
        <label>{t('scheduleFrom')}<input type="date" required min={data.class.starts_on} max={data.class.ends_on} value={starts} onChange={e => { setStarts(e.target.value); changed() }} /></label>
        <label>{t('scheduleTo')}<input type="date" required min={starts} max={data.class.ends_on} value={ends} onChange={e => { setEnds(e.target.value); changed() }} /></label>
        {slots.map((slot, index) => <fieldset key={index}><legend>{t('scheduleSlot')} {index + 1}</legend>
          <label>{t('weekday')}<select value={slot.weekday} onChange={e => updateSlot(index, { weekday: Number(e.target.value) })}>{[0, 1, 2, 3, 4, 5, 6].map(day => <option key={day} value={day}>{t(`weekday_${day}`)}</option>)}</select></label>
          <label>{t('startTime')}<input type="time" required step={60} value={slot.starts_at} onChange={e => updateSlot(index, { starts_at: e.target.value })} /></label><label>{t('endTime')}<input type="time" required step={60} value={slot.ends_at} onChange={e => updateSlot(index, { ends_at: e.target.value })} /></label>
          <label>{t('sessionRoom')}<select disabled={data.class.format === 'online'} value={slot.room_id || ''} onChange={e => updateSlot(index, { room_id: e.target.value || null })}><option value="">{t('noDefaultRoom')}</option>{data.rooms.map(room => {
            const unavailable = !!room.archived || (room.capacity || 0) < (data.class.capacity || 0) || !!preview?.room_checks.find(x => x.slot === index)?.unavailable_room_ids.includes(room.id)
            return <option key={room.id} value={room.id} disabled={unavailable}>{room.name} ({room.code}) · {room.capacity}{unavailable ? ` · ${t('roomUnavailable')}` : ''}</option>
          })}</select></label>
          <fieldset><legend>{t('slotTeachers')}</legend>{data.teachers.filter(teacher => assignedIds.includes(teacher.id)).map(teacher => <label className="check" key={teacher.id}><input type="checkbox" checked={slot.teacher_ids.includes(teacher.id)} onChange={e => updateSlot(index, { teacher_ids: e.target.checked ? [...slot.teacher_ids, teacher.id] : slot.teacher_ids.filter(id => id !== teacher.id) })} />{teacher.name}{!teacher.active ? ` · ${t('planningTeacherInactive')}` : ''}</label>)}</fieldset>
          <button type="button" disabled={slots.length <= 1} onClick={() => { setSlots(slots.filter((_, i) => i !== index)); changed() }}>{t('removeScheduleSlot')}</button>
        </fieldset>)}
        <button type="button" disabled={slots.length >= 14} onClick={() => { setSlots([...slots, makeSlot()]); changed() }}>{t('addScheduleSlot')}</button><button>{t('saveScheduleDraft')}</button>
      </fieldset>
    </form>
    {!locked && <section className="card"><h3>{t('schedulePreview')}</h3><p>{t('previewHint')}</p>{(dirty || assignmentDirty) && <p>{t('saveBeforePreview')}</p>}
      <button disabled={disabled || dirty || assignmentDirty || !data.plan} onClick={() => void loadPreview()}>{t('loadSchedulePreview')}</button>
      {preview && <><p>{t('sessionCount')}: {preview.sessions.length} · {preview.timezone}</p>
        {preview.issues.map((issue, i) => <p className="error" key={i}>{issue.slot === undefined ? '' : `${t('scheduleSlot')} ${issue.slot + 1}: `}{errorMessage(language, issue.code)} {data.teachers.find(x => x.id === issue.teacher_id)?.name}</p>)}
        {preview.conflicts.map((conflict, i) => <p className="error" key={i}>{t(`conflict_${conflict.type}`)} · {t('scheduleSlot')} {conflict.slot + 1} · {conflict.class_code} · {stamp(conflict.starts_at, preview.timezone, language)} → {stamp(conflict.ends_at, preview.timezone, language)}</p>)}
        <ol>{preview.sessions.map((row, index) => <li key={index}>{stamp(row.starts_at, preview.timezone, language)} → {stamp(row.ends_at, preview.timezone, language)} · {data.rooms.find(x => x.id === row.room_id)?.name || t('noDefaultRoom')} · {row.teacher_ids.map(id => data.teachers.find(x => x.id === id)?.name || id).join(', ')}</li>)}</ol>
        <button disabled={disabled || !preview.can_confirm || confirmation} onClick={() => setConfirmation(true)}>{t('confirmSchedule')}</button>
        {confirmation && <div><p>{t('confirmScheduleWarning')}</p><button disabled={disabled} onClick={() => void write('/schedule/confirm', { version: preview.version, preview_digest: preview.preview_digest, confirmation_key: confirmationKey }, 'POST')}>{t('confirm')}</button><button disabled={busy} onClick={() => setConfirmation(false)}>{t('cancel')}</button></div>}
      </>}
    </section>}
    <section><h3>{t('confirmedSessions')}</h3>{!data.sessions.length && <p>{t('noConfirmedSessions')}</p>}{data.sessions.map(row => <SessionCard key={row.id} row={row} language={language} />)}</section>
  </>
}

function SessionCard({ row, language }: { row: SessionRow; language: Language }) {
  const t = (key: string) => translate(language, key)
  return <article className="card"><h3>{row.class_name} ({row.class_code})</h3><p>{stamp(row.starts_at, row.timezone, language)} → {stamp(row.ends_at, row.timezone, language)}</p><p>{row.timezone} · {row.branch_name} · {row.room_name || t('format_online')}</p><p>{row.teachers.map(x => x.name).join(', ')}</p></article>
}

export function TeachingSessions({ language }: { language: Language }) {
  const t = (key: string) => translate(language, key)
  const [data, setData] = useState<{ items: SessionRow[]; total: number } | null>(null)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let cancelled = false
    api<{ items: SessionRow[]; total: number }>(`/teaching-sessions?offset=${offset}`).then(result => { if (!cancelled) setData(result) }).catch(e => { if (!cancelled) setError(failure(e)) })
    return () => { cancelled = true }
  }, [offset, revision])
  function reload() { setData(null); setError(''); setRevision(x => x + 1) }
  return <><h1>{t('myTeachingSessions')}</h1><p>{t('myTeachingSessionsHint')}</p><button onClick={reload}>{t('refreshList')}</button>
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}{!data && !error && <p role="status">{t('loading')}</p>}{data && !error && <>{!data.items.length && <p>{t('noConfirmedSessions')}</p>}{data.items.map(row => <SessionCard key={row.id} row={row} language={language} />)}<div className="session-actions"><button disabled={!offset} onClick={() => { setOffset(Math.max(0, offset - 20)); reload() }}>{t('previousPage')}</button><span>{data.total ? offset + 1 : 0}–{Math.min(offset + 20, data.total)} / {data.total}</span><button disabled={offset + 20 >= data.total} onClick={() => { setOffset(offset + 20); reload() }}>{t('nextPage')}</button></div></>}
  </>
}
