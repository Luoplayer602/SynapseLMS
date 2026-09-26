import { useEffect, useState } from 'react'
import { api, ApiError } from './api'
import { errorMessage, translate } from './i18n'
import type { Language } from './i18n'
import type { Metadata } from './Courses'

type Options = { languages: Metadata[]; frameworks: Metadata[]; levels: Metadata[] }
interface Page<T> { items: T[]; total: number }
export interface Proficiency {
  id: string; version: number; language_id: string; framework_id: string;
  self_level_id: string | null; self_declared_at: string | null; verified_level_id: string | null;
  verified_at: string | null; verified_by_name: string | null; goal_level_id: string | null;
  goal_text: string; target_date: string | null; goals_updated_at: string | null;
  language: Metadata; framework: Metadata; self_level: Metadata | null; verified_level: Metadata | null;
  goal_level: Metadata | null; verification_source?: string; evidence?: string;
}
interface HistoryEntry extends Proficiency {
  action: string; actor_name: string | null; actor_role: string; occurred_at: string;
  internal?: { source: string; evidence: string; reason: string };
}
const failure = (e: unknown) => e instanceof ApiError ? e.code : 'REQUEST_FAILED'
const formatTime = (s: string | null, language: Language) => s ? new Date(s).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB') : '—'
async function optionsFor(kind: keyof Options) {
  const result: Metadata[] = []
  let total = 1
  while (result.length < total) {
    const page = await api<Page<Metadata>>(`/student-proficiency-options/${kind}?limit=100&offset=${result.length}`)
    result.push(...page.items); total = page.total
    if (!page.items.length) break
  }
  return result.sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0) || a.name.localeCompare(b.name))
}

