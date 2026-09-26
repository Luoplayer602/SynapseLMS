import { useEffect, useState } from 'react'
import { api, ApiError } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import type { CourseRecord } from './Courses'

type Kind = 'branches' | 'rooms' | 'classes'
interface Page<T> { items: T[]; total: number }
export interface FoundationRecord {
  id: string; code: string; name: string; version: number; archived?: boolean; status?: string;
  address?: string; timezone?: string; notes?: string; capacity?: number; branch_id?: string;
  branch_name?: string; branch_archived?: boolean; room_id?: string | null; room_name?: string | null;
  room_archived?: boolean; course_id?: string; course_status?: string; course_snapshot?: CourseRecord & { captured_at: string };
  starts_on?: string; ends_on?: string; format?: string;
}
export interface FoundationOptions { branches: FoundationRecord[]; rooms: FoundationRecord[]; courses: CourseRecord[] }
const pathFor = (kind: Kind) => kind === 'classes' ? '/classes' : `/facilities/${kind}`
const failure = (e: unknown) => e instanceof ApiError ? e.code : 'REQUEST_FAILED'
const archived = (item: FoundationRecord | null) => !!item && (item.archived || item.status === 'archived')
async function all<T>(path: string) {
  const rows: T[] = []; let total = 1
  while (rows.length < total) {
    const part = await api<Page<T>>(`${path}?status=all&limit=100&offset=${rows.length}`)
    rows.push(...part.items); total = part.total
    if (!part.items.length) break
  }
  return rows
}

export function Classrooms({ language, facilities = false, manager = false }: { language: Language; facilities?: boolean; manager?: boolean }) {
  const t = (key: string) => translate(language, key)
  const [facilityKind, setKind] = useState<'branches' | 'rooms'>('branches')
  const kind: Kind = facilities ? facilityKind : 'classes'
  return <><h1>{t(facilities ? 'facilities' : 'classes')}</h1><p>{t(facilities ? 'facilitiesHint' : 'draftClassHint')}</p>
    {facilities && <div className="session-actions">{(['branches', 'rooms'] as const).map(value => <button key={value} aria-pressed={kind === value} onClick={() => setKind(value)}>{t(value)}</button>)}</div>}
    <FoundationList key={kind} kind={kind} language={language} writable={!facilities || manager} />
  </>
}

