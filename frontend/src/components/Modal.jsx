import React from 'react'

export function Modal({ open, onClose, title, children, footer, width = 480 }) {
  if (!open) return null

  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal-box" style={{ maxWidth: width }}>
        <div className="modal-header">
          <span style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)' }}>
            {title}
          </span>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text-muted)', fontSize: 18, lineHeight: 1,
              padding: 4, borderRadius: 6,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => e.target.style.color = 'var(--text-primary)'}
            onMouseLeave={e => e.target.style.color = 'var(--text-muted)'}
          >
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}

export function FormField({ label, children, hint }) {
  return (
    <div style={{ marginBottom: 14 }}>
      {label && <label className="label">{label}</label>}
      {children}
      {hint && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{hint}</div>}
    </div>
  )
}

export function Toast({ message, type = 'info', onClose }) {
  if (!message) return null
  const cls = `alert alert-${type}`
  return (
    <div className={cls} style={{ position: 'relative' }}>
      <span style={{ flex: 1 }}>{message}</span>
      {onClose && (
        <button onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'inherit', opacity: 0.6, fontSize: 14,
        }}>✕</button>
      )}
    </div>
  )
}

export function Toggle({ checked, onChange, disabled }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} disabled={disabled} />
      <span className="toggle-slider" />
    </label>
  )
}

export function SignalBars({ strength = 'strong' }) {
  return (
    <div className={`signal-bars ${strength}`}>
      <div className="bar" />
      <div className="bar" />
      <div className="bar" />
      <div className="bar" />
    </div>
  )
}

export function BeaconDot({ active = true }) {
  return active
    ? <div className="beacon-dot" />
    : <div className="dot dot-gray" />
}

export function SecurityBadge({ security }) {
  const map = {
    'open':           { label: 'OPEN',       cls: 'badge-yellow' },
    'wpa2-psk':       { label: 'WPA2',       cls: 'badge-blue' },
    'wpa2-enterprise':{ label: 'ENTERPRISE', cls: 'badge-blue' },
  }
  const s = map[security] || { label: security, cls: 'badge-gray' }
  return <span className={`badge ${s.cls}`}>{s.label}</span>
}

export function DeviceIcon({ deviceType }) {
  const icons = {
    laptop: '💻', macbook: '🍎', smartphone: '📱',
    tablet: '📲', server: '🖥️', iot: '🔧',
  }
  return <span>{icons[deviceType] || '💻'}</span>
}

export function Spinner() {
  return (
    <div style={{
      width: 16, height: 16, borderRadius: '50%',
      border: '2px solid var(--border)',
      borderTop: '2px solid var(--accent)',
      animation: 'beacon-pulse 0.8s linear infinite',
    }} />
  )
}