export function Proficiencies({ language, profileId, personal, archived }: { language: Language; profileId: string; personal: boolean; archived: boolean }) {
  const t = (key: string) => translate(language, key)
  const base = `/student-proficiencies/${personal ? 'me' : profileId}`
  const [page, setPage] = useState<Page<Proficiency> | null>(null)
  const [options, setOptions] = useState<Options>({ languages: [], frameworks: [], levels: [] })
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState<Proficiency | null>(null)
  const [offset, setOffset] = useState(0)
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [languageId, setLanguageId] = useState('')
  const [framework, setFramework] = useState('')
  useEffect(() => {
    let cancelled = false
    Promise.all([api<Page<Proficiency> | Proficiency>(selected ? `${base}/${selected}` : `${base}?offset=${offset}`), optionsFor('languages'), optionsFor('frameworks'), optionsFor('levels')])
      .then(([data, languages, frameworks, levels]) => { if (!cancelled) { if ('items' in data) setPage(data); else setDetail(data); setOptions({ languages, frameworks, levels }) } })
      .catch(e => { if (!cancelled) setError(failure(e)) }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [base, selected, offset, revision])
  function refresh() { setError(''); setLoading(true); setRevision(n => n + 1) }
  function changed(item: Proficiency) { setDetail(item); setSelected(item.id); setSaved(true) }
  return <section><h2>{t('proficiencies')}</h2><p>{t('proficiencyHint')}</p>
    {archived && <p>{t('proficiencyArchived')}</p>}
    {error && <p role="alert" className="error">{saved && t('savedReloadFailed')} {errorMessage(language, error)}</p>}
    {saved && <p role="status">{t('proficiencySaved')}</p>}
    {loading && <p role="status">{t('loading')}</p>}
    <div className="session-actions"><button disabled={loading} onClick={refresh}>{t('refreshProficiencies')}</button>{selected && <button onClick={() => { setSelected(''); setDetail(null); setSaved(false); refresh() }}>{t('backToProficiencies')}</button>}</div>
    {!loading && !error && !selected && <>
      {!archived && <form aria-label={t('addProficiency')} className="card compact-form" onSubmit={async e => {
        e.preventDefault(); setLoading(true); setError(''); setSaved(false)
        try { changed(await api<Proficiency>(base, 'POST', { framework_id: framework })) }
        catch (err) { setError(failure(err)) } finally { setLoading(false) }
      }}><h3>{t('addProficiency')}</h3><label>{t('courseLanguage')}<select required value={languageId} onChange={e => { setLanguageId(e.target.value); setFramework('') }}><option value="">{t('notSelected')}</option>{options.languages.map(x => <option key={x.id} value={x.id}>{x.name} ({x.code})</option>)}</select></label>
        <label>{t('levelFramework')}<select required value={framework} onChange={e => setFramework(e.target.value)}><option value="">{t('notSelected')}</option>{options.frameworks.filter(x => x.language_id === languageId).map(x => <option key={x.id} value={x.id}>{x.name} ({x.code})</option>)}</select></label><button>{t('addProficiency')}</button>
        {!options.frameworks.length && <p>{t('proficiencyNoOptions')}</p>}</form>}
      {!page?.items.length && <p>{t('noProficiencies')}</p>}
      {page?.items.map(item => <article className="card" key={item.id}><h3>{item.language.name} · {item.framework.name}</h3><Summary item={item} language={language} />
        <button onClick={() => { setSelected(item.id); setDetail(null); setSaved(false); setLoading(true) }}>{t('viewProficiency')}</button></article>)}
      {page && <Pager language={language} offset={offset} total={page.total} onPage={n => { setOffset(n); setLoading(true) }} />}
    </>}
    {!loading && !error && selected && detail && <ProficiencyEditor key={`${detail.id}:${detail.version}:${revision}`} language={language} personal={personal} archived={archived} item={detail} levels={options.levels.filter(x => x.framework_id === detail.framework_id)} path={`${base}/${detail.id}`} onSaved={changed} />}
  </section>
}

function Summary({ item, language }: { item: Proficiency; language: Language }) {
  const t = (key: string) => translate(language, key)
  return <div className="course-detail"><p>{t('selfDeclared')}: {item.self_declared_at ? item.self_level?.name || t('unknownLevel') : t('notDeclared')} · {formatTime(item.self_declared_at, language)}</p>
    <p>{t('centerVerified')}: {item.verified_level?.name || t('notVerified')} · {formatTime(item.verified_at, language)} {item.verified_by_name}</p>
    <p>{t('learningGoal')}: {item.goal_text || '—'}</p><p>{t('targetLevel')}: {item.goal_level?.name || '—'} · {t('targetDate')}: {item.target_date || '—'}</p><p>{t('goalsUpdatedAt')}: {formatTime(item.goals_updated_at, language)}</p></div>
}

export function ProficiencyEditor({ language, personal, archived, item, levels, path, onSaved }: {
  language: Language; personal: boolean; archived: boolean; item: Proficiency; levels: Metadata[];
  path: string; onSaved: (item: Proficiency) => void;
}) {
  const t = (key: string) => translate(language, key)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [verification, setVerification] = useState('')
  const [history, setHistory] = useState(false)
  const disabled = archived || busy || error === 'PROFICIENCY_CONFLICT' || error === 'STUDENT_ARCHIVED'
  async function save(action: string, payload: object) {
    if (disabled) return
    setBusy(true); setError('')
    try { onSaved(await api<Proficiency>(`${path}/${action}`, action === 'verification' ? 'POST' : 'PATCH', { version: item.version, ...payload })) }
    catch (err) { setError(failure(err)) } finally { setBusy(false) }
  }
  const choices = <>{levels.map(x => <option key={x.id} value={x.id}>{x.name} ({x.code})</option>)}</>
  return <article className="card"><h3>{item.language.name} · {item.framework.name}</h3><Summary item={item} language={language} />
    {error && <p role="alert" className="error">{error === 'REQUEST_FAILED' ? t('mutationUncertain') : errorMessage(language, error)}</p>}
    {personal && <form aria-label={t('selfDeclared')} className="compact-form" onSubmit={e => { e.preventDefault(); void save('declaration', { self_level_id: new FormData(e.currentTarget).get('self') || null }) }}>
      <fieldset className="profile-fields" disabled={disabled}><label>{t('selfDeclared')}<select name="self" defaultValue={item.self_level_id || ''}><option value="">{t('unknownLevel')}</option>{choices}</select></label><button>{t('saveDeclaration')}</button></fieldset></form>}
    <form aria-label={t('learningGoal')} className="compact-form" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void save('goals', { goal_text: data.get('goal'), goal_level_id: data.get('target') || null, target_date: data.get('date') || null }) }}>
      <fieldset className="profile-fields" disabled={disabled}><label>{t('learningGoal')}<textarea name="goal" defaultValue={item.goal_text} maxLength={5000} /></label>
        <label>{t('targetLevel')}<select name="target" defaultValue={item.goal_level_id || ''}><option value="">{t('notSelected')}</option>{choices}</select></label>
        <label>{t('targetDate')}<input type="date" name="date" defaultValue={item.target_date || ''} /></label><button>{t('saveGoals')}</button></fieldset></form>
    {!personal && <><h4>{t('verificationInternal')}</h4><p>{item.verification_source || '—'}</p><p>{item.evidence || '—'}</p><div className="session-actions">
      <button disabled={disabled || !!verification} onClick={() => setVerification('verify')}>{t('verifyProficiency')}</button>{item.verified_at && <button disabled={disabled || !!verification} onClick={() => setVerification('revoke')}>{t('revokeProficiency')}</button>}</div>
      {verification && <form aria-label={t('verificationForm')} className="compact-form" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); void save('verification', { action: verification, reason: data.get('reason'), ...(verification === 'verify' ? { level_id: data.get('level'), source: data.get('source'), evidence: data.get('evidence') } : {}) }) }}>
        <fieldset className="profile-fields" disabled={disabled}><p>{t('verificationHint')}</p>{verification === 'verify' && <>
          <label>{t('verifiedLevel')}<select name="level" required defaultValue={item.verified_level_id || ''}><option value="">{t('notSelected')}</option>{choices}</select></label>
          <label>{t('verificationSource')}<input name="source" required maxLength={500} defaultValue={item.verification_source || ''} /></label>
          <label>{t('verificationEvidence')}<textarea name="evidence" required maxLength={5000} defaultValue={item.evidence || ''} /></label></>}
          <label>{t('reason')}<input name="reason" minLength={3} maxLength={500} required /></label><div className="session-actions"><button>{t('confirm')}</button><button type="button" onClick={() => setVerification('')}>{t('cancel')}</button></div></fieldset></form>}
    </>}
    <button onClick={() => setHistory(!history)}>{t(history ? 'hideProficiencyHistory' : 'proficiencyHistory')}</button>
    {history && <History path={path} language={language} personal={personal} />}
  </article>
}

