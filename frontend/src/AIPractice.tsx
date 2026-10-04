import { useEffect, useState } from 'react'
import { api } from './api'
import { createRequestKey, requestErrorCode } from './requestKey'
import type { Language } from './i18n'
import { errorMessage } from './i18n'
import './ai.css'

type Question = {id: string; course_id: string; locale: string; stem: string; options: string[]; status: string; correct_index?: number; explanation?: string}
type Attempt = {id: string; correct: boolean; correct_index: number; explanation: string}
type Rewards = {current_streak: number; best_streak: number; unlocked: string[]; selected: string}
const word = (l: Language, vi: string, en: string) => l === 'vi' ? vi : en
const errorCode = (e: unknown) => requestErrorCode(e)
const displayError = (language: Language, code: string) => code === 'REQUEST_KEY_UNAVAILABLE' ? errorMessage(language, code) : code

export function AIPractice({language}: {language: Language}) {
  const [questions, setQuestions] = useState<Question[]>([]), [rewards, setRewards] = useState<Rewards | null>(null)
  const [answer, setAnswer] = useState<Record<string, number>>({}), [results, setResults] = useState<Record<string, Attempt>>({})
  const [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const refresh = () => Promise.all([api<{items: Question[]}>('/practice/mine'), api<Rewards>('/practice/rewards/mine')])
    .then(([q, r]) => { setQuestions(q.items); setRewards(r); document.documentElement.dataset.theme = r.selected })
    .catch(e => setError(errorCode(e)))
  useEffect(() => { void refresh() }, [])
  async function submit(question: Question) {
    if (answer[question.id] === undefined) return
    setBusy(true); setError('')
    try { const result = await api<Attempt>(`/practice/questions/${question.id}/submit`, 'POST', { request_key: createRequestKey(), answer_index: answer[question.id] }); setResults(prev => ({...prev, [question.id]: result})); const r = await api<Rewards>('/practice/rewards/mine'); setRewards(r) }
    catch (e) { setError(errorCode(e)) } finally { setBusy(false) }
  }
  return <section className="ai-page"><h1>{word(language, 'Bài luyện AI', 'AI practice')}</h1><p>{word(language, 'Hoàn thành một bài hợp lệ mỗi ngày để tích chuỗi, không cần đạt điểm tối thiểu. Bài sai vẫn giúp bạn luyện tập.', 'Complete one valid exercise each day to grow your streak. No minimum score is required.')}</p>
    {error && <p role="alert" className="error">{displayError(language, error)}</p>}
    {rewards && <article className="card ai-streak"><strong>🔥 {rewards.current_streak}</strong><span>{word(language, 'ngày liên tiếp', 'day streak')} · {word(language, 'kỷ lục', 'best')} {rewards.best_streak}</span></article>}
    {!questions.length && <p>{word(language, 'Chưa có bài mới được duyệt cho lớp đang học. Hãy quay lại sau.', 'No new approved exercises for your current classes yet.')}</p>}
    <div className="ai-grid">{questions.map(q => <article className="card" key={q.id}><h2>{q.stem}</h2><fieldset disabled={!!results[q.id] || busy}><legend>{word(language, 'Chọn một đáp án', 'Choose one answer')}</legend>{q.options.map((option, index) => <label className="check" key={index}><input type="radio" name={`answer-${q.id}`} checked={answer[q.id] === index} onChange={() => setAnswer(prev => ({...prev, [q.id]: index}))} />{option}</label>)}</fieldset>{results[q.id] ? <p role="status">{results[q.id].correct ? word(language, 'Chính xác!', 'Correct!') : word(language, 'Chưa đúng.', 'Not quite.')} {results[q.id].explanation} {word(language, 'Đáp án:', 'Answer:')} {q.options[results[q.id].correct_index]}</p> : <button className="primary" disabled={busy || answer[q.id] === undefined} onClick={() => void submit(q)}>{word(language, 'Nộp bài', 'Submit')}</button>}</article>)}</div>
    <ThemeRewards language={language} rewards={rewards} onChanged={refresh} />
  </section>
}

export function ThemeRewards({language, rewards, onChanged}: {language: Language; rewards: Rewards | null; onChanged: () => void}) {
  const [error, setError] = useState('')
  const themes = [{id: 'synapse-soft', name: 'Synapse Soft', days: 0}, {id: 'neo-pop', name: 'Neo Pop', days: 3}, {id: 'clay-garden', name: 'Clay Garden', days: 7}, {id: 'liquid-glass', name: 'Liquid Glass', days: 14}]
  return <section className="ai-rewards"><h2>{word(language, 'Theme thưởng', 'Theme rewards')}</h2>{error && <p role="alert" className="error">{displayError(language, error)}</p>}<div className="ai-grid">{themes.map(theme => <article className={`card ai-theme ai-theme-${theme.id}`} key={theme.id}><h3>{theme.name}</h3><p>{theme.days ? word(language, `Mở sau ${theme.days} ngày`, `Unlock after ${theme.days} days`) : word(language, 'Mặc định', 'Default')}</p><button disabled={!rewards?.unlocked.includes(theme.id) || rewards?.selected === theme.id} onClick={async () => { try { await api('/practice/rewards/theme', 'PUT', {theme: theme.id}); document.documentElement.dataset.theme = theme.id; onChanged() } catch (e) { setError(errorCode(e)) } }}>{rewards?.selected === theme.id ? word(language, 'Đang dùng', 'Selected') : rewards?.unlocked.includes(theme.id) ? word(language, 'Chọn', 'Select') : word(language, 'Chưa mở', 'Locked')}</button></article>)}</div></section>
}

export function PracticeReview({language, manager}: {language: Language; manager: boolean}) {
  const [courses, setCourses] = useState<{id: string; name: string}[]>([]), [course, setCourse] = useState('')
  const [questions, setQuestions] = useState<Question[]>([]), [stem, setStem] = useState(''), [options, setOptions] = useState(['', '', '', ''])
  const [correct, setCorrect] = useState(0), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => { const path = manager ? '/courses?limit=100' : '/results/classes?limit=100'; api<{items: {id: string; name: string; course_id?: string}[]}>(path).then(x => { const items = manager ? x.items : x.items.map(c => ({id: c.course_id || '', name: c.name})); setCourses(items.filter(c => c.id)); setCourse(items[0]?.id || '') }).catch(e => setError(errorCode(e))) }, [manager])
  const refresh = () => { if (course) api<{items: Question[]}>(`/practice/questions?course_id=${course}`).then(x => setQuestions(x.items)).catch(e => setError(errorCode(e))) }
  useEffect(refresh, [course])
  async function mutate(path: string, body?: unknown) { setBusy(true); setError(''); try { await api(path, 'POST', body); refresh() } catch (e) { setError(errorCode(e)) } finally { setBusy(false) } }
  return <section className="ai-page"><h1>{word(language, 'Duyệt bài luyện', 'Review practice')}</h1>{error && <p role="alert" className="error">{displayError(language, error)}</p>}<label>{word(language, 'Khóa học', 'Course')}<select value={course} onChange={e => setCourse(e.target.value)}>{courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
    {manager && course && <><button disabled={busy} onClick={() => void mutate('/practice/questions/generate', {course_id: course, locale: language})}>{word(language, 'Sinh bản nháp bằng AI', 'Generate AI draft')}</button><form className="card ai-form" onSubmit={e => { e.preventDefault(); void mutate('/practice/questions', {course_id: course, locale: language, stem, options: options.filter(Boolean), correct_index: correct}) }}><h2>{word(language, 'Bài dự phòng đã kiểm duyệt', 'Curated fallback question')}</h2><label>{word(language, 'Câu hỏi', 'Question')}<textarea value={stem} onChange={e => setStem(e.target.value)} minLength={10} required /></label>{options.map((value, i) => <label key={i}>{word(language, `Đáp án ${i + 1}`, `Option ${i + 1}`)}<input value={value} onChange={e => setOptions(prev => prev.map((x, index) => index === i ? e.target.value : x))} /></label>)}<label>{word(language, 'Chỉ số đáp án đúng (0–3)', 'Correct option index (0–3)')}<input type="number" min="0" max="3" value={correct} onChange={e => setCorrect(Number(e.target.value))} /></label><button disabled={busy}>{word(language, 'Lưu bản nháp', 'Save draft')}</button></form></>}
    <div className="ai-grid">{questions.map(q => <article className="card" key={q.id}><h2>{q.stem}</h2><ol>{q.options.map((x, i) => <li key={i}>{x} {i === q.correct_index ? '✓' : ''}</li>)}</ol><p>{q.status} · {q.explanation}</p><button disabled={busy || q.status === 'published'} onClick={() => void mutate(`/practice/questions/${q.id}/publish`)}>{word(language, 'Duyệt phát hành', 'Publish')}</button> <button disabled={busy || q.status === 'hidden'} onClick={() => void mutate(`/practice/questions/${q.id}/hide`)}>{word(language, 'Ẩn', 'Hide')}</button></article>)}</div>
  </section>
}
