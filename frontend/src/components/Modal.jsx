import React from 'react'

export function Modal({ open, onClose, title, children, footer, width = 480 }) {
  if (!open) return null

  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal-box" style={{ maxWidth: width }}>
        <div className="modal-header">
          <span className="modal-title">{title}</span>
          <button onClick={onClose} className="btn btn-ghost btn-icon">
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
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
    <div className="mb-4">
      {label && <label className="label">{label}</label>}
      {children}
      {hint && <div className="text-label-sm text-on-surface-variant mt-1">{hint}</div>}
    </div>
  )
}

export function Spinner() {
  return (
    <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>
      sync
    </span>
  )
}