function Pager({ language, offset, total, onPage }: { language: Language; offset: number; total: number; onPage: (n: number) => void }) {
  const t = (key: string) => translate(language, key)
  return <div className="session-actions"><button disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - 20))}>{t('previousPage')}</button><span>{total ? offset + 1 : 0}–{Math.min(offset + 20, total)} / {total}</span><button disabled={offset + 20 >= total} onClick={() => onPage(offset + 20)}>{t('nextPage')}</button></div>
}

function History({ path, language, personal }: { path: string; language: Language; personal: boolean }) {
  const t = (key: string) => translate(language, key)
  const [page, setPage] = useState<Page<HistoryEntry> | null>(null)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    api<Page<HistoryEntry>>(`${path}/history?offset=${offset}`).then(data => { if (!cancelled) setPage(data) }).catch(e => { if (!cancelled) setError(failure(e)) })
    return () => { cancelled = true }
  }, [path, offset])
  return <section><h4>{t('proficiencyHistory')}</h4>{error && <p role="alert">{errorMessage(language, error)}</p>}{!page && !error && <p>{t('loading')}</p>}
    {!error && page?.items.map(entry => <article className="card" key={entry.id}><h4>{t(`proficiency_${entry.action}`)} · v{entry.version}</h4><p>{entry.actor_name || t(entry.actor_role)} · {t(entry.actor_role)} · {formatTime(entry.occurred_at, language)}</p>
      <p>{entry.language.name} ({entry.language.code}) · {entry.framework.name} ({entry.framework.code})</p><Summary item={entry} language={language} />
      {!personal && entry.internal && <div className="course-detail"><p>{t('verificationSource')}: {entry.internal.source || '—'}</p><p>{t('verificationEvidence')}: {entry.internal.evidence || '—'}</p><p>{t('reason')}: {entry.internal.reason || '—'}</p></div>}</article>)}
    {page && <Pager language={language} offset={offset} total={page.total} onPage={n => { setPage(null); setError(''); setOffset(n) }} />}
  </section>
}
