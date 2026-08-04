import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="wrap" style={{ paddingTop: 50, maxWidth: 560 }}>
      <div className="kicker">404</div>
      <h1 style={{ fontSize: 'var(--text-xl)', marginTop: 6 }}>That page isn’t here</h1>
      <p style={{ color: 'var(--ink-2)', margin: '10px 0 18px' }}>
        The link may be from an older version of the site.
      </p>
      <Link className="btn-accent" to="/" style={{ textDecoration: 'none' }}>Back to the start</Link>
    </div>
  )
}
