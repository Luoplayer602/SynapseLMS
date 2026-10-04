import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from './api'
import { createRequestKey, requestErrorCode } from './requestKey'
import type { Language } from './i18n'
import { errorMessage } from './i18n'
import './results.css'

type ClassRow = { id: string; name: string; course_id: string; gradebook_id: string | null }
type Item = { id: string; code: string; name: string; skill: string; max_score: number; weight: number; assessed_at: string | null }
type Mark = { item_id: string; name: string; skill: string; max_score: number; score: number | null; comment: string }
type Student = { enrollment_id: string; student_name: string; final_score: number | null; coverage_percent: number; skills: Record<string, number>; marks: Mark[]; attendance: { attendance_percent: number | null } }
type Book = { id: string; class_id: string; version: number; publish_at: string | null; locked_at: string | null; items: Item[]; students: Student[] }
type Mine = { class_id: string; class_name: string; final_score: number | null; coverage_percent: number; skills: Record<string, number>; marks: Mark[]; attendance: { attendance_percent: number | null } }
const labels: Record<string, [string, string]> = {
  title: ['Sổ điểm lớp', 'Class gradebooks'], mine: ['Kết quả của tôi', 'My results'],
  refresh: ['Làm mới', 'Refresh'], loading: ['Đang tải…', 'Loading…'], empty: ['Chưa có kết quả.', 'No results yet.'],
  class: ['Lớp', 'Class'], create: ['Khởi tạo sổ điểm', 'Create gradebook'], item: ['Đầu điểm', 'Grading item'],
  timing: ['Thời điểm đánh giá', 'Assessment time'], saveTiming: ['Lưu thời điểm', 'Save assessment time'],
  score: ['Điểm', 'Score'], comment: ['Nhận xét học viên sẽ thấy', 'Comment visible to student'],
  save: ['Lưu điểm', 'Save scores'], student: ['Học viên', 'Student'], total: ['Điểm tổng / 100', 'Total / 100'],
  coverage: ['Trọng số đã đánh giá', 'Assessed weight'], skills: ['Theo kỹ năng', 'By skill'],
  attendance: ['Chuyên cần', 'Attendance'], ungraded: ['Chưa đủ điểm', 'Incomplete'],
  publish: ['Công bố từ', 'Publish from'], savePublish: ['Hẹn / công bố', 'Schedule / publish'],
  lock: ['Khóa sổ', 'Lock gradebook'], unlock: ['Mở khóa', 'Unlock gradebook'],
  reason: ['Lý do (bắt buộc sau công bố)', 'Reason (required after publication)'],
  locked: ['Sổ đã khóa', 'Gradebook locked'], waiting: ['Chưa công bố', 'Not published'],
  noItem: ['Chưa có mẫu đầu điểm đã công bố cho khóa học.', 'No published grading scheme for this course.'],
  listening: ['Nghe', 'Listening'], speaking: ['Nói', 'Speaking'],
  reading: ['Đọc', 'Reading'], writing: ['Viết', 'Writing'],
}
const word = (language: Language, key: string) => labels[key]?.[language === 'vi' ? 0 : 1] || key
const locale = (language: Language) => language === 'vi' ? 'vi-VN' : 'en-GB'
const display = (score: number | null) => score === null ? '—' : score.toFixed(2)

