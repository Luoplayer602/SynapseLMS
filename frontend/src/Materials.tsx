import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, apiContent } from './api'
import { createRequestKey, requestErrorCode } from './requestKey'
import type { Language } from './i18n'
import { errorMessage } from './i18n'
import './materials.css'

type Version = { id: string; revision: number; kind: string; file_status: string; filename: string; source_url: string | null; published_at: string | null }
type Material = { id: string; title: string; description: string; source: string; status: string; audience: string; scope: string; class_id: string | null; latest?: Version }
type Assignment = { id: string; class_id: string; publish_at: string; withdrawn_at: string | null; material: Material; version: Version }
type Curriculum = { id: string; title: string; status: string }
type CurriculumDetail = { id: string; versions: { id: string; revision: number; status: string; units: { id: string; title: string; position: number; materials: { material_version_id: string }[] }[] }[] }
type Named = { id: string; name: string }
const l = (language: Language, vi: string, en: string) => language === 'vi' ? vi : en
const message = (language: Language, error: unknown) => errorMessage(language, requestErrorCode(error))

async function openContent(version: Version) {
  const content = await apiContent(`/materials/versions/${version.id}/content`)
  if (content.url) { window.open(content.url, '_blank', 'noopener,noreferrer'); return }
  if (content.blob) {
    const url = URL.createObjectURL(content.blob)
    window.open(url, '_blank', 'noopener,noreferrer')
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  }
}

