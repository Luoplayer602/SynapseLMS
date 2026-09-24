import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'

export interface Metadata { id: string; code: string; name: string; version?: number; language_id?: string; framework_id?: string; rank?: number }
interface Settings { languages: Metadata[]; frameworks: Metadata[]; levels: Metadata[] }
export interface CourseRecord {
  id: string; code: string; name: string; description: string; objectives: string;
  entry_requirements: string; completion_requirements: string; language_id: string | null;
  framework_id: string | null; entry_level_id: string | null; exit_level_id: string | null;
  status?: string; version?: number; missing_fields?: string[];
  language: Metadata | null; framework: Metadata | null; entry_level: Metadata | null; exit_level: Metadata | null;
}
interface Page<T> { items: T[]; total: number; limit: number; offset: number }
const failure = (e: unknown) => e instanceof ApiError ? e.code : 'REQUEST_FAILED'
const emptySettings: Settings = { languages: [], frameworks: [], levels: [] }
async function allSettings(kind: keyof Settings) {
  const items: Metadata[] = []
  let total = 1
  while (items.length < total) {
    const page = await api<Page<Metadata>>(`/course-settings/${kind}?limit=100&offset=${items.length}`)
    items.push(...page.items); total = page.total
    if (!page.items.length) break
  }
  return items
}