function FoundationList({ kind, language, writable }: { kind: Kind; language: Language; writable: boolean }) {
  const t = (key: string) => translate(language, key)
  const [data, setData] = useState<Page<FoundationRecord> | null>(null)
  const [options, setOptions] = useState<FoundationOptions | null>(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<FoundationRecord | 'new' | null>(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState(kind === 'classes' ? 'draft' : 'active')
  const [branch, setBranch] = useState('')
  const [course, setCourse] = useState('')
  const [offset, setOffset] = useState(0)
  const [revision, setRevision] = useState(0)
  const [saved, setSaved] = useState(false)
  const path = pathFor(kind)
  useEffect(() => {
    let cancelled = false
    const params = new URLSearchParams({ q: query, status, offset: String(offset) })
    if (branch && kind !== 'branches') params.set('branch_id', branch)
    if (course && kind === 'classes') params.set('course_id', course)
    Promise.all([
      api<Page<FoundationRecord>>(`${path}?${params}`),
      all<FoundationRecord>('/facilities/branches'),
      kind === 'classes' ? all<FoundationRecord>('/facilities/rooms') : Promise.resolve([]),
      kind === 'classes' ? all<CourseRecord>('/courses') : Promise.resolve([]),
    ]).then(([result, branches, rooms, courses]) => {
      if (!cancelled) { setData(result); setOptions({ branches, rooms, courses }) }
    }).catch(e => { if (!cancelled) setError(failure(e)) })
    return () => { cancelled = true }
  }, [path, kind, query, status, branch, course, offset, revision])
  function reload() { setError(''); setData(null); setOptions(null); setEditing(null); setRevision(n => n + 1) }
  return <section><button onClick={() => { setSaved(false); reload() }}>{t('refreshList')}</button>
    {saved && <p role="status">{t('updated')}</p>}{saved && error && <p>{t('savedReloadFailed')}</p>}
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}
    {!data && !error && <p role="status">{t('loading')}</p>}
    {editing && options ? <><button onClick={() => setEditing(null)}>{t('foundationBack')}</button>
      <FoundationEditor key={editing === 'new' ? 'new' : `${editing.id}:${editing.version}`} kind={kind} language={language} writable={writable} item={editing === 'new' ? null : editing} options={options} onSaved={() => { reload(); setSaved(true) }} />
    </> : <>
      <form className="compact-form" onSubmit={e => { e.preventDefault(); const values = new FormData(e.currentTarget); setQuery(String(values.get('q'))); setStatus(String(values.get('status'))); setBranch(String(values.get('branch') || '')); setCourse(String(values.get('course') || '')); setOffset(0); setSaved(false); reload() }}>
        <label>{t('foundationSearch')}<input name="q" maxLength={100} defaultValue={query} /></label>
        <label>{t('foundationStatus')}<select name="status" defaultValue={status}><option value={kind === 'classes' ? 'draft' : 'active'}>{t(kind === 'classes' ? 'course_draft' : 'foundationActive')}</option><option value="archived">{t('profileArchived')}</option><option value="all">{t('allStatuses')}</option></select></label>
        {kind !== 'branches' && <label>{t('branch')}<select name="branch" defaultValue={branch}><option value="">{t('foundationAll')}</option>{options?.branches.map(x => <option key={x.id} value={x.id}>{x.name} ({x.code})</option>)}</select></label>}
        {kind === 'classes' && <label>{t('courseSource')}<select name="course" defaultValue={course}><option value="">{t('foundationAll')}</option>{options?.courses.map(x => <option key={x.id} value={x.id}>{x.name} ({x.code})</option>)}</select></label>}<button>{t('search')}</button>
      </form>
      {writable && <button disabled={!options || !!error} onClick={() => { setEditing('new'); setSaved(false) }}>{t(`new_${kind}`)}</button>}
      {!error && data && <>{!data.items.length && <p>{t('empty')}</p>}{data.items.map(item => <article className="card" key={item.id}><h2>{item.name}</h2><p>{item.code} · {t(archived(item) ? 'profileArchived' : kind === 'classes' ? 'course_draft' : 'foundationActive')}</p>{item.branch_name && <p>{item.branch_name}</p>}{item.course_snapshot && <p>{item.course_snapshot.name} ({item.course_snapshot.code})</p>}
        <button disabled={!options} onClick={() => { setEditing(item); setSaved(false) }}>{t('foundationDetail')}</button></article>)}
        <div className="session-actions"><button disabled={!offset} onClick={() => { setOffset(Math.max(0, offset - 20)); reload() }}>{t('previousPage')}</button><span>{data.total ? offset + 1 : 0}–{Math.min(offset + 20, data.total)} / {data.total}</span><button disabled={offset + 20 >= data.total} onClick={() => { setOffset(offset + 20); reload() }}>{t('nextPage')}</button></div></>}
    </>}
  </section>
}

export function FoundationEditor({ kind, language, writable, item, options, onSaved }: { kind: Kind; language: Language; writable: boolean; item: FoundationRecord | null; options: FoundationOptions; onSaved: () => void }) {
  const t = (key: string) => translate(language, key)
  const [branch, setBranch] = useState(item?.branch_id || '')
  const [room, setRoom] = useState(item?.room_id || '')
  const [format, setFormat] = useState(item?.format || 'offline')
  const [action, setAction] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const disabled = busy || ['CLASS_RESOURCE_CONFLICT', 'CLASS_DRAFT_REQUIRED', 'FACILITY_ARCHIVED'].includes(error)
  const inactive = archived(item)
  const path = pathFor(kind) + (item ? `/${item.id}` : '')
  async function save(method: string, payload: object, suffix = '') {
    if (disabled || !writable) return
    setBusy(true); setError('')
    try { await api(path + suffix, method, payload); onSaved() }
    catch (e) { setError(failure(e)) } finally { setBusy(false) }
  }
  const snapshot = item?.course_snapshot
  return <article className="card"><h2>{item ? `${item.name} (${item.code})` : t(`new_${kind}`)}</h2>
    {error && <p role="alert" className="error">{error === 'REQUEST_FAILED' ? t('mutationUncertain') : errorMessage(language, error)}</p>}
    {item && <p>{t(inactive ? 'profileArchived' : kind === 'classes' ? 'course_draft' : 'foundationActive')} · v{item.version}</p>}
    {snapshot && <section><h3>{t('courseSnapshot')}</h3><p>{snapshot.name} ({snapshot.code})</p><p>{snapshot.language?.name} · {snapshot.framework?.name} · {snapshot.entry_level?.name || '—'} → {snapshot.exit_level?.name}</p>
      {['description', 'objectives', 'entry_requirements', 'completion_requirements'].map(key => <p key={key}><strong>{t(`snapshot_${key}`)}: </strong>{snapshot[key as keyof CourseRecord] as string || '—'}</p>)}
      <p>{t('snapshotCaptured')}: {new Date(snapshot.captured_at).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB')}</p>
      {item.course_status !== 'published' && <p role="status">{t('sourceUnpublished')}</p>}{(item.branch_archived || item.room_archived) && <p>{t('classFacilityArchived')}</p>}
      <p>{t('branchTimezone')}: {item.timezone}</p>
    </section>}
    <form className="compact-form" onSubmit={e => {
      e.preventDefault(); const values = new FormData(e.currentTarget)
      const common = { name: values.get('name'), ...(item ? { version: item.version } : { code: values.get('code') }) }
      const fields = kind === 'branches' ? { address: values.get('address'), timezone: values.get('timezone') } : kind === 'rooms' ? { capacity: Number(values.get('capacity')), notes: values.get('notes'), ...(!item ? { branch_id: branch } : {}) } : {
        branch_id: branch, room_id: format === 'online' ? null : room || null, capacity: Number(values.get('capacity')), starts_on: values.get('starts_on'), ends_on: values.get('ends_on'), format,
        ...(!item ? { course_id: values.get('course') } : {}),
      }
      void save(item ? 'PATCH' : 'POST', { ...common, ...fields })
    }}><fieldset className="profile-fields" disabled={!writable || disabled || inactive || !!action}>
      {!item && <label>{t('foundationCode')}<input name="code" required minLength={2} maxLength={40} pattern="[A-Za-z0-9][A-Za-z0-9_-]{1,39}" /></label>}
      <label>{t('foundationName')}<input name="name" required maxLength={200} defaultValue={item?.name || ''} /></label>
      {kind === 'branches' ? <><label>{t('branchAddress')}<textarea name="address" maxLength={5000} defaultValue={item?.address || ''} /></label><label>{t('branchTimezone')}<input name="timezone" required maxLength={100} defaultValue={item?.timezone || 'Asia/Ho_Chi_Minh'} /></label></> : <>
        {kind === 'classes' && !item && <label>{t('courseSource')}<select name="course" required defaultValue=""><option value="">{t('notSelected')}</option>{options.courses.filter(x => x.status === 'published').map(x => <option key={x.id} value={x.id}>{x.name} ({x.code})</option>)}</select></label>}
        <label>{t('branch')}<select required disabled={kind === 'rooms' && !!item} value={branch} onChange={e => { setBranch(e.target.value); setRoom('') }}><option value="">{t('notSelected')}</option>{options.branches.filter(x => !x.archived || x.id === branch).map(x => <option key={x.id} value={x.id} disabled={!!x.archived}>{x.name} ({x.code}){x.archived ? ` · ${t('profileArchived')}` : ''}</option>)}</select></label>
        <label>{t('capacity')}<input name="capacity" type="number" min={1} max={10000} required defaultValue={item?.capacity || 20} /></label>
        {kind === 'rooms' ? <label>{t('roomNotes')}<textarea name="notes" maxLength={5000} defaultValue={item?.notes || ''} /></label> : <>
          <label>{t('classFormat')}<select value={format} onChange={e => { setFormat(e.target.value); if (e.target.value === 'online') setRoom('') }}>{['offline', 'online', 'hybrid'].map(x => <option key={x} value={x}>{t(`format_${x}`)}</option>)}</select></label>
          <label>{t('defaultRoom')}<select disabled={format === 'online' || !branch} value={room} onChange={e => setRoom(e.target.value)}><option value="">{t('noDefaultRoom')}</option>{options.rooms.filter(x => x.branch_id === branch && (!x.archived || x.id === room)).map(x => <option key={x.id} value={x.id} disabled={!!x.archived}>{x.name} ({x.code}) · {x.capacity}{x.archived ? ` · ${t('profileArchived')}` : ''}</option>)}</select></label>
          <label>{t('plannedStart')}<input name="starts_on" type="date" required defaultValue={item?.starts_on || ''} /></label><label>{t('plannedEnd')}<input name="ends_on" type="date" required defaultValue={item?.ends_on || ''} /></label><p>{t('draftClassHint')}</p>
        </>}
      </>}{writable && <button>{t('save')}</button>}
    </fieldset></form>
    {item && writable && <><div className="session-actions"><button disabled={disabled || !!action} onClick={() => setAction('state')}>{t(inactive ? 'foundationRestore' : 'foundationArchive')}</button>{!inactive && <button disabled={disabled || !!action} onClick={() => setAction('code')}>{t('foundationCorrectCode')}</button>}</div>
      {action && <form className="compact-form" onSubmit={e => { e.preventDefault(); const values = new FormData(e.currentTarget); void save(action === 'code' ? 'PATCH' : 'POST', { version: item.version, reason: values.get('reason'), ...(action === 'code' ? { code: values.get('code') } : kind === 'classes' ? { status: inactive ? 'draft' : 'archived' } : { archived: !inactive }) }, '/' + action) }}><fieldset className="profile-fields" disabled={disabled}>
        <p>{t(action === 'code' ? 'foundationCodeHint' : inactive ? 'foundationRestoreHint' : 'foundationArchiveHint')}</p>
        {action === 'code' && <label>{t('foundationCode')}<input name="code" required minLength={2} maxLength={40} pattern="[A-Za-z0-9][A-Za-z0-9_-]{1,39}" defaultValue={item.code} /></label>}
        <label>{t('reason')}<input name="reason" required minLength={3} maxLength={500} /></label><button>{t('confirm')}</button><button type="button" onClick={() => setAction('')}>{t('cancel')}</button>
      </fieldset></form>}
    </>}
  </article>
}
