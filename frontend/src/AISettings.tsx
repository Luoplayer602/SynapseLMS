import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from './api'
import type { Language } from './i18n'
import './ai.css'

type Task = 'class_recommendation' | 'practice_generation' | 'progress_summary'
type Provider = { id: string; code: string; name: string; kind: string; base_url: string; model_id: string; has_key: boolean; enabled: boolean; allowed_tasks: Task[]; timeout_seconds: number; max_output_tokens: number; max_daily_calls: number; version: number }
type Route = { task: Task; provider_id: string; priority: number }
type TenantTask = { task: Task; enabled: boolean; max_daily_calls: number; timezone: string }
type Usage = { task: Task; status: string; count: number; output_tokens: number }
const tasks: Task[] = ['class_recommendation', 'practice_generation', 'progress_summary']
const names: Record<Task, [string, string]> = { class_recommendation: ['Gợi ý lớp', 'Class suggestions'], practice_generation: ['Sinh bài luyện', 'Practice generation'], progress_summary: ['Tóm tắt tiến độ', 'Progress summary'] }
const kinds = ['openai', 'gemini', 'claude', 'openai_compatible', 'ollama', 'lm_studio']
const msg = (language: Language, vi: string, en: string) => language === 'vi' ? vi : en
const fail = (error: unknown) => error instanceof ApiError ? error.code : 'REQUEST_FAILED'

export function AISettings({ language, root }: { language: Language; root: boolean }) {
  const [providers, setProviders] = useState<Provider[]>([])
  const [routes, setRoutes] = useState<Route[]>([])
  const [tenantTasks, setTenantTasks] = useState<TenantTask[]>([])
  const [usage, setUsage] = useState<Usage[]>([])
  const [selected, setSelected] = useState<string>('')
  const [name, setName] = useState(''), [code, setCode] = useState(''), [kind, setKind] = useState('openai')
  const [baseUrl, setBaseUrl] = useState(''), [model, setModel] = useState(''), [key, setKey] = useState('')
  const [enabled, setEnabled] = useState(false), [allowed, setAllowed] = useState<Task[]>(tasks)
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('')
  const refresh = () => {
    if (root) Promise.all([api<{items: Provider[]}>('/ai/providers'), api<{items: Route[]}>('/ai/routes')])
      .then(([p, r]) => { setProviders(p.items); setRoutes(r.items) }).catch(e => setError(fail(e)))
    else Promise.all([api<{items: TenantTask[]}>('/ai/tenant-tasks'), api<{items: Usage[]}>('/ai/usage')])
      .then(([settings, totals]) => { setTenantTasks(settings.items); setUsage(totals.items) }).catch(e => setError(fail(e)))
  }
  useEffect(refresh, [root])
  const pick = (row?: Provider) => {
    setSelected(row?.id || ''); setName(row?.name || ''); setCode(row?.code || ''); setKind(row?.kind || 'openai')
    setBaseUrl(row?.base_url || ''); setModel(row?.model_id || ''); setKey(''); setEnabled(row?.enabled || false)
    setAllowed(row?.allowed_tasks || tasks); setError(''); setNotice('')
  }
  async function saveProvider(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    try {
      await api(`/ai/providers${selected ? `/${selected}` : ''}`, selected ? 'PUT' : 'POST',
        { name, code, kind, base_url: baseUrl, model_id: model, api_key: key || null,
          enabled, allowed_tasks: allowed, timeout_seconds: 20, max_output_tokens: 1024, max_daily_calls: 100,
          version: selected ? providers.find(p => p.id === selected)?.version : null })
      setKey(''); setNotice(msg(language, 'Đã lưu nguồn.', 'Provider saved.')); refresh()
    } catch (e) { setError(fail(e)) } finally { setBusy(false) }
  }
  async function testProvider(id: string) {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await api<{ok: boolean}>(`/ai/providers/${id}/test`, 'POST')
      setNotice(result.ok ? msg(language, 'Kết nối và JSON đạt.', 'Connection and JSON passed.') : msg(language, 'Nguồn trả JSON nhưng chưa đúng yêu cầu.', 'JSON did not match the probe.'))
    } catch (e) { setError(fail(e)) } finally { setBusy(false) }
  }
  async function saveRoute(task: Task, text: string) {
    const ids = text.split(',').map(x => x.trim()).filter(Boolean)
    setBusy(true); setError('')
    try { await api('/ai/routes', 'PUT', { task, provider_ids: ids }); refresh(); setNotice(msg(language, 'Đã lưu thứ tự nguồn.', 'Routing saved.')) }
    catch (e) { setError(fail(e)) } finally { setBusy(false) }
  }
  async function saveTenantTask(task: Task, enabled: boolean, max_daily_calls: number, timezone: string) {
    setBusy(true); setError('')
    try { await api('/ai/tenant-tasks', 'PUT', { task, enabled, max_daily_calls, timezone }); refresh(); setNotice(msg(language, 'Đã cập nhật tác vụ.', 'Task updated.')) }
    catch (e) { setError(fail(e)) } finally { setBusy(false) }
  }
  return <section className="ai-page"><h1>{msg(language, 'Thiết lập AI', 'AI settings')}</h1>
    <p>{msg(language, 'Nguồn API và local chạy tại server. Khóa chỉ nhập mới hoặc thay thế; không đọc lại được.', 'API and local providers run on the server. Keys can only be entered or replaced.')}</p>
    {error && <p role="alert" className="error">{error}</p>}{notice && <p role="status">{notice}</p>}
    {root ? <>
      <div className="ai-grid">{providers.map(p => <article key={p.id} className="card"><h2>{p.name}</h2><p>{p.kind} · {p.model_id} · {p.enabled ? 'on' : 'off'} · {p.has_key ? 'key set' : 'no key'}</p><button onClick={() => pick(p)}>{msg(language, 'Sửa', 'Edit')}</button> <button disabled={busy} onClick={() => void testProvider(p.id)}>{msg(language, 'Thử kết nối', 'Test connection')}</button></article>)}</div>
      <form className="card ai-form" onSubmit={saveProvider}><h2>{selected ? msg(language, 'Sửa nguồn', 'Edit provider') : msg(language, 'Thêm nguồn', 'Add provider')}</h2>
        {selected && <button type="button" onClick={() => pick()}>{msg(language, 'Tạo mới', 'New')}</button>}
        <label>{msg(language, 'Mã', 'Code')}<input value={code} onChange={e => setCode(e.target.value)} disabled={!!selected} required /></label>
        <label>{msg(language, 'Tên', 'Name')}<input value={name} onChange={e => setName(e.target.value)} required /></label>
        <label>{msg(language, 'Loại nguồn', 'Provider kind')}<select value={kind} onChange={e => setKind(e.target.value)} disabled={!!selected}>{kinds.map(k => <option key={k}>{k}</option>)}</select></label>
        <label>Model ID<input value={model} onChange={e => setModel(e.target.value)} required /></label>
        {!['openai', 'gemini', 'claude'].includes(kind) && <label>Base URL<input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder={kind === 'ollama' ? 'http://192.168.1.10:11434' : 'https://provider.example/v1'} required /></label>}
        <label>API key / token<input type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} placeholder={selected ? msg(language, 'Để trống để giữ khóa cũ', 'Leave blank to keep existing key') : ''} /></label>
        <fieldset><legend>{msg(language, 'Tác vụ cho phép', 'Allowed tasks')}</legend>{tasks.map(t => <label className="check" key={t}><input type="checkbox" checked={allowed.includes(t)} onChange={e => setAllowed(e.target.checked ? [...allowed, t] : allowed.filter(x => x !== t))} />{names[t][language === 'vi' ? 0 : 1]}</label>)}</fieldset>
        <label className="check"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />{msg(language, 'Bật nguồn', 'Enable provider')}</label><button className="primary" disabled={busy}>{msg(language, 'Lưu nguồn', 'Save provider')}</button>
      </form>
      <div className="ai-grid">{tasks.map(task => <RouteEditor key={`${task}:${routes.length}`} language={language} task={task} providers={providers} routes={routes.filter(r => r.task === task)} busy={busy} onSave={saveRoute} />)}</div>
    </> : <><div className="ai-grid">{tasks.map(task => <TenantEditor key={`${task}:${tenantTasks.length}`} language={language} task={task} setting={tenantTasks.find(x => x.task === task)} busy={busy} onSave={saveTenantTask} />)}</div><article className="card"><h2>{msg(language, 'Sử dụng của trung tâm', 'Center usage')}</h2>{usage.map(row => <p key={`${row.task}:${row.status}`}>{names[row.task][language === 'vi' ? 0 : 1]} · {row.status}: {row.count} {msg(language, 'lượt', 'calls')} · {row.output_tokens} output tokens</p>)}</article></>}
  </section>
}