export function Materials({ language, role }: { language: Language; role: 'manager' | 'staff' | 'teacher' }) {
  const [items, setItems] = useState<Material[]>([])
  const [classes, setClasses] = useState<Named[]>([])
  const [courses, setCourses] = useState<Named[]>([])
  const [reviews, setReviews] = useState<{ id: string; material_version_id: string; status: string }[]>([])
  const [curricula, setCurricula] = useState<Curriculum[]>([])
  const [selectedCurriculum, setSelectedCurriculum] = useState<CurriculumDetail | null>(null)
  const [selectedClass, setSelectedClass] = useState('')
  const [creationClass, setCreationClass] = useState(''), [assignClass, setAssignClass] = useState('')
  const [sessions, setSessions] = useState<{ id: string; starts_at: string }[]>([])
  const [creationSessions, setCreationSessions] = useState<{ id: string; starts_at: string }[]>([])
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [error, setError] = useState(''), [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [revision, setRevision] = useState(0)
  const [file, setFile] = useState<File | null>(null), [target, setTarget] = useState('')
  const staff = role !== 'teacher'
  const refresh = () => { setError(''); setRevision(n => n + 1) }
  useEffect(() => {
    let active = true
    Promise.all([
      api<{ items: Material[] }>('/materials?limit=100'),
      api<{ items: Named[] }>('/materials/classes'),
      staff ? api<{ items: Named[] }>('/courses?limit=100') : Promise.resolve({ items: [] as Named[] }),
      staff ? api<{ items: Curriculum[] }>('/materials/curricula') : Promise.resolve({ items: [] as Curriculum[] }),
      staff ? api<{ items: typeof reviews }>('/materials/reviews') : Promise.resolve({ items: [] as typeof reviews }),
    ]).then(([a, b, c, d, e]) => { if (active) { setItems(a.items); setClasses(b.items); setCourses(c.items); setCurricula(d.items); setReviews(e.items); setLoading(false) } })
      .catch(e => { if (active) { setError(message(language, e)); setLoading(false) } })
    return () => { active = false }
  }, [revision, staff, language])
  useEffect(() => {
    if (!selectedClass) return
    let active = true
    api<{ items: Assignment[] }>(`/materials/assignments?class_id=${selectedClass}`)
      .then(x => { if (active) setAssignments(x.items) })
      .catch(e => { if (active) setError(message(language, e)) })
    return () => { active = false }
  }, [selectedClass, revision, language])
  useEffect(() => {
    if (!assignClass) return
    let active = true
    api<{ items: { id: string; starts_at: string }[] }>(`/materials/classes/${assignClass}/sessions`)
      .then(x => { if (active) setSessions(x.items) })
      .catch(e => { if (active) setError(message(language, e)) })
    return () => { active = false }
  }, [assignClass, language])
  useEffect(() => {
    if (!creationClass) return
    let active = true
    api<{ items: { id: string; starts_at: string }[] }>(`/materials/classes/${creationClass}/sessions`)
      .then(x => { if (active) setCreationSessions(x.items) })
      .catch(e => { if (active) setError(message(language, e)) })
    return () => { active = false }
  }, [creationClass, language])
  async function mutate(path: string, method = 'POST', body?: object | FormData | (() => object | FormData)) {
    if (busy) return null
    setBusy(true); setError(''); setNotice('')
    try { const value = await api<unknown>(path, method, typeof body === 'function' ? body() : body); setNotice(l(language, 'Đã lưu.', 'Saved.')); refresh(); return value }
    catch (e) { setError(message(language, e)); return null }
    finally { setBusy(false) }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const value = await mutate('/materials', 'POST', {
      title: data.get('title'), description: data.get('description'), source: data.get('source'),
      audience: data.get('audience'), ...(data.get('class_id') ? { class_id: data.get('class_id') } : {}),
      ...(data.get('session_id') ? { session_id: data.get('session_id') } : {}),
    })
    if (value) form.reset()
  }
  async function addVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!target) return
    const data = new FormData(event.currentTarget)
    if (file) {
      const saved = await mutate(`/materials/${target}/versions/file`, 'POST', () => { const body = new FormData(); body.append('upload', file); body.append('request_key', createRequestKey()); return body })
      if (saved) setFile(null)
    } else if (data.get('url')) await mutate(`/materials/${target}/versions/link`, 'POST', () => ({ url: data.get('url'), request_key: createRequestKey() }))
  }
  async function assign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    await mutate('/materials/assignments', 'POST', () => ({
      class_id: data.get('class_id'), material_version_id: data.get('version_id'),
      ...(data.get('session_id') ? { session_id: data.get('session_id') } : {}),
      publish_at: data.get('publish_at') ? new Date(String(data.get('publish_at'))).toISOString() : null,
      request_key: createRequestKey(),
    }))
  }
  async function createCurriculum(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    await mutate('/materials/curricula', 'POST', { title: data.get('title'), author: data.get('author'), isbn: data.get('isbn') })
  }
  async function loadCurriculum(id: string) {
    try { setSelectedCurriculum(await api<CurriculumDetail>(`/materials/curricula/${id}`)) }
    catch (e) { setError(message(language, e)) }
  }
  const ready = items.filter(x => x.latest?.published_at && x.latest.file_status === 'ready' && x.status === 'published')
  return <div className="materials-page">
    <h1>{l(language, 'Thư viện học liệu', 'Learning materials')}</h1>
    <p>{l(language, 'Tài liệu chỉ hiển thị cho học viên sau khi được công bố vào lớp.', 'Learners see materials only after class publication.')}</p>
    <button onClick={refresh} disabled={busy}>{l(language, 'Làm mới', 'Refresh')}</button>
    {loading && <p role="status">{l(language, 'Đang tải…', 'Loading…')}</p>}
    {error && <p role="alert" className="error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="materials-grid">
      <section className="card"><h2>{l(language, 'Tạo tài liệu', 'New material')}</h2>
        <form onSubmit={create} className="material-form">
          <label>{l(language, 'Tên tài liệu', 'Title')}<input name="title" minLength={2} maxLength={200} required /></label>
          <label>{l(language, 'Mô tả', 'Description')}<input name="description" /></label>
          <label>{l(language, 'Tác giả / nguồn', 'Author / source')}<input name="source" /></label>
          <label>{l(language, 'Đối tượng', 'Audience')}<select name="audience"><option value="students">{l(language, 'Học viên', 'Learners')}</option><option value="teachers">{l(language, 'Giáo viên', 'Teachers')}</option></select></label>
          <label>{l(language, 'Phạm vi', 'Scope')}<select name="class_id" value={creationClass} onChange={e => { setCreationClass(e.target.value); setCreationSessions([]) }}><option value="">{l(language, 'Thư viện chung', 'Shared library')}</option>{classes.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          {role === 'teacher' && creationClass && <label>{l(language, 'Buổi dạy thay (nếu có)', 'Substitute session (if any)')}<select name="session_id"><option value="">{l(language, 'Cả lớp', 'Whole class')}</option>{creationSessions.map(x => <option key={x.id} value={x.id}>{new Date(x.starts_at).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB')}</option>)}</select></label>}
          <button disabled={busy}>{l(language, 'Tạo bản nháp', 'Create draft')}</button>
        </form>
      </section>
      <section className="card"><h2>{l(language, 'Thêm phiên bản', 'Add version')}</h2>
        <form onSubmit={addVersion} className="material-form">
          <label>{l(language, 'Tài liệu', 'Material')}<select value={target} onChange={e => setTarget(e.target.value)} required><option value="">—</option>{items.filter(x => x.status !== 'withdrawn').map(x => <option key={x.id} value={x.id}>{x.title}</option>)}</select></label>
          <label>{l(language, 'File PDF / ảnh / MP3', 'PDF / image / MP3 file')}<input type="file" accept=".pdf,.png,.jpg,.jpeg,.mp3" onChange={e => setFile(e.target.files?.[0] || null)} /></label>
          <label>{l(language, 'Hoặc liên kết HTTPS', 'Or HTTPS link')}<input name="url" type="url" placeholder="https://" /></label>
          <button disabled={busy || !target}>{l(language, 'Thêm', 'Add')}</button>
        </form>
      </section>
    </div>
    <section className="card"><h2>{l(language, 'Danh sách tài liệu', 'Materials')}</h2>
      {!loading && items.length === 0 && <p>{l(language, 'Chưa có tài liệu.', 'No materials yet.')}</p>}
      <div className="material-list">{items.map(x => <article key={x.id} className="material-row">
        <div><strong>{x.title}</strong><p>{x.description}</p><small>{x.status} · {x.scope} · {x.audience}{x.latest && ` · v${x.latest.revision} · ${x.latest.file_status}`}</small></div>
        <div className="material-actions">
          {x.latest?.file_status === 'pending_check' && <button disabled={busy} onClick={() => void mutate(`/materials/versions/${x.latest!.id}/retry-scan`)}>{l(language, 'Quét lại', 'Rescan')}</button>}
          {x.latest?.file_status === 'ready' && !x.latest.published_at && <button disabled={busy} onClick={() => void mutate(`/materials/versions/${x.latest!.id}/publish`)}>{l(language, 'Công bố phiên bản', 'Publish version')}</button>}
          {role === 'teacher' && x.latest?.file_status === 'ready' && <button disabled={busy} onClick={() => void mutate(`/materials/versions/${x.latest!.id}/submit`)}>{l(language, 'Đề xuất dùng chung', 'Submit to library')}</button>}
          {x.latest?.published_at && <button onClick={() => void openContent(x.latest!).catch(e => setError(message(language, e)))}>{l(language, 'Xem', 'Open')}</button>}
          {x.status === 'published' && <button disabled={busy} onClick={() => void mutate(`/materials/${x.id}/archive`)}>{l(language, 'Lưu trữ', 'Archive')}</button>}
          {x.status !== 'withdrawn' && <button disabled={busy} onClick={() => { const reason = window.prompt(l(language, 'Lý do thu hồi', 'Withdrawal reason')); if (reason) void mutate(`/materials/${x.id}/withdraw`, 'POST', { reason }) }}>{l(language, 'Thu hồi', 'Withdraw')}</button>}
        </div>
      </article>)}</div>
    </section>
    {staff && reviews.some(x => x.status === 'pending') && <section className="card"><h2>{l(language, 'Đề xuất cần duyệt', 'Pending reviews')}</h2>{reviews.filter(x => x.status === 'pending').map(x => <article key={x.id} className="material-row"><span>{x.material_version_id}</span><div className="material-actions"><button onClick={() => void mutate(`/materials/reviews/${x.id}/decision?approve=true`, 'POST', { reason: '' })}>{l(language, 'Duyệt', 'Approve')}</button><button onClick={() => { const reason = window.prompt(l(language, 'Lý do từ chối', 'Rejection reason')); if (reason) void mutate(`/materials/reviews/${x.id}/decision?approve=false`, 'POST', { reason }) }}>{l(language, 'Từ chối', 'Reject')}</button></div></article>)}</section>}
    {staff && <section className="card"><h2>{l(language, 'Giáo trình', 'Curricula')}</h2>
      <form onSubmit={createCurriculum} className="material-inline"><input name="title" placeholder={l(language, 'Tên giáo trình', 'Curriculum title')} minLength={2} required /><input name="author" placeholder={l(language, 'Tác giả', 'Author')} /><input name="isbn" placeholder="ISBN" /><button disabled={busy}>{l(language, 'Tạo giáo trình', 'Create curriculum')}</button></form>
      <label>{l(language, 'Chọn giáo trình', 'Select curriculum')}<select onChange={e => void loadCurriculum(e.target.value)} defaultValue=""><option value="">—</option>{curricula.map(x => <option key={x.id} value={x.id}>{x.title}</option>)}</select></label>
      {selectedCurriculum && <CurriculumEditor language={language} detail={selectedCurriculum} courses={courses} classes={classes} ready={ready} mutate={mutate} reload={() => void loadCurriculum(selectedCurriculum.id)} />}
    </section>}
    <section className="card"><h2>{l(language, 'Phát tài liệu cho lớp', 'Assign to class')}</h2>
      <form onSubmit={assign} className="material-form">
        <label>{l(language, 'Lớp', 'Class')}<select name="class_id" required value={assignClass} onChange={e => { setAssignClass(e.target.value); setSessions([]) }}><option value="">—</option>{classes.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
        {assignClass && <label>{l(language, 'Buổi học (tùy chọn)', 'Session (optional)')}<select name="session_id"><option value="">{l(language, 'Cả lớp', 'Whole class')}</option>{sessions.map(x => <option key={x.id} value={x.id}>{new Date(x.starts_at).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB')}</option>)}</select></label>}
        <label>{l(language, 'Tài liệu đã công bố', 'Published material')}<select name="version_id" required><option value="">—</option>{ready.map(x => <option key={x.latest!.id} value={x.latest!.id}>{x.title} · v{x.latest!.revision}</option>)}</select></label>
        <label>{l(language, 'Giờ công bố (để trống = ngay)', 'Publish time (blank = now)')}<input name="publish_at" type="datetime-local" /></label>
        <button disabled={busy}>{l(language, 'Phát tài liệu', 'Assign material')}</button>
      </form>
      <label>{l(language, 'Xem tài liệu lớp', 'View class assignments')}<select value={selectedClass} onChange={e => { setSelectedClass(e.target.value); setAssignments([]) }}><option value="">—</option>{classes.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      {assignments.map(x => <article key={x.id} className="material-row"><span>{x.material.title} · {new Date(x.publish_at).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB')}{x.withdrawn_at && ` · ${l(language, 'Đã thu hồi', 'Withdrawn')}`}</span>{!x.withdrawn_at && <button onClick={() => { const reason = window.prompt(l(language, 'Lý do thu hồi', 'Withdrawal reason')); if (reason) void mutate(`/materials/assignments/${x.id}/withdraw`, 'POST', { reason }) }}>{l(language, 'Thu hồi', 'Withdraw')}</button>}</article>)}
    </section>
  </div>
}

function CurriculumEditor({ language, detail, courses, classes, ready, mutate, reload }: { language: Language; detail: CurriculumDetail; courses: Named[]; classes: Named[]; ready: Material[]; mutate: (path: string, method?: string, body?: object | FormData) => Promise<unknown>; reload: () => void }) {
  const version = detail.versions[0]
  if (!version) return null
  async function submit(event: FormEvent<HTMLFormElement>, path: string, values: (data: FormData) => object) {
    event.preventDefault(); await mutate(path, 'POST', values(new FormData(event.currentTarget))); reload()
  }
  return <div className="curriculum-editor"><h3>v{version.revision} · {version.status}</h3>
    {version.status === 'draft' && <><form className="material-inline" onSubmit={e => void submit(e, `/materials/curriculum-versions/${version.id}/units`, d => ({ title: d.get('title'), position: Number(d.get('position')) }))}><input name="title" placeholder={l(language, 'Chương / bài', 'Chapter / lesson')} required /><input name="position" type="number" min="1" defaultValue={version.units.length + 1} required /><button>{l(language, 'Thêm bài', 'Add unit')}</button></form>
      {version.units.map(u => <form key={u.id} className="material-inline" onSubmit={e => void submit(e, `/materials/curriculum-units/${u.id}/materials`, d => ({ material_version_id: d.get('material_version_id'), page_hint: d.get('page_hint') }))}><span>{u.position}. {u.title}</span><select name="material_version_id" aria-label={l(language, 'Tài liệu', 'Material')} required><option value="">{l(language, 'Chọn tài liệu đã công bố', 'Select published material')}</option>{ready.map(x => <option key={x.latest!.id} value={x.latest!.id}>{x.title} · v{x.latest!.revision}</option>)}</select><input name="page_hint" placeholder={l(language, 'Trang', 'Pages')} /><button>{l(language, 'Gắn tài liệu', 'Attach')}</button></form>)}
      <button onClick={() => void mutate(`/materials/curriculum-versions/${version.id}/publish`).then(reload)}>{l(language, 'Phát hành giáo trình', 'Publish curriculum')}</button></>}
    {version.status === 'published' && <><button onClick={() => void mutate(`/materials/curricula/${detail.id}/clone`).then(reload)}>{l(language, 'Tạo phiên bản mới', 'New revision')}</button>
      <form className="material-inline" onSubmit={e => void submit(e, `/materials/courses/${String(new FormData(e.currentTarget).get('course_id'))}/curricula`, () => ({ curriculum_version_id: version.id, primary: true }))}><select name="course_id" required><option value="">{l(language, 'Khóa học', 'Course')}</option>{courses.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select><button>{l(language, 'Gắn khóa', 'Bind course')}</button></form>
      <form className="material-inline" onSubmit={e => void submit(e, `/materials/classes/${String(new FormData(e.currentTarget).get('class_id'))}/curricula`, () => ({ curriculum_version_id: version.id, primary: true, reason: 'Gắn giáo trình' }))}><select name="class_id" required><option value="">{l(language, 'Lớp', 'Class')}</option>{classes.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select><button>{l(language, 'Gắn lớp', 'Bind class')}</button></form></>}
  </div>
}

export function MyMaterials({ language }: { language: Language }) {
  const [items, setItems] = useState<Assignment[]>([]), [error, setError] = useState(''), [loading, setLoading] = useState(true)
  const [revision, setRevision] = useState(0)
  useEffect(() => { let active = true; api<{ items: Assignment[] }>('/materials/mine').then(x => { if (active) { setItems(x.items); setLoading(false) } }).catch(e => { if (active) { setError(message(language, e)); setLoading(false) } }); return () => { active = false } }, [revision, language])
  return <div className="materials-page"><h1>{l(language, 'Tài liệu của tôi', 'My materials')}</h1><button onClick={() => { setLoading(true); setRevision(x => x + 1) }}>{l(language, 'Làm mới', 'Refresh')}</button>{loading && <p role="status">{l(language, 'Đang tải…', 'Loading…')}</p>}{error && <p role="alert" className="error">{error}</p>}{!loading && items.length === 0 && <p>{l(language, 'Chưa có tài liệu được công bố.', 'No published materials yet.')}</p>}<div className="material-list">{items.map(x => <article className="card material-row" key={x.id}><div><h2>{x.material.title}</h2><p>{x.material.description}</p><small>{x.material.source} · v{x.version.revision}</small></div><button onClick={() => void openContent(x.version).catch(e => setError(message(language, e)))}>{x.version.kind === 'audio' ? l(language, 'Nghe', 'Listen') : l(language, 'Xem / tải', 'Open / download')}</button></article>)}</div></div>
}
