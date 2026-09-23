import { useEffect, useState } from 'react'

export function useEmailLink() {
  const [link, setLink] = useState(() => ({ token: new URLSearchParams(window.location.hash.slice(1)).get('token') || '', version: 0 }))
  useEffect(() => {
    const scrub = () => window.history.replaceState(window.history.state, '', window.location.pathname)
    const changed = () => {
      const token = new URLSearchParams(window.location.hash.slice(1)).get('token') || ''
      setLink(previous => ({ token, version: previous.version + 1 }))
      scrub()
    }
    scrub()
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  return link
}
