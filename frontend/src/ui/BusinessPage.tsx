import type { ReactNode } from 'react'
import './business.css'

export function BusinessPage({ title, description, actions, children, className = '' }: {
  title: ReactNode
  description?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return <div className={`business-page ${className}`.trim()}>
    <header className="business-page-heading">
      <div><h1>{title}</h1>{description && <p>{description}</p>}</div>
      {actions && <div className="business-page-actions">{actions}</div>}
    </header>
    {children}
  </div>
}

export function BusinessList({ children, label }: { children: ReactNode; label: string }) {
  return <div className="business-list" role="list" aria-label={label}>{children}</div>
}
