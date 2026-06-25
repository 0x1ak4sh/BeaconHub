import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { systemApi } from '../services/api'
import eventSocket from '../services/websocket'

const nav = [
  { path: '/',              label: 'Dashboard',      icon: 'dashboard' },
  { path: '/access-points', label: 'Access Points',  icon: 'cell_tower' },
  { path: '/clients',       label: 'Clients',        icon: 'devices' },
  { path: '/adapters',      label: 'Adapters',       icon: 'settings_input_antenna' },
  { path: '/attacks',       label: 'Attacks',        icon: 'security' },
  { path: '/scenarios',     label: 'Scenarios',      icon: 'science' },
  { path: '/logs',          label: 'Event Log',      icon: 'terminal' },
]

function Layout({ children }) {
  const location = useLocation()
  const [resetting, setResetting] = useState(false)
  const [wsStatus, setWsStatus] = useState('connecting')
  const [events, setEvents] = useState([])

  React.useEffect(() => {
    eventSocket.connect()
    const unsub = eventSocket.subscribe((msg) => {
      if (msg.type === 'connected') setWsStatus('connected')
      else if (msg.type === 'disconnected') setWsStatus('disconnected')
      else if (msg.type === 'event' && msg.data) {
        const sources = ['cmd', 'ap', 'client', 'adapter', 'attack', 'radius', 'scenario', 'traffic', 'error', 'lab']
        if (sources.includes(msg.data.source) || msg.data.level !== 'info') {
          setEvents(prev => [msg.data, ...prev].slice(0, 6))
        }
      }
    })
    return () => unsub()
  }, [])

  const handleReset = async () => {
    if (!window.confirm('Stop all APs, clients, and adapters?')) return
    setResetting(true)
    try { await systemApi.reset() } catch (e) { console.error(e) }
    finally { setResetting(false) }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div style={{ 
                width: 36, height: 36, borderRadius: 8, 
                background: 'var(--bg-elevated)', 
                display: 'flex', alignItems: 'center', justifyContent: 'center' 
              }}>
                <span className="material-symbols-outlined" style={{ fontSize: 22, color: 'var(--primary)' }}>
                  wifi
                </span>
              </div>
              <div 
                style={{
                  position: 'absolute', bottom: -2, right: -2,
                  width: 10, height: 10, borderRadius: '50%',
                  border: '2px solid var(--bg-surface)',
                  background: wsStatus === 'connected' ? 'var(--secondary)' : 'var(--tertiary)',
                  boxShadow: wsStatus === 'connected' ? '0 0 6px var(--secondary)' : '0 0 6px var(--tertiary)'
                }}
              />
            </div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>
                <span style={{ color: 'var(--primary)' }}>Beacon</span>
                <span style={{ color: 'var(--text-primary)' }}>Hub</span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
                WiFi Security Lab
              </div>
            </div>
          </div>
        </div>

        {/* Nav Links */}
        <nav className="sidebar-nav">
          <div style={{ 
            fontSize: 9, color: 'var(--text-muted)', 
            textTransform: 'uppercase', letterSpacing: '0.1em',
            padding: '8px 12px', fontFamily: 'JetBrains Mono, monospace'
          }}>
            Navigation
          </div>
          {nav.map((item) => {
            const active = location.pathname === item.path ||
              (item.path !== '/' && location.pathname.startsWith(item.path))
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-item ${active ? 'active' : ''}`}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* Footer */}
        <div style={{ padding: '12px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <div className="flex items-center gap-2 mb-3" style={{ padding: '0 4px' }}>
            <div className={`status-dot ${wsStatus === 'connected' ? 'status-dot-active' : 'status-dot-error'}`} />
            <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
              {wsStatus === 'connected' ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          
          <button
            onClick={handleReset}
            disabled={resetting}
            className="btn btn-ghost w-full"
            style={{ justifyContent: 'center', fontSize: 11 }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
              {resetting ? 'sync' : 'restart_alt'}
            </span>
            {resetting ? 'Resetting...' : 'Reset Lab'}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {children}
      </main>
      <LiveOps events={events} />
    </div>
  )
}

function LiveOps({ events }) {
  if (!events.length) return null

  return (
    <div className="live-ops">
      <div className="live-ops-header">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>terminal</span>
          <span>Backend Steps</span>
        </div>
        <span className="status-dot status-dot-active" />
      </div>
      <div className="live-ops-list">
        {events.map((event, idx) => (
          <div key={`${event.timestamp}-${idx}`} className={`live-ops-row live-ops-${event.level}`}>
            <span className="live-ops-source">{event.source}</span>
            <span className="live-ops-message">{event.message}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default Layout
