import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from './api'
import type { Profile } from './api'
import type { Language } from './i18n'
import type { SessionRow } from './SessionOperations'
import { Icon } from './ui/Icon'
import { routeIcon } from './ui/routeIcon'
import './dashboard.css'

type Page<T> = { items: T[]; total: number }
type Request = { id: string; student_name: string; course_name: string; status: string }
type Summary = {
  students?: number
  classes?: number
  requests?: Page<Request>
  invoices?: number
  sessions?: Page<SessionRow>
  checkedAt: number
  failed: boolean
}

const copy = {
  vi: {
    eyebrow: 'KHÔNG GIAN HỌC TẬP', greeting: 'Chào mừng trở lại', intro: 'Chọn công việc bạn muốn tiếp tục hôm nay.',
    center: 'Trung tâm', work: 'Công việc gần đây', workHint: 'Yêu cầu đăng ký mới nhất trong trung tâm', next: 'Buổi học sắp tới', noSession: 'Chưa có buổi học trong 7 ngày tới.', moreSessions: 'Xem toàn bộ lịch học để tìm buổi tiếp theo.', sessionError: 'Không thể tải lịch học.',
    shortcuts: 'Lối tắt', shortcutsHint: 'Đi thẳng đến chức năng bạn cần', viewAll: 'Xem tất cả',
    students: 'Học viên đang hoạt động', classes: 'Lớp đã tạo', requests: 'Yêu cầu đăng ký', invoices: 'Hóa đơn',
    partial: 'Một số số liệu chưa tải được.', workError: 'Không thể tải yêu cầu đăng ký.', retry: 'Thử lại', empty: 'Chưa có yêu cầu đăng ký.',
    personal: 'Không gian của tôi', account: 'Tài khoản và bảo mật', unavailable: 'Không gian trung tâm hiện chưa khả dụng.',
    rootHint: 'Chọn trung tâm hoặc quản lý hệ thống. Dữ liệu trung tâm chỉ xuất hiện khi bắt đầu phiên hỗ trợ.',
    status: { submitted: 'Chờ duyệt', waiting: 'Chờ xếp lớp', placed: 'Đã xếp lớp', rejected: 'Từ chối' },
  },
  en: {
    eyebrow: 'LEARNING SPACE', greeting: 'Welcome back', intro: 'Choose what you would like to continue today.',
    center: 'Center', work: 'Recent work', workHint: 'Latest admission requests in this center', next: 'Upcoming class', noSession: 'No class in the next 7 days.', moreSessions: 'View the full calendar to find the next class.', sessionError: 'Could not load the calendar.',
    shortcuts: 'Quick links', shortcutsHint: 'Go straight to the tools you need', viewAll: 'View all',
    students: 'Active students', classes: 'Classes created', requests: 'Admission requests', invoices: 'Invoices',
    partial: 'Some figures could not be loaded.', workError: 'Could not load admission requests.', retry: 'Retry', empty: 'No admission requests yet.',
    personal: 'My workspace', account: 'Account and security', unavailable: 'This center is currently unavailable.',
    rootHint: 'Choose a center or manage the system. Center data appears only in an active support session.',
    status: { submitted: 'Awaiting review', waiting: 'Awaiting placement', placed: 'Placed', rejected: 'Rejected' },
  },
} as const

const shortcuts = {
  manager: [['/admissions', 'Tuyển sinh', 'Admissions', '◎'], ['/finances', 'Học phí', 'Fees', '◈'], ['/classes', 'Lớp học', 'Classes', '▦'], ['/class-calendar', 'Lịch học', 'Calendar', '◫']],
  staff: [['/admissions', 'Tuyển sinh', 'Admissions', '◎'], ['/finances', 'Học phí', 'Fees', '◈'], ['/classes', 'Lớp học', 'Classes', '▦'], ['/enrollments', 'Bảo lưu & hoàn phí', 'Enrollment & refunds', '↗']],
  teacher: [['/attendance', 'Điểm danh', 'Attendance', '◎'], ['/teaching-sessions', 'Buổi dạy', 'Teaching sessions', '◫'], ['/gradebook', 'Sổ điểm', 'Gradebook', '▤'], ['/materials', 'Học liệu', 'Materials', '▦']],
  student: [['/practice', 'Tiếp tục luyện tập', 'Continue practice', '✦'], ['/my-learning', 'Lịch học của tôi', 'My learning', '◫'], ['/finances', 'Học phí', 'Fees', '◈'], ['/my-materials', 'Học liệu', 'Materials', '▦']],
  root: [['/centers', 'Chọn nơi hỗ trợ', 'Choose workspace', '▦'], ['/ai-settings', 'Thiết lập AI', 'AI settings', '✦'], ['/ai-prompts', 'Prompt Studio', 'Prompt Studio', '◈'], ['/sessions', 'Phiên đăng nhập', 'Sessions', '◎']],
} as const