function Scores({ language, book, item, done }: { language: Language; book: Book; item: Item; done: () => void }) {
  const students = book.students.filter(s => s.marks.some(m => m.item_id === item.id))
  const published = !!book.publish_at && new Date(book.publish_at) <= new Date()
  const [entries, setEntries] = useState(() => Object.fromEntries(students.map(s => {
    const mark = s.marks.find(m => m.item_id === item.id)!
    return [s.enrollment_id, { score: mark.score === null ? '' : String(mark.score), comment: mark.comment }]
  })))
  const [reason, setReason] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('')
  async function save(event: FormEvent) {
    event.preventDefault(); if (busy) return
    setBusy(true); setError('')
    try {
      await api(`/results/classes/${book.class_id}/items/${item.id}`, 'PUT', {
        request_key: createRequestKey(), version: book.version, reason,
        scores: students.map(s => ({ enrollment_id: s.enrollment_id,
          score: entries[s.enrollment_id].score === '' ? null : entries[s.enrollment_id].score,
          comment: entries[s.enrollment_id].comment })),
      })
      done()
    } catch (e) { setError(requestErrorCode(e)) }
    finally { setBusy(false) }
  }
  return <form className="result-scores" onSubmit={save}><h3>{item.name} / {item.max_score}</h3>
    {students.map(s => <div className="result-score-row" key={s.enrollment_id}><strong>{s.student_name}</strong>
      <label>{word(language, 'score')}<input type="number" min="0" max={item.max_score} step="0.01" value={entries[s.enrollment_id]?.score ?? ''}
        onChange={e => setEntries(old => ({ ...old, [s.enrollment_id]: { ...old[s.enrollment_id], score: e.target.value } }))} /></label>
      <label>{word(language, 'comment')}<input maxLength={1000} value={entries[s.enrollment_id]?.comment ?? ''}
        onChange={e => setEntries(old => ({ ...old, [s.enrollment_id]: { ...old[s.enrollment_id], comment: e.target.value } }))} /></label>
    </div>)}
    <label>{word(language, 'reason')}<input required={published} minLength={3} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
    <button className="primary" disabled={busy}>{word(language, 'save')}</button>{error && <p role="alert">{errorMessage(language, error)}</p>}
  </form>
}