export function Courses({ language, catalog = false, manager = false }: { language: Language; catalog?: boolean; manager?: boolean }) {
  const t = (key: string) => translate(language, key)
  const [page, setPage] = useState<Page<CourseRecord> | null>(null)
  const [settings, setSettings] = useState<Settings>(emptySettings)
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<CourseRecord | null>(null)
  const [creating, setCreating] = useState(false)
  const [configuration, setConfiguration] = useState(false)
  const [settingKind, setSettingKind] = useState<keyof Settings>('languages')
  const [filter, setFilter] = useState({ q: '', status: 'all', language_id: '', exit_level_id: '' })
  const [offset, setOffset] = useState(0)
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const base = catalog ? '/course-catalog' : '/courses'
  useEffect(() => {
    let cancelled = false
    const params = new URLSearchParams({ q: filter.q, offset: String(offset) })
    if (!catalog) params.set('status', filter.status)
    if (filter.language_id) params.set('language_id', filter.language_id)
    if (filter.exit_level_id) params.set('exit_level_id', filter.exit_level_id)
    const options = catalog ? api<{ languages: Metadata[]; levels: Metadata[] }>('/course-catalog/options').then(data => ({ ...data, frameworks: [] })) : Promise.all([allSettings('languages'), allSettings('frameworks'), allSettings('levels')]).then(([languages, frameworks, levels]) => ({ languages, frameworks, levels }))
    Promise.all([api<Page<CourseRecord> | CourseRecord>(selected ? `${base}/${selected}` : `${base}?${params}`), options])
      .then(([result, meta]) => { if (!cancelled) { setSettings(meta); if ('items' in result) setPage(result); else setDetail(result) } })
      .catch(e => { if (!cancelled) setError(failure(e)) }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [base, catalog, filter, selected, offset, revision])
  function reload() { setError(''); setLoading(true); setRevision(n => n + 1) }
  function back() { setCreating(false); setConfiguration(false); setSelected(''); setDetail(null); setNotice(''); reload() }
  function saved(item: CourseRecord) { setDetail(item); setCreating(false); setSelected(item.id); setNotice('updated') }
  return <><h1>{t(catalog ? 'courseCatalog' : 'courses')}</h1><p>{t(catalog ? 'catalogHint' : 'coursesHint')}</p>
    {error && <p role="alert" className="error">{t(notice === 'catalogDeleted' ? 'deletedReloadFailed' : notice ? 'savedReloadFailed' : 'catalogLoadFailed')} {errorMessage(language, error)}</p>}
    {notice && <p role="status">{t(notice)}</p>}
    {loading && <p role="status">{t('loading')}</p>}
    <div className="session-actions">{(selected || creating || configuration) && <button onClick={back}>{t('backToCourses')}</button>}<button disabled={loading} onClick={reload}>{t('refreshList')}</button></div>
    {!selected && !creating && !configuration && <>
      <form className="compact-form" onSubmit={e => { e.preventDefault(); const values = new FormData(e.currentTarget); setOffset(0); setFilter({ q: String(values.get('q')), status: String(values.get('status') || 'all'), language_id: String(values.get('language_id')), exit_level_id: String(values.get('exit_level_id')) }); reload() }}>
        <label>{t('courseSearch')}<input name="q" defaultValue={filter.q} maxLength={100} /></label>
        {!catalog && <label>{t('courseStatus')}<select name="status" defaultValue={filter.status}>{['all', 'draft', 'published', 'archived'].map(value => <option key={value} value={value}>{t(`course_${value}`)}</option>)}</select></label>}
        <label>{t('courseLanguage')}<select name="language_id" defaultValue={filter.language_id}><option value="">{t('allChoices')}</option>{settings.languages.map(item => <option value={item.id} key={item.id}>{item.name} ({item.code})</option>)}</select></label>
        <label>{t('exitLevel')}<select name="exit_level_id" defaultValue={filter.exit_level_id}><option value="">{t('allChoices')}</option>{settings.levels.map(item => <option value={item.id} key={item.id}>{item.name} ({item.code})</option>)}</select></label>
        <button disabled={loading}>{t('search')}</button>
      </form>
      {!catalog && <div className="session-actions"><button disabled={loading || !!error} onClick={() => { setCreating(true); setDetail(null); setNotice('') }}>{t('newCourse')}</button><button disabled={loading || !!error} onClick={() => setConfiguration(true)}>{t('courseSettings')}</button></div>}
      {!loading && !error && !page?.items.length && <p>{t('empty')}</p>}
      {!error && page?.items.map(item => <article key={item.id} className="card management-card"><h2>{item.name}</h2><p>{item.code}{item.status && ` · ${t(`course_${item.status}`)}`}</p><p>{item.language?.name} {item.exit_level && ` · ${item.exit_level.name}`}</p>
        <button disabled={loading} onClick={() => { setSelected(item.id); setDetail(null); setNotice(''); setLoading(true) }}>{t('viewCourse')}</button></article>)}
      {page && <div className="session-actions"><button disabled={loading || offset === 0} onClick={() => { setOffset(Math.max(0, offset - 20)); setLoading(true) }}>{t('previousPage')}</button><span>{page.items.length ? offset + 1 : 0}–{page.items.length ? offset + page.items.length : 0} / {page.total}</span><button disabled={loading || offset + 20 >= page.total} onClick={() => { setOffset(offset + 20); setLoading(true) }}>{t('nextPage')}</button></div>}
    </>}
    {!loading && !error && configuration && <CourseSettings language={language} manager={manager} settings={settings} initialKind={settingKind} onKind={setSettingKind} onSaved={(deleted = false) => { setNotice(deleted ? 'catalogDeleted' : 'updated'); reload() }} />}
    {!loading && !error && (creating || selected && detail) && (catalog && detail ? <article className="card course-detail"><h2>{detail.name}</h2><p>{detail.code} · {detail.language?.name} · {detail.framework?.name}</p>
      <h3>{t('courseDescription')}</h3><p>{detail.description || '—'}</p><h3>{t('entryLevel')}</h3><p>{detail.entry_level?.name || t('noEntryRequirement')}</p><p>{detail.entry_requirements || '—'}</p>
      <h3>{t('exitLevel')}</h3><p>{detail.exit_level?.name}</p><h3>{t('objectives')}</h3><p>{detail.objectives}</p><h3>{t('completionRequirements')}</h3><p>{detail.completion_requirements || '—'}</p></article> :
      <CourseEditor key={`${detail?.id || 'new'}:${detail?.version || 0}:${revision}`} language={language} manager={manager} detail={detail} settings={settings} onSaved={saved} onDeleted={() => { back(); setNotice('catalogDeleted') }} />)}
  </>
}

export function CourseEditor({ language, manager, detail, settings, onSaved, onDeleted }: { language: Language; manager: boolean; detail: CourseRecord | null; settings: Settings; onSaved: (item: CourseRecord) => void; onDeleted?: () => void }) {
  const t = (key: string) => translate(language, key)
  const [languageId, setLanguageId] = useState(detail?.language_id || '')
  const [frameworkId, setFrameworkId] = useState(detail?.framework_id || '')
  const [entry, setEntry] = useState(detail?.entry_level_id || '')
  const [exit, setExit] = useState(detail?.exit_level_id || '')
  const [action, setAction] = useState('')
  const [busy, setBusy] = useState(false)
  const [maintenance, setMaintenance] = useState(false)
  const [error, setError] = useState('')
  const conflict = error === 'COURSE_CONFLICT'
  const editable = !detail || detail.status === 'draft'
  const levels = settings.levels.filter(item => item.framework_id === frameworkId)
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setError(''); setBusy(true)
    const payload = { name: data.get('name'), description: data.get('description'), objectives: data.get('objectives'), entry_requirements: data.get('entry_requirements'), completion_requirements: data.get('completion_requirements'), language_id: languageId || null, framework_id: frameworkId || null, entry_level_id: entry || null, exit_level_id: exit || null, ...(detail ? { version: detail.version } : { code: data.get('code') }) }
    try { onSaved(await api<CourseRecord>(detail ? `/courses/${detail.id}` : '/courses', detail ? 'PATCH' : 'POST', payload)) }
    catch (e) { setError(failure(e)) } finally { setBusy(false) }
  }
  return <section><h2>{t(detail ? 'editCourse' : 'newCourse')}</h2>
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}
    {detail && <p>{detail.code} · {t(`course_${detail.status}`)}</p>}
    {!!detail?.missing_fields?.length && <p>{t('courseMissing')}: {detail.missing_fields.map(field => t(({ language_id: 'courseLanguage', exit_level_id: 'exitLevel', objectives: 'objectives' } as Record<string, string>)[field])).join(', ')}</p>}
    {!editable && <p>{t('courseReadOnly')}</p>}
    <form className="card compact-form" onSubmit={save}><fieldset className="profile-fields" disabled={busy || maintenance || conflict || !editable}>
      {!detail && <label>{t('courseCode')}<input name="code" minLength={2} maxLength={40} pattern="[A-Za-z0-9][A-Za-z0-9_-]{1,39}" required /></label>}
      <label>{t('courseName')}<input name="name" defaultValue={detail?.name || ''} maxLength={200} required /></label>
      <label>{t('courseDescription')}<textarea name="description" defaultValue={detail?.description || ''} maxLength={5000} /></label>
      <label>{t('courseLanguage')}<select value={languageId} onChange={e => { setLanguageId(e.target.value); setFrameworkId(''); setEntry(''); setExit('') }}><option value="">{t('notSelected')}</option>{settings.languages.map(item => <option key={item.id} value={item.id}>{item.name} ({item.code})</option>)}</select></label>
      <label>{t('levelFramework')}<select value={frameworkId} onChange={e => { setFrameworkId(e.target.value); setEntry(''); setExit('') }}><option value="">{t('notSelected')}</option>{settings.frameworks.filter(item => item.language_id === languageId).map(item => <option key={item.id} value={item.id}>{item.name} ({item.code})</option>)}</select></label>
      <label>{t('entryLevel')}<select value={entry} onChange={e => setEntry(e.target.value)}><option value="">{t('noEntryRequirement')}</option>{levels.map(item => <option key={item.id} value={item.id}>{item.name} ({item.code})</option>)}</select></label>
      <label>{t('exitLevel')}<select value={exit} onChange={e => setExit(e.target.value)}><option value="">{t('notSelected')}</option>{levels.map(item => <option key={item.id} value={item.id}>{item.name} ({item.code})</option>)}</select></label>
      <label>{t('objectives')}<textarea name="objectives" defaultValue={detail?.objectives || ''} maxLength={5000} /></label>
      <label>{t('entryRequirements')}<textarea name="entry_requirements" defaultValue={detail?.entry_requirements || ''} maxLength={5000} /></label>
      <label>{t('completionRequirements')}<textarea name="completion_requirements" defaultValue={detail?.completion_requirements || ''} maxLength={5000} /></label>
      <button className="primary" disabled={busy || conflict || !editable}>{t('save')}</button></fieldset></form>
    {manager && detail && <><div className="session-actions">{(detail.status === 'draft' ? ['published', 'archived'] : detail.status === 'published' ? ['draft', 'archived'] : ['draft']).map(value => <button key={value} disabled={busy || maintenance || conflict || !!action} onClick={() => setAction(value)}>{t(`setCourse_${value}`)}</button>)}</div>
      {action && <form className="card compact-form" onSubmit={async e => { e.preventDefault(); const reason = new FormData(e.currentTarget).get('reason'); setBusy(true); setError(''); try { onSaved(await api<CourseRecord>(`/courses/${detail.id}/state`, 'POST', { status: action, version: detail.version, reason })); setAction('') } catch (err) { setError(failure(err)) } finally { setBusy(false) } }}>
        <h3>{t(`setCourse_${action}`)}</h3><p>{t('courseStateHint')}</p><label>{t('reason')}<input name="reason" minLength={3} maxLength={500} required /></label><div className="session-actions"><button disabled={busy || conflict}>{t('confirm')}</button><button type="button" disabled={busy} onClick={() => setAction('')}>{t('cancel')}</button></div></form>}
    </>}
    {manager && detail?.status === 'draft' && <CatalogActions language={language} item={detail} path={`/courses/${detail.id}`} disabled={busy || conflict || !!action} onBusy={setMaintenance} onChanged={item => onSaved(item as CourseRecord)} onDeleted={() => onDeleted?.()} />}
  </section>
}