export function Dashboard({ profile, language, support, children }: {
  profile: Profile; language: Language; support: boolean; children: React.ReactNode
}) {
  const c = copy[language]
  const membership = profile.membership
  const hasCenter = !!membership?.tenant_available || support
  const role = profile.is_root_admin && !support ? 'root' : membership?.role === 'organization_manager' || support ? 'manager' : membership?.role === 'staff' ? 'staff' : membership?.role === 'teacher' ? 'teacher' : 'student'
  const showOperations = hasCenter && (role === 'manager' || role === 'staff')
  const [revision, setRevision] = useState(0)
  const [summary, setSummary] = useState<Summary | null>(null)
  useEffect(() => {
    if (!showOperations) return
    let active = true
    const today = new Date()
    const earlier = new Date(today)
    earlier.setDate(earlier.getDate() - 1)
    const later = new Date(today)
    later.setDate(later.getDate() + 8)
    const day = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
    const paths = ['/students?offset=0&status=active', '/classes?offset=0&status=all', '/admissions/requests?offset=0', '/admissions/invoices?offset=0', `/class-sessions?starts_on=${day(earlier)}&ends_on=${day(later)}&status=scheduled&limit=100&offset=0`] as const
    void Promise.allSettled(paths.map(path => api<Page<Request>>(path))).then(results => {
      if (!active) return
      const value = (index: number) => {
        const result = results[index]
        return result.status === 'fulfilled' && Array.isArray(result.value?.items) && typeof result.value.total === 'number' ? result.value : undefined
      }
      setSummary({ students: value(0)?.total, classes: value(1)?.total, requests: value(2), invoices: value(3)?.total, sessions: value(4) as Page<SessionRow> | undefined, checkedAt: Date.now(),
        failed: results.some((result, index) => result.status === 'rejected' || !value(index)) })
    })
    return () => { active = false }
  }, [showOperations, membership?.id, support, revision])

  const name = profile.display_name?.trim() || profile.email.split('@')[0]
  const date = new Intl.DateTimeFormat(language === 'vi' ? 'vi-VN' : 'en-GB', { dateStyle: 'full' }).format(new Date())
  const items = shortcuts[role]
  const upcoming = summary?.sessions?.items.find(item => {
    const start = new Date(item.starts_at).getTime()
    return start >= summary.checkedAt && start <= summary.checkedAt + 7 * 86400000
  })
  return <div className={`dashboard dashboard-role-${role}`}>
    <header className="dashboard-heading"><div><p className="dashboard-eyebrow">{c.eyebrow} · {date}</p><h1>{c.greeting}, {name} <span aria-hidden="true">✦</span></h1><p>{role === 'root' ? c.rootHint : hasCenter ? c.intro : c.unavailable}</p></div>
      {showOperations && <Link className="dashboard-primary" to="/students">{language === 'vi' ? 'Quản lý học viên' : 'Manage students'} <Icon name="arrow" /></Link>}</header>
    {hasCenter && <p className="dashboard-context">{c.center}: <strong>{support ? (language === 'vi' ? 'Phiên hỗ trợ đang hoạt động' : 'Active support session') : membership?.organization_name}</strong></p>}
    {!showOperations && (hasCenter || role === 'root') && <section className={`dashboard-role-card ${role === 'student' ? 'dashboard-chat-card' : ''}`}>
      <span className="dashboard-role-icon"><Icon name={role === 'student' ? 'chat' : role === 'teacher' ? 'book' : 'shield'} width="28" height="28" /></span>
      <div><p className="dashboard-eyebrow">{role === 'root' ? (language === 'vi' ? 'QUẢN TRỊ HỆ THỐNG' : 'SYSTEM ADMINISTRATION') : role === 'teacher' ? (language === 'vi' ? 'KHÔNG GIAN GIẢNG DẠY' : 'TEACHING SPACE') : (language === 'vi' ? 'BẠN ĐỒNG HÀNH HỌC TẬP' : 'YOUR LEARNING COMPANION')}</p>
        <h2>{role === 'root' ? (language === 'vi' ? 'Quản lý trung tâm, kết nối hệ thống.' : 'Manage centers, connect your system.') : role === 'teacher' ? (language === 'vi' ? 'Sẵn sàng cho buổi dạy tiếp theo?' : 'Ready for your next lesson?') : (language === 'vi' ? 'Hôm nay mình cùng học gì?' : 'What shall we learn today?')}</h2>
        <p>{role === 'root' ? (language === 'vi' ? 'Chọn nơi hỗ trợ hoặc điều chỉnh nguồn AI và prompt.' : 'Choose a support workspace or configure AI sources and prompts.') : role === 'teacher' ? (language === 'vi' ? 'Xem lịch dạy, chuẩn bị học liệu và theo dõi học viên.' : 'Review your schedule, prepare materials and follow student progress.') : (language === 'vi' ? 'Một bước nhỏ giúp bạn giữ nhịp học mỗi ngày.' : 'A small step helps you keep learning every day.')}</p>
        <div className="dashboard-role-actions"><Link to={role === 'root' ? '/centers' : role === 'teacher' ? '/teaching-sessions' : '/ai-hub'}>{role === 'root' ? (language === 'vi' ? 'Chọn trung tâm' : 'Choose a center') : role === 'teacher' ? (language === 'vi' ? 'Xem buổi dạy' : 'View teaching sessions') : (language === 'vi' ? 'Mở trung tâm AI' : 'Open AI hub')} <Icon name="arrow" /></Link>
          {role === 'student' && <Link to="/ai-progress">{language === 'vi' ? 'Nhận xét & bước tiếp theo' : 'Feedback & next step'} <Icon name="arrow" /></Link>}</div>
      </div>
    </section>}
    {showOperations && <><section className="dashboard-metrics" aria-label={language === 'vi' ? 'Số liệu trung tâm' : 'Center figures'}>
      {([[c.students, summary?.students, 'mint', '/students'], [c.classes, summary?.classes, 'blue', '/classes'], [c.requests, summary?.requests?.total, 'violet', '/admissions'], [c.invoices, summary?.invoices, 'orange', '/finances']] as const).map(([label, count, tone, path]) => <Link to={path} className="dashboard-metric" key={label}><span className={`dashboard-metric-icon ${tone}`}><Icon name={routeIcon(path)} /></span><span className="dashboard-metric-label">{label}</span><strong>{count === undefined ? '—' : new Intl.NumberFormat(language === 'vi' ? 'vi-VN' : 'en-GB').format(count)}</strong><span className="dashboard-metric-open"><Icon name="arrow" /></span></Link>)}
    </section>{summary?.failed && <p role="status" className="dashboard-data-warning">{c.partial} <button type="button" onClick={() => { setSummary(null); setRevision(value => value + 1) }}>{c.retry}</button></p>}</>}
    <div className="dashboard-columns">
      {showOperations && <section className="dashboard-panel dashboard-work"><div className="dashboard-panel-heading"><div><span className="dashboard-eyebrow">{language === 'vi' ? 'ƯU TIÊN HÔM NAY' : 'TODAY’S PRIORITIES'}</span><h2>{c.work}</h2><p>{c.workHint}</p></div><Link to="/admissions">{c.viewAll} →</Link></div>
        {!summary ? <p role="status">{language === 'vi' ? 'Đang tải dữ liệu…' : 'Loading data…'}</p> : summary.requests ? summary.requests.items.length ? <div className="dashboard-work-list">{summary.requests.items.slice(0, 4).map((request, index) => <Link to="/admissions" className="dashboard-work-item" key={request.id}><span className={`dashboard-work-badge tone-${index % 4}`} aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><span><strong>{request.student_name}</strong><small>{request.course_name} · {c.status[request.status as keyof typeof c.status] || request.status}</small></span><span aria-hidden="true">→</span></Link>)}</div> : <p>{c.empty}</p> : <p role="alert">{c.workError}</p>}
      </section>}
      <section className="dashboard-panel dashboard-shortcuts">
        <div className="dashboard-panel-heading"><div><span className="dashboard-eyebrow">{c.personal.toUpperCase()}</span><h2>{c.shortcuts}</h2><p>{c.shortcutsHint}</p></div></div><div className="dashboard-shortcut-list">{items.map(([path, vi, en]) => <Link to={path} key={path} className="dashboard-shortcut"><span className="dashboard-shortcut-icon"><Icon name={routeIcon(path)} /></span><span>{language === 'vi' ? vi : en}</span><span aria-hidden="true">→</span></Link>)}</div></section>
    </div>
    {showOperations && <section className="dashboard-next"><div className="dashboard-next-heading"><div><span className="dashboard-eyebrow">{language === 'vi' ? 'NHỊP HOẠT ĐỘNG' : 'CENTER ACTIVITY'}</span><h2>{c.next}</h2></div><Link to="/class-calendar">{language === 'vi' ? 'Xem lịch học' : 'View calendar'} <Icon name="arrow" /></Link></div>
      {summary?.sessions ? upcoming ? <div className="dashboard-next-card"><strong>{upcoming.class_name}</strong><span>{new Date(upcoming.starts_at).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB', { timeZone: upcoming.timezone, dateStyle: 'medium', timeStyle: 'short' })} · {upcoming.room_name || upcoming.branch_name}</span></div> : <p>{summary.sessions.total > summary.sessions.items.length ? c.moreSessions : c.noSession}</p> : <p>{summary ? c.sessionError : language === 'vi' ? 'Đang tải dữ liệu…' : 'Loading data…'}</p>}
    </section>}
    <details className="dashboard-account"><summary>{c.account}</summary><div className="dashboard-account-content">{children}</div></details>
  </div>
}