function RouteEditor({ language, task, providers, routes, busy, onSave }: {language: Language; task: Task; providers: Provider[]; routes: Route[]; busy: boolean; onSave: (task: Task, value: string) => Promise<void>}) {
  const [value, setValue] = useState(routes.map(x => x.provider_id).join(','))
  return <form className="card" onSubmit={e => { e.preventDefault(); void onSave(task, value) }}><h2>{names[task][language === 'vi' ? 0 : 1]}</h2><p>{msg(language, 'Nhập ID nguồn theo thứ tự, cách nhau bằng dấu phẩy.', 'Enter provider IDs in priority order, comma-separated.')}</p><select onChange={e => setValue(e.target.value)} value=""><option value="">{msg(language, 'Thêm nguồn vào thứ tự', 'Add provider')}</option>{providers.filter(p => p.allowed_tasks.includes(task)).map(p => <option key={p.id} value={value ? `${value},${p.id}` : p.id}>{p.name}</option>)}</select><textarea aria-label="Provider IDs" value={value} onChange={e => setValue(e.target.value)} /><button disabled={busy}>{msg(language, 'Lưu định tuyến', 'Save routing')}</button></form>
}

function TenantEditor({ language, task, setting, busy, onSave }: {language: Language; task: Task; setting?: TenantTask; busy: boolean; onSave: (task: Task, enabled: boolean, max: number, timezone: string) => Promise<void>}) {
  const [enabled, setEnabled] = useState(setting?.enabled || false), [max, setMax] = useState(setting?.max_daily_calls || 30), [timezone, setTimezone] = useState(setting?.timezone || 'Asia/Ho_Chi_Minh')
  return <form className="card" onSubmit={e => { e.preventDefault(); void onSave(task, enabled, max, timezone) }}><h2>{names[task][language === 'vi' ? 0 : 1]}</h2><label className="check"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />{msg(language, 'Bật cho trung tâm', 'Enable for center')}</label><label>{msg(language, 'Lượt mỗi ngày', 'Daily calls')}<input type="number" min="1" max="1000" value={max} onChange={e => setMax(Number(e.target.value))} /></label>{task === 'practice_generation' && <label>Timezone<input value={timezone} onChange={e => setTimezone(e.target.value)} /></label>}<button disabled={busy}>{msg(language, 'Lưu', 'Save')}</button></form>
}