function CourseSettings({ language, manager, settings, onSaved, initialKind, onKind }: { language: Language; manager: boolean; settings: Settings; onSaved: (deleted?: boolean) => void; initialKind: keyof Settings; onKind: (kind: keyof Settings) => void }) {
  const t = (key: string) => translate(language, key)
  const [kind, setKind] = useState<keyof Settings>(initialKind)
  const [busy, setBusy] = useState(false)
  const [maintenance, setMaintenance] = useState('')
  const [error, setError] = useState('')
  const [renaming, setRenaming] = useState<Metadata | null>(null)
  const [pageIndex, setPageIndex] = useState(0)
  const rows = settings[kind]
  return <section><h2>{t('courseSettings')}</h2><p>{t('courseSettingsHint')}</p>
    {error && <p role="alert" className="error">{errorMessage(language, error)}</p>}
    <label>{t('settingKind')}<select disabled={busy || !!maintenance} value={kind} onChange={e => { const next = e.target.value as keyof Settings; setKind(next); onKind(next); setRenaming(null); setPageIndex(0); setError('') }}>{(['languages', 'frameworks', 'levels'] as const).map(value => <option value={value} key={value}>{t(`setting_${value}`)}</option>)}</select></label>
    {manager && <form key={kind} className="card compact-form" onSubmit={async e => {
      e.preventDefault(); const data = new FormData(e.currentTarget); setBusy(true); setError('')
      try { await api(`/course-settings/${kind}`, 'POST', { code: data.get('code'), name: data.get('name'), ...(kind === 'frameworks' ? { language_id: data.get('parent') } : kind === 'levels' ? { framework_id: data.get('parent'), rank: Number(data.get('rank')) } : {}) }); onSaved() }
      catch (err) { setError(failure(err)) } finally { setBusy(false) }
    }}><label>{t('settingCode')}<input name="code" minLength={2} maxLength={40} pattern="[A-Za-z0-9][A-Za-z0-9_-]{1,39}" required /></label><label>{t('settingName')}<input name="name" maxLength={200} required /></label>
      {kind !== 'languages' && <label>{t(kind === 'frameworks' ? 'courseLanguage' : 'levelFramework')}<select name="parent" required defaultValue=""><option value="" disabled>{t('notSelected')}</option>{(kind === 'frameworks' ? settings.languages : settings.frameworks).map(item => <option value={item.id} key={item.id}>{item.name} ({item.code}){item.language_id && ` · ${settings.languages.find(x => x.id === item.language_id)?.name}`}</option>)}</select></label>}
      {kind === 'levels' && <label>{t('levelRank')}<input name="rank" type="number" min={1} max={10000} required /></label>}
      <button disabled={busy || !!maintenance}>{t('create')}</button></form>}
    {renaming && <form key={renaming.id} className="card compact-form" onSubmit={async e => {
      e.preventDefault(); const name = new FormData(e.currentTarget).get('name'); setBusy(true); setError('')
      try { await api(`/course-settings/${kind}/${renaming.id}`, 'PATCH', { name, version: renaming.version }); onSaved() }
      catch (err) { setError(failure(err)) } finally { setBusy(false) }
    }}><p>{renaming.code}</p><label>{t('settingName')}<input name="name" defaultValue={renaming.name} maxLength={200} required /></label><div className="session-actions"><button disabled={busy || error === 'COURSE_CONFLICT'}>{t('save')}</button><button type="button" disabled={busy} onClick={() => setRenaming(null)}>{t('cancel')}</button></div></form>}
    {!rows.length && <p>{t('empty')}</p>}{rows.slice(pageIndex, pageIndex + 20).map(item => <article className="card management-card" key={item.id}><h3>{item.name}</h3><p>{item.code}{item.rank !== undefined && ` · ${t('levelRank')}: ${item.rank}`}</p>{item.framework_id && <p>{settings.frameworks.find(x => x.id === item.framework_id)?.name}</p>}{item.language_id && <p>{settings.languages.find(x => x.id === item.language_id)?.name}</p>}{manager && <><button disabled={busy || !!maintenance} onClick={() => setRenaming(item)}>{t('renameLabel')}</button><CatalogActions language={language} item={item} path={`/course-settings/${kind}/${item.id}`} disabled={busy || !!renaming || !!maintenance && maintenance !== item.id} onBusy={active => setMaintenance(active ? item.id : '')} onChanged={() => onSaved()} onDeleted={() => onSaved(true)} /></>}</article>)}
    <div className="session-actions"><button disabled={busy || !!maintenance || pageIndex === 0} onClick={() => setPageIndex(n => Math.max(0, n - 20))}>{t('previousPage')}</button><span>{rows.length ? pageIndex + 1 : 0}–{Math.min(pageIndex + 20, rows.length)} / {rows.length}</span><button disabled={busy || !!maintenance || pageIndex + 20 >= rows.length} onClick={() => setPageIndex(n => n + 20)}>{t('nextPage')}</button></div>
  </section>
}

