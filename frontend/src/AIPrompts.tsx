import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from './api'
import type { Language } from './i18n'
import './ai.css'

type Prompt = { id: string; task: string; locale: string; revision: number; status: string; body: string; active: boolean }
const tasks = ['class_recommendation', 'practice_generation', 'progress_summary']
const text = (l: Language, vi: string, en: string) => l === 'vi' ? vi : en
function lineDiff(before: string, after: string) {
  const a = before.split('\n'), b = after.split('\n'), lines: string[] = []
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if (a[i] === b[i]) lines.push(`  ${a[i]}`)
    else { if (a[i] !== undefined) lines.push(`- ${a[i]}`); if (b[i] !== undefined) lines.push(`+ ${b[i]}`) }
  }
  return lines.join('\n')
}

export function AIPrompts({ language }: {language: Language}) {
  const [rows, setRows] = useState<Prompt[]>([]), [task, setTask] = useState(tasks[0])
  const [locale, setLocale] = useState<'vi' | 'en'>('vi'), [body, setBody] = useState('')
  const [reason, setReason] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false)
  const refresh = () => api<{items: Prompt[]}>('/ai/prompts').then(x => setRows(x.items)).catch(e => setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED'))
  useEffect(() => { void refresh() }, [])
  const history = rows.filter(x => x.task === task && x.locale === locale)
  const activeBody = history.find(x => x.active)?.body
  async function create(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try { await api('/ai/prompts', 'POST', { task, locale, body }); setBody(''); setNotice(text(language, 'Đã tạo bản nháp.', 'Draft created.')); await refresh() }
    catch (e) { setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED') } finally { setBusy(false) }
  }
  async function action(row: Prompt, kind: 'test' | 'publish') {
    setBusy(true); setError(''); setNotice('')
    try {
      await api(`/ai/prompts/${row.id}/${kind}`, 'POST', kind === 'publish' ? { reason } : undefined)
      setNotice(kind === 'test' ? text(language, 'Kiểm tra cấu trúc đạt.', 'Structure check passed.') : text(language, 'Đã chuyển bản đang dùng.', 'Active version changed.'))
      await refresh()
    } catch (e) { setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED') } finally { setBusy(false) }
  }
  return <section className="ai-page"><h1>Prompt Studio</h1><p>{text(language, 'Root chỉnh lời hướng dẫn cho từng tác vụ và ngôn ngữ. Quyền, nguồn dữ liệu và schema đầu ra được server giữ riêng. Chỉ run mới dùng bản vừa publish.', 'Edit task and language instructions. The server owns permissions, data sources and output schemas. Only new runs use a newly published version.')}</p>
    {error && <p role="alert" className="error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="ai-toolbar"><label>{text(language, 'Tác vụ', 'Task')}<select value={task} onChange={e => setTask(e.target.value)}>{tasks.map(x => <option key={x}>{x}</option>)}</select></label><label>{text(language, 'Ngôn ngữ', 'Language')}<select value={locale} onChange={e => setLocale(e.target.value as 'vi' | 'en')}><option value="vi">VI</option><option value="en">EN</option></select></label></div>
    <form className="card ai-form" onSubmit={create}><h2>{text(language, 'Bản nháp mới', 'New draft')}</h2><p>{text(language, 'Biến cho phép: {task}, {locale}. Tránh dữ liệu cá nhân trong bản nháp và dữ liệu thử.', 'Allowed variables: {task}, {locale}. Do not place personal data in drafts or tests.')}</p><textarea value={body} onChange={e => setBody(e.target.value)} minLength={30} maxLength={6000} required /><button className="primary" disabled={busy}>{text(language, 'Tạo phiên bản', 'Create version')}</button></form>
    <label className="ai-reason">{text(language, 'Lý do publish/rollback', 'Publish/rollback reason')}<input value={reason} onChange={e => setReason(e.target.value)} minLength={3} maxLength={500} /></label>
    <div className="ai-grid">{history.map(row => <article className="card" key={row.id}><h2>v{row.revision} · {row.status} {row.active && '●'}</h2><pre className="ai-prompt-body">{row.body}</pre>{activeBody && !row.active && <details><summary>{text(language, 'So với bản đang dùng', 'Compare with active')}</summary><pre className="ai-prompt-body">{lineDiff(activeBody, row.body)}</pre></details>}<div className="ai-actions"><button disabled={busy} onClick={() => void action(row, 'test')}>{text(language, 'Thử cấu trúc', 'Check structure')}</button><button disabled={busy || reason.length < 3 || row.status === 'draft' || row.active} onClick={() => void action(row, 'publish')}>{text(language, row.status === 'retired' ? 'Rollback' : 'Publish', row.status === 'retired' ? 'Rollback' : 'Publish')}</button><button onClick={() => setBody(row.body)}>{text(language, 'Sao chép vào bản nháp', 'Copy to draft')}</button></div></article>)}</div>
  </section>
}
