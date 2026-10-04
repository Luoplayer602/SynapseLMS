import { Link } from 'react-router'
import type { Language } from './i18n'
import { Icon } from './ui/Icon'
import './ai-hub.css'

export function AIHub({ language }: { language: Language }) {
  const vi = language === 'vi'
  const tasks = [
    { to: '/practice', icon: 'spark' as const, title: vi ? 'Làm bài luyện' : 'Practice', detail: vi ? 'Luyện với bài hiện có và theo dõi chuỗi ngày hoàn thành.' : 'Work on available exercises and track completed days.' },
    { to: '/ai-progress', icon: 'chat' as const, title: vi ? 'Nhận xét & bước tiếp' : 'Feedback & next step', detail: vi ? 'Xem nhận xét có nguồn từ kết quả, chuyên cần và bài luyện.' : 'See sourced feedback from results, attendance and practice.' },
    { to: '/course-catalog', icon: 'book' as const, title: vi ? 'Khám phá khóa học' : 'Explore courses', detail: vi ? 'Xem các khóa đã công bố trước khi chọn hướng học tiếp.' : 'Browse published courses before choosing what to study next.' },
  ]
  return <section className="ai-hub" aria-labelledby="ai-hub-title">
    <header className="ai-hub-heading"><span className="ai-hub-eyebrow">SYNAPSE AI</span><h1 id="ai-hub-title">{vi ? 'Góc học tập của bạn' : 'Your learning space'}</h1><p>{vi ? 'Chọn việc bạn muốn làm. Mỗi gợi ý mở một tác vụ đang có trong SynapseLMS.' : 'Choose what to do next. Each suggestion opens an existing SynapseLMS task.'}</p></header>
    <Link className="ai-hub-bubble" to="/practice" aria-label={vi ? 'Mở bài luyện AI' : 'Open AI practice'}>
      <span className="ai-hub-bubble-icon"><Icon name="chat" width={42} height={42} /></span>
      <strong>{vi ? 'Hôm nay mình học gì?' : 'What shall we learn today?'}</strong>
      <span>{vi ? 'Bắt đầu bài luyện' : 'Start practice'} <Icon name="arrow" width={18} height={18} /></span>
    </Link>
    <nav className="ai-hub-tasks" aria-label={vi ? 'Tác vụ học tập' : 'Learning tasks'}>{tasks.map(task => <Link className="ai-hub-task" key={task.to} to={task.to}>
      <span className="ai-hub-task-icon"><Icon name={task.icon} /></span><span><strong>{task.title}</strong><small>{task.detail}</small></span><Icon name="arrow" />
    </Link>)}</nav>
  </section>
}
