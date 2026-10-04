import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from './api'
import { createRequestKey, requestErrorCode } from './requestKey'
import type { Language } from './i18n'
import { errorMessage } from './i18n'
import './results.css'

type Component = { code: string; name: string; skill: string; max_score: number; weight: number }
type Scheme = { id: string; course_id: string; name: string; revision: number; status: string; version: number; components: Component[] }
type Course = { id: string; name: string }
const labels: Record<string, [string, string]> = {
  title: ['Mẫu đầu điểm', 'Grading schemes'], course: ['Khóa học', 'Course'], name: ['Tên mẫu', 'Scheme name'],
  code: ['Mã đầu điểm', 'Item code'], item: ['Tên đầu điểm', 'Item name'], skill: ['Kỹ năng', 'Skill'],
  max: ['Điểm tối đa', 'Maximum score'], weight: ['Trọng số (basis point)', 'Weight (basis points)'],
  add: ['Thêm đầu điểm', 'Add item'], remove: ['Bỏ', 'Remove'], save: ['Lưu bản nháp', 'Save draft'],
  publish: ['Công bố mẫu', 'Publish scheme'], retire: ['Ngừng dùng', 'Retire'], clone: ['Sao chép phiên bản', 'Clone revision'],
  edit: ['Sửa nháp', 'Edit draft'], cancel: ['Hủy sửa', 'Cancel edit'], refresh: ['Làm mới', 'Refresh'],
  empty: ['Chưa có mẫu.', 'No schemes yet.'], loading: ['Đang tải…', 'Loading…'],
  hint: ['Tổng trọng số phải bằng 10.000 trước khi công bố. Mẫu đã công bố không đổi sổ điểm lớp cũ.', 'Weights must total 10,000 before publishing. Published schemes do not change existing gradebooks.'],
  draft: ['Nháp', 'Draft'], published: ['Đang dùng', 'Published'], retired: ['Ngừng dùng', 'Retired'],
  listening: ['Nghe', 'Listening'], speaking: ['Nói', 'Speaking'], reading: ['Đọc', 'Reading'], writing: ['Viết', 'Writing'], general: ['Chung', 'General'],
}
const word = (language: Language, key: string) => labels[key]?.[language === 'vi' ? 0 : 1] || key
const blank = (): Component => ({ code: '', name: '', skill: 'general', max_score: 10, weight: 10000 })

export function GradingSchemes({ language, manager }: { language: Language; manager: boolean }) {
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [courseId, setCourseId] = useState('')
  const [name, setName] = useState('')
  const [parts, setParts] = useState<Component[]>([blank()])
  const [editing, setEditing] = useState<Scheme | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let active = true
    Promise.all([api<{ items: Scheme[] }>('/results/schemes?limit=100'), api<{ items: Course[] }>('/courses?limit=100')])
      .then(([a, b]) => { if (active) { setSchemes(a.items); setCourses(b.items); setLoading(false) } })
      .catch(e => { if (active) { setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED'); setLoading(false) } })
    return () => { active = false }
  }, [revision])
  const refresh = () => { setError(''); setLoading(true); setRevision(n => n + 1) }
  const reset = () => { setEditing(null); setCourseId(''); setName(''); setParts([blank()]) }
  const change = (index: number, patch: Partial<Component>) => setParts(current => current.map((p, i) => i === index ? { ...p, ...patch } : p))
  async function mutate(path: string, method: string, body: object) {
    if (busy) return
    setBusy(true); setError('')
    try { await api(path, method, { ...body, request_key: createRequestKey() }); reset(); refresh() }
    catch (e) { setError(requestErrorCode(e)) }
    finally { setBusy(false) }
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    void mutate(editing ? `/results/schemes/${editing.id}` : '/results/schemes', editing ? 'PATCH' : 'POST',
      { course_id: courseId, name, components: parts, ...(editing ? { version: editing.version } : {}) })
  }
  return <section className="result-page"><header className="result-heading"><h1>{word(language, 'title')}</h1><button onClick={refresh}>{word(language, 'refresh')}</button></header>
    {loading && <p role="status">{word(language, 'loading')}</p>}{error && <p role="alert">{errorMessage(language, error)}</p>}
    {manager && <form className="card result-form" onSubmit={submit}><fieldset disabled={busy}>
      <label>{word(language, 'course')}<select required value={courseId} disabled={!!editing} onChange={e => setCourseId(e.target.value)}><option value="">—</option>{courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>{word(language, 'name')}<input required maxLength={200} value={name} onChange={e => setName(e.target.value)} /></label>
      {parts.map((p, i) => <div className="result-part" key={i}>
        <label>{word(language, 'code')}<input required pattern="[A-Za-z0-9_-]{1,40}" value={p.code} onChange={e => change(i, { code: e.target.value })} /></label>
        <label>{word(language, 'item')}<input required value={p.name} onChange={e => change(i, { name: e.target.value })} /></label>
        <label>{word(language, 'skill')}<select value={p.skill} onChange={e => change(i, { skill: e.target.value })}>{['listening', 'speaking', 'reading', 'writing', 'general'].map(x => <option key={x} value={x}>{word(language, x)}</option>)}</select></label>
        <label>{word(language, 'max')}<input required type="number" min="0.01" max="10000" step="0.01" value={p.max_score} onChange={e => change(i, { max_score: Number(e.target.value) })} /></label>
        <label>{word(language, 'weight')}<input required type="number" min="1" max="10000" step="1" value={p.weight} onChange={e => change(i, { weight: Number(e.target.value) })} /></label>
        <button type="button" disabled={parts.length === 1} onClick={() => setParts(current => current.filter((_, n) => n !== i))}>{word(language, 'remove')}</button>
      </div>)}
      <p>{word(language, 'hint')} {parts.reduce((n, p) => n + Number(p.weight || 0), 0)} / 10000</p>
      <button type="button" onClick={() => setParts(current => [...current, blank()])}>{word(language, 'add')}</button>
      <button className="primary" type="submit">{word(language, 'save')}</button>
      {editing && <button type="button" onClick={reset}>{word(language, 'cancel')}</button>}
    </fieldset></form>}
    {!loading && !schemes.length && <p>{word(language, 'empty')}</p>}
    {schemes.map(s => <article className="card" key={s.id}><h2>{s.name} · v{s.revision}</h2>
      <p>{courses.find(c => c.id === s.course_id)?.name || s.course_id} · {word(language, s.status)}</p>
      <ul>{s.components.map(p => <li key={p.code}>{p.name} ({word(language, p.skill)}) · {p.weight}/10000 · {p.max_score}</li>)}</ul>
      {manager && <div className="result-actions">
        {s.status === 'draft' && <><button disabled={busy} onClick={() => { setEditing(s); setCourseId(s.course_id); setName(s.name); setParts(s.components.map(p => ({ ...p }))) }}>{word(language, 'edit')}</button>
          <button disabled={busy || s.components.reduce((n, p) => n + p.weight, 0) !== 10000} onClick={() => void mutate(`/results/schemes/${s.id}/publish`, 'POST', { version: s.version })}>{word(language, 'publish')}</button></>}
        {s.status === 'published' && <button disabled={busy} onClick={() => void mutate(`/results/schemes/${s.id}/retire`, 'POST', { version: s.version })}>{word(language, 'retire')}</button>}
        <button disabled={busy} onClick={() => void mutate(`/results/schemes/${s.id}/clone`, 'POST', { version: s.version })}>{word(language, 'clone')}</button>
      </div>}
    </article>)}
  </section>
}
