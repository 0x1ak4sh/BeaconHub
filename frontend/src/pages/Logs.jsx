import React, { useState, useEffect, useRef } from 'react'
import { systemApi } from '../services/api'
import eventSocket from '../services/websocket'

const LEVEL_COLORS = {
  error: 'text-tertiary',
  warning: 'text-warning',
  info: 'text-on-surface-variant',
}

const SOURCE_COLORS = {
  ap: 'text-primary',
  client: 'text-secondary',
  adapter: 'text-tertiary',
  lab: 'text-on-surface-variant',
  system: 'text-on-surface-variant',
}

function Logs() {
  const [logs, setLogs] = useState([])
  const [filter, setFilter] = useState('all')
  const [autoScroll, setAutoScroll] = useState(true)
  const [wsConnected, setWsConnected] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    const fetch = async () => {
      try { const d = await systemApi.logs(300); setLogs(d.logs || []) } catch {}
    }
    fetch()
  }, [])

  useEffect(() => {
    eventSocket.connect()
    const unsub = eventSocket.subscribe((msg) => {
      if (msg.type === 'connected') setWsConnected(true)
      if (msg.type === 'disconnected') setWsConnected(false)
      if (msg.type === 'event') setLogs(prev => [...prev.slice(-499), msg.data])
    })
    return () => unsub()
  }, [])

  useEffect(() => {
    if (autoScroll && endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const sources = [...new Set(logs.map(l => l.source))].filter(Boolean)

  const filtered = filter === 'all' ? logs
    : logs.filter(l => l.source === filter || l.level === filter)

  const exportLogs = () => {
    const text = filtered.map(l =>
      `[${l.timestamp}] [${l.level}] [${l.source}] ${l.message}`
    ).join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `beaconhub-logs-${Date.now()}.txt`
    a.click()
  }

  const errorCount = logs.filter(l => l.level === 'error').length
  const warningCount = logs.filter(l => l.level === 'warning').length

  return (
    <div className="animate-fade-in flex flex-col" style={{ height: 'calc(100vh - 100px)' }}>
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Event Log</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-label-md text-on-surface-variant font-mono">{filtered.length} events</span>
            {errorCount > 0 && (
              <span className="text-label-md text-tertiary font-mono">{errorCount} errors</span>
            )}
            {warningCount > 0 && (
              <span className="text-label-md text-warning font-mono">{warningCount} warnings</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input 
              type="checkbox" 
              checked={autoScroll}
              onChange={e => setAutoScroll(e.target.checked)}
              className="w-4 h-4"
              style={{ accentColor: 'var(--primary)' }} 
            />
            <span className="text-label-md text-on-surface-variant">Auto-scroll</span>
          </label>
          <button className="btn btn-ghost btn-sm" onClick={exportLogs}>
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>download</span>
            Export
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => setLogs([])}>
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>delete</span>
            Clear
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <FilterChip label="All" active={filter === 'all'} onClick={() => setFilter('all')} />
        <FilterChip label="Error" active={filter === 'error'} onClick={() => setFilter('error')} color="tertiary" />
        <FilterChip label="Warning" active={filter === 'warning'} onClick={() => setFilter('warning')} color="warning" />
        
        <div className="w-px h-4 bg-outline-variant mx-1" />
        
        {sources.map(s => (
          <FilterChip 
            key={s} 
            label={s} 
            active={filter === s} 
            onClick={() => setFilter(s)}
            color={s === 'ap' ? 'primary' : s === 'client' ? 'secondary' : s === 'adapter' ? 'tertiary' : 'muted'} 
          />
        ))}
      </div>

      {/* Terminal */}
      <div className="terminal scanline flex-1 flex flex-col overflow-hidden">
        {/* Terminal Header */}
        <div className="terminal-header">
          <div className="flex items-center gap-2">
            <div className="terminal-dot terminal-dot-red" />
            <div className="terminal-dot terminal-dot-yellow" />
            <div className="terminal-dot terminal-dot-green" />
          </div>
          <span className="text-label-md text-on-surface-variant font-mono ml-4">BEACONHUB SYSTEM LOG</span>
          <div className="ml-auto flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-secondary animate-pulse' : 'bg-tertiary'}`} />
            <span className="text-label-md text-on-surface-variant font-mono">
              {wsConnected ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>
        </div>

        {/* Log Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {filtered.length === 0 ? (
            <div className="flex items-center justify-center h-full text-on-surface-variant">
              <span className="material-symbols-outlined mr-2" style={{ fontSize: 24 }}>terminal</span>
              Waiting for events...
            </div>
          ) : (
            filtered.map((log, i) => (
              <LogLine key={i} log={log} isNew={i === filtered.length - 1} />
            ))
          )}
          <div ref={endRef} />
        </div>
      </div>
    </div>
  )
}

function LogLine({ log, isNew }) {
  const levelBg = {
    error: 'border-l-tertiary bg-tertiary/5',
    warning: 'border-l-warning bg-warning/5',
    info: 'border-l-transparent',
  }

  return (
    <div className={`flex items-start gap-3 py-1 px-2 border-l-2 ${levelBg[log.level] || 'border-l-transparent'} ${isNew ? 'animate-fade-in' : ''}`}>
      <span className="text-label-md text-on-surface-variant font-mono flex-shrink-0 w-20">
        {formatTime(log.timestamp)}
      </span>
      <span className={`text-label-md font-mono flex-shrink-0 w-14 uppercase font-medium ${LEVEL_COLORS[log.level]}`}>
        {log.level}
      </span>
      <span className={`text-label-md font-mono flex-shrink-0 w-16 ${SOURCE_COLORS[log.source]}`}>
        [{log.source}]
      </span>
      <span className="text-sm text-on-surface-variant">
        {log.message}
      </span>
    </div>
  )
}

function FilterChip({ label, active, onClick, color }) {
  const colorClasses = {
    primary: active ? 'bg-primary/20 border-primary text-primary' : '',
    secondary: active ? 'bg-secondary/20 border-secondary text-secondary' : '',
    tertiary: active ? 'bg-tertiary/20 border-tertiary text-tertiary' : '',
    warning: active ? 'bg-warning/20 border-warning text-warning' : '',
    muted: active ? 'bg-surface-container-high border-on-surface-variant text-on-surface' : '',
  }

  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded text-label-md font-mono uppercase transition-all border ${
        active 
          ? colorClasses[color] || 'bg-primary/20 border-primary text-primary'
          : 'bg-transparent border-outline-variant text-on-surface-variant hover:border-on-surface-variant'
      }`}
    >
      {label}
    </button>
  )
}

function formatTime(iso) {
  try { return new Date(iso).toLocaleTimeString('en-US', { hour12: false }) } catch { return '' }
}

export default Logs
