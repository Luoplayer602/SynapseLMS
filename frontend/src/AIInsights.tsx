import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, ApiError } from './api'
import type { Language } from './i18n'
import './ai.css'

type Fact = {id: string; label: string; value: string; href: string}
type Summary = {mode: 'ai' | 'rule'; facts: Fact[]; highlights: Fact[]; next_step: string}
const word = (l: Language, vi: string, en: string) => l === 'vi' ? vi : en

export function AIInsights({language, teacher}: {language: Language; teacher?: boolean}) {
  const [classes, setClasses] = useState<{id: string; name: string}[]>([]), [classId, setClassId] = useState('')
  const [result, setResult] = useState<Summary | null>(null), [error, setError] = useState('')
  useEffect(() => { if (teacher) api<{items: {id: string; name: string}[]}>('/results/classes?limit=100').then(x => {setClasses(x.items); setClassId(x.items[0]?.id || '')}).catch(e => setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED')) }, [teacher])
  useEffect(() => { if (teacher && !classId) return; let active = true; const path = teacher ? `/ai/progress/classes/${classId}` : '/ai/progress/mine'; api<Summary>(`${path}?locale=${language}`).then(x => { if (active) setResult(x) }).catch(e => { if (active) setError(e instanceof ApiError ? e.code : 'REQUEST_FAILED') }); return () => {active = false} }, [teacher, classId, language])
  return <section className="ai-page"><h1>{word(language, 'Tiến độ học tập', 'Learning progress')}</h1><p>{word(language, 'Bản tóm tắt chỉ dựa vào điểm đã công bố, chuyên cần đã chốt và bài luyện. Các mục đều mở được nguồn dữ liệu.', 'The summary uses published results, finalized attendance and completed practice. Each fact links to its source.')}</p>{teacher && <label>{word(language, 'Lớp', 'Class')}<select value={classId} onChange={e => { setClassId(e.target.value); setResult(null); setError('') }}>{classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>}{error && <p role="alert" className="error">{error}</p>}{!result && !error && <p role="status">{word(language, 'Đang tải…', 'Loading…')}</p>}{result && <><p>{result.mode === 'ai' ? word(language, 'AI hỗ trợ chọn điểm nổi bật', 'AI selected highlights') : word(language, 'Tóm tắt theo quy tắc', 'Rule-based summary')}</p>{!result.facts.length && <p>{word(language, 'Chưa có dữ liệu được công bố.', 'No published data yet.')}</p>}<div className="ai-grid">{result.highlights.map(f => <article className="card" key={f.id}><h2>{f.label}</h2><strong>{f.value}</strong><p><Link to={f.href}>{word(language, 'Xem nguồn', 'View source')}</Link></p></article>)}</div><p>{result.next_step === 'practice_more' ? word(language, 'Gợi ý: luyện thêm bài mới.', 'Suggestion: practice another exercise.') : result.next_step === 'review_results' ? word(language, 'Gợi ý: xem lại điểm và chuyên cần.', 'Suggestion: review your results and attendance.') : word(language, 'Tiếp tục nhịp học hiện tại.', 'Keep up your learning rhythm.')}</p></>}</section>
}
