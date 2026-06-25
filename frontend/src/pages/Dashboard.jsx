import React, { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { systemApi, apApi } from '../services/api'
import eventSocket from '../services/websocket'

function AnimatedCount({ value }) {
  const [display, setDisplay] = useState(0)
  const prev = useRef(0)
  useEffect(() => {
    const target = value || 0
    if (prev.current === target) return
    const step = (target - prev.current) / 12
    let cur = prev.current
    const t = setInterval(() => {
      cur += step
      if ((step > 0 && cur >= target) || (step < 0 && cur <= target)) {
        setDisplay(target); clearInterval(t)
      } else {
        setDisplay(Math.round(cur))
      }
    }, 40)
    prev.current = target
    return () => clearInterval(t)
  }, [value])
  return <>{display}</>
}

function Dashboard() {
  const [status, setStatus] = useState(null)
  const [aps, setAps] = useState([])
  const [logs, setLogs] = useState([])
  const [wsOk, setWsOk] = useState(false)
  const logRef = useRef(null)

  useEffect(() => {
    const load = async () => {
      try { setStatus(await systemApi.status()) } catch {}
      try { setAps(await apApi.list()) } catch {}
    }
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    eventSocket.connect()
    const unsub = eventSocket.subscribe((msg) => {
      if (msg.type === 'connected') setWsOk(true)
      if (msg.type === 'disconnected') setWsOk(false)
      if (msg.type === 'event') setLogs(prev => [...prev.slice(-79), msg.data])
    })
    return () => unsub()
  }, [])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  const uptime = status ? formatUptime(status.uptime_seconds) : '--:--'

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Real-time lab overview</p>
        </div>
        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded ${
            wsOk ? 'bg-secondary/10 border border-secondary/30' : 'bg-tertiary/10 border border-tertiary/30'
          }`}>
            <div className={`w-2 h-2 rounded-full ${wsOk ? 'status-dot-active' : 'status-dot-error'}`} />
            <span className={`text-label-md font-mono ${wsOk ? 'text-secondary' : 'text-tertiary'}`}>
              {wsOk ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>
          <div className="text-label-md text-on-surface-variant font-mono">
            UPTIME: <span className="text-primary">{uptime}</span>
          </div>
        </div>
      </div>

      {/* Module warning */}
      {status && !status.hwsim_loaded && (
        <div className="flex items-center gap-3 p-4 mb-6 bg-tertiary/10 border border-tertiary/30 rounded-lg">
          <span className="material-symbols-outlined text-tertiary">warning</span>
          <div>
            <div className="text-tertiary font-medium">mac80211_hwsim not loaded</div>
            <div className="text-on-surface-variant text-sm">
              Run <code className="font-mono bg-surface-container px-1.5 py-0.5 rounded">beaconhub start</code> inside the VM first.
            </div>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="stats-grid mb-6">
        <StatCard
          label="Radios"
          value={<AnimatedCount value={status?.total_radios} />}
          icon="settings_input_antenna"
          color={status?.hwsim_loaded ? 'primary' : 'tertiary'}
          sub={status?.hwsim_loaded ? 'MODULE LOADED' : 'NOT LOADED'}
          to="/adapters"
        />
        <StatCard
          label="Access Points"
          value={<AnimatedCount value={status?.aps_running} />}
          icon="cell_tower"
          color={status?.aps_running > 0 ? 'secondary' : 'muted'}
          sub={status?.aps_running > 0 ? 'BROADCASTING' : 'IDLE'}
          to="/access-points"
        />
        <StatCard
          label="Clients"
          value={<AnimatedCount value={status?.clients_connected} />}
          icon="devices"
          color={status?.clients_connected > 0 ? 'primary' : 'muted'}
          sub="CONNECTED"
          to="/clients"
        />
        <StatCard
          label="Free Adapters"
          value={<AnimatedCount value={status?.adapters_available} />}
          icon="hub"
          color={status?.adapters_available > 0 ? 'secondary' : 'warning'}
          sub="AVAILABLE"
          to="/adapters"
        />
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <QuickAction
          to="/access-points"
          title="Create Access Point"
          desc="Broadcast a new WiFi network with simulated clients"
          icon="add_circle"
          accent="primary"
        />
        <QuickAction
          to="/scenarios"
          title="Run Scenario"
          desc="Launch pre-configured attack scenarios"
          icon="science"
          accent="secondary"
        />
      </div>

      {/* Access Points Overview */}
      {aps.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="font-semibold text-on-surface">Access Points</div>
            <Link to="/access-points" className="text-label-md text-primary hover:underline">View All →</Link>
          </div>
          <div className="grid gap-3">
            {aps.map(ap => {
              const isOpen = ap.security === 'open'
              const isWep = ap.security === 'wep'
              const isEnterprise = ap.security?.includes('enterprise')
              const accent = isOpen ? 'border-l-warning' : isWep ? 'border-l-tertiary' : 'border-l-secondary'
              return (
                <Link key={ap.id} to={`/access-points/${ap.id}`} className="block">
                  <div className={`card p-4 border-l-4 ${accent} hover:bg-primary/5 transition-all`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center">
                          <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 18 }}>
                            {isEnterprise ? 'badge' : isWep ? 'lock_open' : isOpen ? 'wifi' : 'lock'}
                          </span>
                        </div>
                        <div>
                          <div className="font-medium text-on-surface">{ap.ssid}</div>
                          <div className="flex items-center gap-2 text-label-sm text-on-surface-variant">
                            <span className="font-mono">{ap.security.toUpperCase()}</span>
                            {ap.hidden && <span className="px-1.5 py-0.5 rounded bg-tertiary/10 text-tertiary font-mono text-xs">HIDDEN</span>}
                            <span>CH {ap.channel}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-label-sm text-on-surface-variant flex items-center gap-1">
                          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>devices</span>
                          {ap.clients_connected}
                        </div>
                        {ap.packets_sent > 0 && (
                          <div className="text-label-sm text-on-surface-variant flex items-center gap-1">
                            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>swap_horiz</span>
                            {ap.packets_sent + ap.packets_received}
                          </div>
                        )}
                        <div className={`w-2 h-2 rounded-full ${ap.status === 'running' ? 'bg-secondary' : 'bg-tertiary'}`} />
                      </div>
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
      )}

      {/* Event Log - Terminal Style */}
      <div className="terminal scanline">
        <div className="terminal-header">
          <div className="flex items-center gap-2">
            <div className="terminal-dot terminal-dot-red" />
            <div className="terminal-dot terminal-dot-yellow" />
            <div className="terminal-dot terminal-dot-green" />
          </div>
          <span className="text-label-md text-on-surface-variant font-mono ml-4">EVENT LOG</span>
          <div className="ml-auto flex items-center gap-2">
            {wsOk && <div className="w-2 h-2 rounded-full bg-secondary animate-pulse" />}
            <span className="text-label-md text-on-surface-variant font-mono">{logs.length} EVENTS</span>
          </div>
        </div>
        <div
          ref={logRef}
          className="terminal-content"
          style={{ height: 320 }}
        >
          {logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-on-surface-variant">
              <span className="material-symbols-outlined mr-2" style={{ fontSize: 20 }}>hourglass_empty</span>
              Waiting for events...
            </div>
          ) : (
            logs.map((log, i) => (
              <LogLine key={i} log={log} isNew={i === logs.length - 1} />
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, icon, color, sub, to }) {
  const colorMap = {
    primary: 'text-primary',
    secondary: 'text-secondary',
    tertiary: 'text-tertiary',
    warning: 'text-warning',
    muted: 'text-on-surface-variant',
  }
  
  return (
    <Link to={to} className="block">
      <div className="stat-card group cursor-pointer transition-all duration-200 hover:border-primary/50 hover:-translate-y-0.5">
        <div className="flex items-center justify-between mb-4">
          <div className="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center">
            <span className={`material-symbols-outlined ${colorMap[color]}`} style={{ fontSize: 22 }}>
              {icon}
            </span>
          </div>
          <span className="text-label-sm text-on-surface-variant font-mono">{sub}</span>
        </div>
        <div className={`stat-value ${colorMap[color]}`}>
          {value}
        </div>
        <div className="stat-label mt-2">{label}</div>
      </div>
    </Link>
  )
}

function QuickAction({ to, title, desc, icon, accent }) {
  const accentColors = {
    primary: 'border-l-primary bg-primary/5 hover:bg-primary/10',
    secondary: 'border-l-secondary bg-secondary/5 hover:bg-secondary/10',
    tertiary: 'border-l-tertiary bg-tertiary/5 hover:bg-tertiary/10',
  }
  const iconColors = {
    primary: 'text-primary bg-primary/10',
    secondary: 'text-secondary bg-secondary/10',
    tertiary: 'text-tertiary bg-tertiary/10',
  }
  
  return (
    <Link to={to} className="block">
      <div className={`card p-5 flex items-start gap-4 cursor-pointer transition-all duration-200 border-l-2 ${accentColors[accent]}`}>
        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${iconColors[accent]}`}>
          <span className="material-symbols-outlined" style={{ fontSize: 24 }}>{icon}</span>
        </div>
        <div>
          <div className="font-semibold text-on-surface mb-1">{title}</div>
          <div className="text-sm text-on-surface-variant">{desc}</div>
        </div>
        <span className="material-symbols-outlined ml-auto text-on-surface-variant" style={{ fontSize: 20 }}>
          arrow_forward
        </span>
      </div>
    </Link>
  )
}

function LogLine({ log, isNew }) {
  const levelColors = {
    error: 'text-tertiary',
    warning: 'text-warning',
    info: 'text-on-surface-variant',
  }
  const sourceColors = {
    ap: 'text-primary',
    client: 'text-secondary',
    adapter: 'text-tertiary',
    lab: 'text-on-surface-variant',
    system: 'text-on-surface-variant',
  }
  const levelBg = {
    error: 'border-l-tertiary bg-tertiary/5',
    warning: 'border-l-warning bg-warning/5',
    info: 'border-l-transparent',
  }

  return (
    <div className={`terminal-line border-l-2 ${levelBg[log.level] || 'border-l-transparent'} ${isNew ? 'animate-fade-in' : ''}`}>
      <span className="terminal-timestamp">{formatTime(log.timestamp)}</span>
      <span className={`${levelColors[log.level]} uppercase w-12`}>{log.level}</span>
      <span className={`${sourceColors[log.source]} w-16`}>[{log.source}]</span>
      <span className="terminal-message">{log.message}</span>
    </div>
  )
}

function formatUptime(sec) {
  if (!sec) return '--:--'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString('en-US', { hour12: false }) } catch { return '' }
}

export default Dashboard
