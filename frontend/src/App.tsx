import { NavLink, Route, Routes } from 'react-router'

const navigation = [
  ['Tổng quan', '/'],
  ['Học viên', '/students'],
  ['Khóa học', '/courses'],
  ['Lớp học', '/classes'],
  ['Lịch học', '/schedule'],
]

function PlaceholderPage({ title }: { title: string }) {
  return (
    <section className="content">
      <p className="eyebrow">Sprint 1</p>
      <h1>{title}</h1>
      <article className="card readiness">
        <div>
          <h2>Module đang được xây dựng</h2>
          <p>Route đã sẵn sàng để nối API và chính sách quyền theo vai trò.</p>
        </div>
        <span className="status">Đang thực hiện</span>
      </article>
    </section>
  )
}

function DashboardPage() {
  return (
    <section className="content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Thứ bảy, 19 tháng 9</p>
          <h1>Chào mừng đến SynapseLMS</h1>
          <p>Nền tảng quản lý trung tâm ngoại ngữ đang sẵn sàng.</p>
        </div>
        <button className="primary" type="button">Bắt đầu thiết lập</button>
      </div>

      <div className="metric-grid">
        {[
          ['Trạng thái API', 'Hoạt động'],
          ['Chế độ', 'Multi-tenant'],
          ['Ngôn ngữ', 'VI / EN'],
        ].map(([label, value]) => (
          <article className="card" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>

      <article className="card readiness">
        <div>
          <h2>Nền tảng Sprint 1</h2>
          <p>FastAPI, React, PostgreSQL và tenant context đã được khởi tạo.</p>
        </div>
        <span className="status">Đang thực hiện</span>
      </article>
    </section>
  )
}

export default function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark" aria-hidden="true">S</div>
        <div>
          <strong>SynapseLMS</strong>
          <p>Trung tâm demo</p>
        </div>
        <nav aria-label="Điều hướng chính">
          {navigation.map(([label, path]) => (
            <NavLink className={({ isActive }) => (isActive ? 'active' : '')} end={path === '/'} to={path} key={path}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main>
        <header className="topbar">
          <span>Tổng quan</span>
          <div className="topbar-actions">
            <button type="button">VI</button>
            <button type="button" aria-label="Thông báo">●</button>
            <div className="avatar">A</div>
          </div>
        </header>

        <Routes>
          <Route index element={<DashboardPage />} />
          <Route path="students" element={<PlaceholderPage title="Học viên" />} />
          <Route path="courses" element={<PlaceholderPage title="Khóa học" />} />
          <Route path="classes" element={<PlaceholderPage title="Lớp học" />} />
          <Route path="schedule" element={<PlaceholderPage title="Lịch học" />} />
          <Route path="*" element={<PlaceholderPage title="Không tìm thấy trang" />} />
        </Routes>
      </main>
    </div>
  )
}