export function CatalogActions({ language, item, path, disabled = false, onBusy, onChanged, onDeleted }: {
  language: Language; item: { id: string; code: string; name: string; version?: number }; path: string;
  disabled?: boolean; onBusy?: (busy: boolean) => void; onChanged: (item: unknown) => void; onDeleted: () => void;
}) {
  const t = (key: string) => translate(language, key)
  const [action, setAction] = useState<'code' | 'delete' | ''>('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [value, setValue] = useState('')
  const conflict = error === 'COURSE_CONFLICT'
  function close() { setAction(''); setError(''); onBusy?.(false) }
  return <section>
    <div className="session-actions">{(['code', 'delete'] as const).map(mode => <button key={mode} disabled={disabled || busy || !!action} onClick={() => { setAction(mode); setError(''); setValue(mode === 'code' ? item.code : ''); onBusy?.(true) }}>{t(mode === 'code' ? 'correctCode' : 'deleteCatalogItem')}</button>)}</div>
    {action && <form className="card compact-form" onSubmit={async e => {
      e.preventDefault(); if (disabled || busy || conflict) return
      const reason = new FormData(e.currentTarget).get('reason'); setBusy(true); setError('')
      try {
        const result = await api(path + (action === 'code' ? '/code' : ''), action === 'code' ? 'PATCH' : 'DELETE', { code: value, reason, version: item.version })
        if (action === 'delete') onDeleted(); else onChanged(result)
        close()
      } catch (err) { setError(failure(err)) } finally { setBusy(false) }
    }}>
      <h3>{t(action === 'code' ? 'correctCode' : 'deleteCatalogItem')}: {item.name} ({item.code})</h3>
      <p>{t(action === 'delete' ? 'catalogDeleteHint' : 'catalogCodeHint')}</p>
      {error && <p role="alert" className="error">{error === 'REQUEST_FAILED' ? t('mutationUncertain') : errorMessage(language, error)}</p>}
      <label>{t(action === 'delete' ? 'confirmCurrentCode' : 'newCode')}<input value={value} onChange={e => setValue(e.target.value)} required minLength={2} maxLength={40} pattern="[A-Za-z0-9][A-Za-z0-9_-]{1,39}" /></label>
      <label>{t('reason')}<input name="reason" required minLength={3} maxLength={500} /></label>
      <div className="session-actions"><button disabled={disabled || busy || conflict || action === 'delete' && value.trim().toUpperCase() !== item.code}>{t('confirm')}</button><button type="button" disabled={busy} onClick={close}>{t('cancel')}</button></div>
    </form>}
  </section>
}