function Gradebook({ language, classId, teacher, manager, revision, refresh }: { language: Language; classId: string; teacher: boolean; manager: boolean; revision: number; refresh: () => void }) {
  const [book, setBook] = useState<Book | null>(null), [missing, setMissing] = useState(false)
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [time, setTime] = useState(''), [publishTime, setPublishTime] = useState(''), [reason, setReason] = useState('')
  useEffect(() => {
    let active = true
    api<Book>(`/results/classes/${classId}`).then(b => { if (active) { setBook(b); setMissing(false); setLoading(false) } })
      .catch(e => { if (active) { setMissing(e instanceof ApiError && e.status === 404); setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED'); setLoading(false) } })
    return () => { active = false }
  }, [classId, revision])
  async function mutate(path: string, body: object) {
    if (busy) return
    setBusy(true); setError('')
    try { await api(path, 'POST', { request_key: createRequestKey(), version: book?.version || 0, ...body }); refresh() }
    catch (e) { setError(requestErrorCode(e)) }
    finally { setBusy(false) }
  }
  if (loading) return <p role="status">{word(language, 'loading')}</p>
  if (missing) return <>{teacher && <button disabled={busy} onClick={() => void mutate(`/results/classes/${classId}/gradebook`, {})}>{word(language, 'create')}</button>}{error && <p role="alert">{word(language, 'noItem')}</p>}</>
  if (!book) return <p role="alert">{errorMessage(language, error)}</p>
  const published = !!book.publish_at && new Date(book.publish_at) <= new Date()
  return <div className="result-book">
    <p>{book.locked_at ? word(language, 'locked') : book.publish_at ? `${word(language, 'publish')}: ${new Date(book.publish_at).toLocaleString(locale(language))}` : word(language, 'waiting')}</p>
    {teacher && !book.locked_at && !published && <form className="result-inline" onSubmit={e => { e.preventDefault(); if (publishTime) void mutate(`/results/classes/${classId}/publication`, { publish_at: new Date(publishTime).toISOString() }) }}>
      <label>{word(language, 'publish')}<input type="datetime-local" required value={publishTime} onChange={e => setPublishTime(e.target.value)} /></label><button disabled={busy}>{word(language, 'savePublish')}</button></form>}
    {manager && <form className="result-inline" onSubmit={e => { e.preventDefault(); void mutate(`/results/classes/${classId}/${book.locked_at ? 'unlock' : 'lock'}`, { reason }) }}>
      <label>{word(language, 'reason')}<input required minLength={3} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label><button disabled={busy || (!book.locked_at && !published)}>{word(language, book.locked_at ? 'unlock' : 'lock')}</button></form>}
    {error && <p role="alert">{errorMessage(language, error)}</p>}
    {book.items.map(item => <article className="card" key={item.id}><h2>{item.name} · {item.weight / 100}%</h2>
      <p>{word(language, 'timing')}: {item.assessed_at ? new Date(item.assessed_at).toLocaleString(locale(language)) : '—'}</p>
      {teacher && !book.locked_at && !published && !item.assessed_at && <form className="result-inline" onSubmit={e => { e.preventDefault(); if (time) { void mutate(`/results/classes/${classId}/items/${item.id}/timing`, { assessed_at: new Date(time).toISOString() }); setTime('') } }}>
        <label>{word(language, 'timing')}<input type="datetime-local" required value={time} onChange={e => setTime(e.target.value)} /></label><button disabled={busy}>{word(language, 'saveTiming')}</button></form>}
      {teacher && !book.locked_at && item.assessed_at && <Scores key={`${item.id}-${book.version}`} language={language} book={book} item={item} done={refresh} />}
    </article>)}
    <h2>{word(language, 'total')}</h2><div className="result-table-scroll"><table><thead><tr><th>{word(language, 'student')}</th><th>{word(language, 'total')}</th><th>{word(language, 'coverage')}</th><th>{word(language, 'attendance')}</th></tr></thead>
      <tbody>{book.students.map(s => <tr key={s.enrollment_id}><td>{s.student_name}</td><td>{display(s.final_score)}</td><td>{s.coverage_percent}%</td><td>{s.attendance.attendance_percent ?? '—'}{s.attendance.attendance_percent === null ? '' : '%'}</td></tr>)}</tbody></table></div>
  </div>
}

export function Results({ language, teacher, manager }: { language: Language; teacher: boolean; manager: boolean }) {
  const [classes, setClasses] = useState<ClassRow[]>([]), [selected, setSelected] = useState('')
  const [revision, setRevision] = useState(0), [loading, setLoading] = useState(true), [error, setError] = useState('')
  const refresh = () => { setLoading(true); setRevision(n => n + 1) }
  useEffect(() => {
    let active = true
    api<{ items: ClassRow[] }>('/results/classes?limit=100').then(p => { if (active) { setClasses(p.items); setLoading(false) } })
      .catch(e => { if (active) { setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED'); setLoading(false) } })
    return () => { active = false }
  }, [revision])
  return <section className="result-page"><header className="result-heading"><h1>{word(language, 'title')}</h1><button onClick={refresh}>{word(language, 'refresh')}</button></header>
    {loading && <p role="status">{word(language, 'loading')}</p>}{error && <p role="alert">{errorMessage(language, error)}</p>}
    {!loading && !classes.length && <p>{word(language, 'empty')}</p>}
    <label>{word(language, 'class')}<select value={selected} onChange={e => setSelected(e.target.value)}><option value="">—</option>{classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
    {selected && <Gradebook key={selected} language={language} classId={selected} teacher={teacher} manager={manager} revision={revision} refresh={refresh} />}
  </section>
}

export function MyResults({ language }: { language: Language }) {
  const [rows, setRows] = useState<Mine[]>([]), [loading, setLoading] = useState(true), [error, setError] = useState(''), [revision, setRevision] = useState(0)
  useEffect(() => {
    let active = true
    api<{ items: Mine[] }>('/results/mine?limit=100').then(p => { if (active) { setRows(p.items); setLoading(false) } })
      .catch(e => { if (active) { setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED'); setLoading(false) } })
    return () => { active = false }
  }, [revision])
  return <section className="result-page"><header className="result-heading"><h1>{word(language, 'mine')}</h1><button onClick={() => { setLoading(true); setRevision(n => n + 1) }}>{word(language, 'refresh')}</button></header>
    {loading && <p role="status">{word(language, 'loading')}</p>}{error && <p role="alert">{errorMessage(language, error)}</p>}
    {!loading && !rows.length && <p>{word(language, 'empty')}</p>}
    {rows.map(row => <article className="card" key={row.class_id}><h2>{row.class_name}</h2>
      <dl><dt>{word(language, 'total')}</dt><dd>{row.final_score === null ? word(language, 'ungraded') : display(row.final_score)}</dd>
        <dt>{word(language, 'coverage')}</dt><dd>{row.coverage_percent}%</dd>
        <dt>{word(language, 'attendance')}</dt><dd>{row.attendance.attendance_percent === null ? '—' : `${row.attendance.attendance_percent}%`}</dd></dl>
      <h3>{word(language, 'skills')}</h3><ul>{Object.entries(row.skills).map(([skill, score]) => <li key={skill}>{word(language, skill)}: {display(score)}</li>)}</ul>
      <ul>{row.marks.map(m => <li key={m.item_id}>{m.name}: {m.score === null ? '—' : display(m.score)} / {m.max_score}{m.comment && ` · ${m.comment}`}</li>)}</ul>
    </article>)}
  </section>
}
