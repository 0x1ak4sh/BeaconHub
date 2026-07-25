import React, { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { clientApi, captureApi } from '../services/api'

function ClientDetail() {
  const { clientId } = useParams()
  const [client, setClient] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [actionLog, setActionLog] = useState([])
  const [credForm, setCredForm] = useState({ username: '', password: '', target_url: 'http://10.0.1.1/login', submit_and_reconnect: true })
  const [credOpen, setCredOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [captureId, setCaptureId] = useState(null)
  const [captureData, setCaptureData] = useState(null)
  const [capturedCreds, setCapturedCreds] = useState([])
  const [capturing, setCapturing] = useState(false)
  const capturePollRef = useRef(null)

  const load = async () => {
    try { setClient(await clientApi.detail(clientId)) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [clientId])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 5000)
  }

  const logAction = (action, result) => {
    setActionLog(prev => [...prev.slice(-19), {
      time: new Date().toLocaleTimeString('en-US', { hour12: false }),
      action,
      result: result?.message || JSON.stringify(result),
      type: result?.status === 'error' ? 'error' : 'ok',
    }])
  }

  const doAction = async (action, extra = {}) => {
    try {
      const r = await clientApi.action(clientId, { action, ...extra })
      showToast(r.message || 'Done')
      logAction(action, r)
      await load()
    } catch (e) {
      showToast(e.message, 'error')
      logAction(action, { message: e.message, status: 'error' })
    }
  }

  const toggleTraffic = async () => {
    setToggling(true)
    try {
      if (client.traffic_running) {
        await clientApi.stopTraffic(clientId)
        showToast('Traffic stopped')
      } else {
        await clientApi.startTraffic(clientId)
        showToast('Traffic started - generating DNS, pings, HTTP...')
      }
      await load()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setToggling(false)
    }
  }

  const openCreds = () => {
    const existing = client?.credentials || {}
    setCredForm({
      username: existing.username || '',
      password: existing.password || '',
      target_url: existing.url || 'http://10.0.1.1/login',
      submit_and_reconnect: true,
    })
    setCredOpen(true)
  }

  const submitCreds = async () => {
    setSubmitting(true)
    try {
      const r = await clientApi.setCredentials(clientId, credForm)
      showToast(r.reconnected ? 'Credentials submitted + reconnected (WPA handshake generated)' : 'Credentials saved')
      logAction('submit_credentials', r)
      setCredOpen(false)
      await load()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const toggleCapture = async () => {
    if (captureId) {
      setCapturing(false)
      if (capturePollRef.current) {
        clearInterval(capturePollRef.current)
        capturePollRef.current = null
      }
      try {
        const r = await captureApi.stop(captureId)
        setCaptureData(r.data)
        setCapturedCreds(r.credentials || [])
        showToast(`Capture stopped — ${r.credentials?.length || 0} credentials found`, r.credentials?.length > 0 ? 'success' : 'info')
      } catch (e) {
        showToast(e.message, 'error')
      }
      setCaptureId(null)
    } else {
      if (!client?.interface) return
      setCapturing(true)
      try {
        const r = await captureApi.start(client.interface)
        setCaptureId(r.capture_id)
        showToast(`Packet capture started on ${client.interface}`)

        // Poll for captured credentials every 3s
        capturePollRef.current = setInterval(async () => {
          try {
            const status = await captureApi.status(r.capture_id)
            setCaptureData(status.data)
            if (status.credentials?.length > 0) {
              setCapturedCreds(prev => {
                const merged = [...status.credentials, ...prev]
                const unique = merged.filter((v, i, a) => a.findIndex(t => t.timestamp === v.timestamp) === i)
                return unique.slice(0, 20)
              })
            }
          } catch {}
        }, 3000)
      } catch (e) {
        showToast(e.message, 'error')
        setCapturing(false)
      }
    }
  }

  // Cleanup capture on unmount
  useEffect(() => {
    return () => {
      if (capturePollRef.current) clearInterval(capturePollRef.current)
    }
  }, [])

  const deviceIcons = { laptop: 'laptop_mac', macbook: 'laptop_mac', smartphone: 'smartphone', tablet: 'tablet_mac', server: 'dns', iot: 'settings_remote' }
  const icon = deviceIcons[client?.device_type] || 'devices'
  const connectedSeconds = client ? Math.floor(Date.now() / 1000 - parseFloat(client.connected_at)) : 0

  if (loading) return (
    <div className="flex items-center justify-center h-48 text-on-surface-variant">
      <span className="material-symbols-outlined animate-spin mr-2">sync</span>
      Loading client...
    </div>
  )

  if (error || !client) return (
    <div className="card">
      <div className="empty-state">
        <span className="material-symbols-outlined text-tertiary" style={{ fontSize: 48 }}>error</span>
        <div className="text-on-surface">{error || 'Client not found'}</div>
        <Link to="/clients" className="btn btn-ghost">
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_back</span>
          Back to Clients
        </Link>
      </div>
    </div>
  )

  return (
    <div className="animate-fade-in">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3 mb-6">
        <Link to="/clients" className="text-on-surface-variant hover:text-on-surface flex items-center gap-1">
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_back</span>
          <span className="text-sm">Clients</span>
        </Link>
        <span className="text-outline-variant">/</span>
        <span className="font-semibold text-on-surface">{client.persona}</span>
        {client.traffic_running && (
          <span className="flex items-center gap-1 text-secondary text-label-md animate-pulse ml-2">
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>play_arrow</span>
            Generating traffic
          </span>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div className={`flex items-center gap-3 p-4 mb-4 rounded-lg ${
          toast.type === 'error' ? 'bg-tertiary/10 border border-tertiary/30' : 'bg-secondary/10 border border-secondary/30'
        }`}>
          <span className={`material-symbols-outlined ${toast.type === 'error' ? 'text-tertiary' : 'text-secondary'}`}>
            {toast.type === 'error' ? 'error' : 'check_circle'}
          </span>
          <span className={toast.type === 'error' ? 'text-tertiary' : 'text-secondary'}>{toast.msg}</span>
          <button onClick={() => setToast(null)} className="ml-auto">
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
          </button>
        </div>
      )}

      {/* Identity Card */}
      <div className="card p-6 mb-4 flex items-start gap-5">
        <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: 32 }}>{icon}</span>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-xl font-bold text-on-surface">{client.persona}</span>
            <span className="badge badge-muted">{client.device_type}</span>
            <div className={`w-2 h-2 rounded-full ${client.is_running ? 'status-dot-active' : 'status-dot-error'}`} />
          </div>
          <div className="grid grid-cols-4 gap-x-6 gap-y-2">
            <Detail label="Hostname" value={client.hostname} />
            <Detail label="Interface" value={client.interface} />
            <Detail label="MAC" value={client.mac_address} />
            <Detail label="IP Address" value={client.ip_address || 'Pending DHCP...'} accent />
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-label-md text-on-surface-variant mb-1">Connected to</div>
          <div className="flex items-center gap-2 justify-end">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 18 }}>cell_tower</span>
            <span className="font-semibold text-primary">{client.ap_ssid || client.connected_to_ap}</span>
          </div>
          <div className="text-label-md text-on-surface-variant mt-1 font-mono">{formatDuration(connectedSeconds)}</div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4 mb-4">
        <StatMini
          label="Traffic Pkts"
          value={client.traffic_count}
          icon="inventory_2"
          color={client.traffic_running ? 'secondary' : 'muted'}
        />
        <StatMini
          label="Traffic Status"
          value={client.traffic_running ? 'Active' : 'Stopped'}
          icon="sensors"
          color={client.traffic_running ? 'secondary' : 'muted'}
        />
        <StatMini
          label="Credentials"
          value={client.credentials ? 'Set' : 'None'}
          icon="key"
          color={client.credentials ? 'warning' : 'muted'}
        />
        <StatMini
          label="Duration"
          value={formatDuration(connectedSeconds)}
          icon="schedule"
          color="primary"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Left: Controls */}
        <div className="flex flex-col gap-4">
          {/* Traffic Control */}
          <div className="card p-5">
            <div className="font-semibold text-on-surface mb-4">Traffic Control</div>
            
            <div className="flex items-center justify-between mb-4 p-3 bg-surface-container rounded-lg">
              <div>
                <div className="font-medium text-on-surface text-sm">Continuous Background Traffic</div>
                <div className="text-label-md text-on-surface-variant">DNS queries, pings, HTTP requests</div>
              </div>
              <button
                onClick={toggleTraffic}
                disabled={toggling}
                className={`w-12 h-6 rounded-full transition-all relative ${
                  client.traffic_running ? 'bg-secondary' : 'bg-surface-container-highest'
                }`}
              >
                <div className={`absolute w-5 h-5 rounded-full bg-on-surface top-0.5 transition-all ${
                  client.traffic_running ? 'left-6' : 'left-0.5'
                }`} />
              </button>
            </div>

            <div className="flex flex-col gap-2">
              <ActionButton 
                icon="language" 
                label="Browse URL" 
                desc="HTTP GET to example.com"
                onClick={() => doAction('browse_url', { url: 'http://example.com' })} 
              />
              <ActionButton 
                icon="dns" 
                label="DNS Lookup" 
                desc="Lookup mail.google.com"
                onClick={() => doAction('dns_lookup', { url: 'mail.google.com' })} 
              />
              <ActionButton 
                icon="captive_portal" 
                label="Captive Portal Check" 
                desc="Simulate device connection check"
                onClick={() => doAction('open_captive')} 
              />
              <ActionButton 
                icon="refresh" 
                label="Reconnect" 
                desc="Disconnect + reconnect (new WPA handshake)"
                onClick={() => doAction('reconnect')} 
                danger 
              />
            </div>
          </div>

          {/* Credentials */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="font-semibold text-on-surface">Credentials</div>
              <button className="btn btn-ghost btn-sm" onClick={openCreds}>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>edit</span>
                {client.credentials ? 'Edit' : 'Set Creds'}
              </button>
            </div>
            {client.credentials ? (
              <div className="p-4 rounded-lg bg-tertiary/5 border border-tertiary/20">
                <div className="text-label-md text-on-surface-variant mb-2">Stored credentials:</div>
                <div className="font-mono text-sm mb-1">
                  <span className="text-on-surface-variant">user: </span>
                  <span className="text-on-surface font-medium">{client.credentials.username}</span>
                </div>
                <div className="font-mono text-sm mb-2">
                  <span className="text-on-surface-variant">pass: </span>
                  <span className="text-on-surface font-medium">{client.credentials.password}</span>
                </div>
                <div className="text-label-md text-on-surface-variant font-mono">
                  → {client.credentials.url}
                </div>
                <button className="btn btn-danger btn-sm mt-3" onClick={() => doAction('submit_credentials')}>
                  <span className="material-symbols-outlined" style={{ fontSize: 14 }}>send</span>
                  Submit Now
                </button>
              </div>
            ) : (
              <div className="text-center py-6 text-on-surface-variant">
                <span className="material-symbols-outlined mb-2" style={{ fontSize: 32, opacity: 0.5 }}>key_off</span>
                <div className="text-sm">No credentials set yet</div>
              </div>
            )}
          </div>
        </div>

        {/* Packet Capture */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="font-semibold text-on-surface">Packet Capture</div>
            <button
              className={`btn btn-sm ${captureId || capturing ? 'btn-danger' : 'btn-primary'}`}
              onClick={toggleCapture}
              disabled={capturing && !captureId}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
                {captureId ? 'stop' : 'play_arrow'}
              </span>
              {captureId ? 'Stop Capture' : capturing ? 'Starting...' : 'Start Capture'}
            </button>
          </div>

          {/* Status */}
          {captureId && (
            <div className="flex items-center gap-2 mb-3 text-label-sm text-secondary font-mono">
              <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
              Capturing on {client?.interface} — listening for HTTP, ARP, EAPOL
            </div>
          )}

          {/* Captured Credentials */}
          {capturedCreds.length > 0 && (
            <div className="mb-3">
              <div className="text-label-sm text-tertiary font-mono uppercase mb-2 flex items-center gap-2">
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>key</span>
                Captured Credentials ({capturedCreds.length})
              </div>
              <div className="flex flex-col gap-2 max-h-48 overflow-y-auto">
                {capturedCreds.map((c, i) => (
                  <div key={i} className="p-3 rounded-lg bg-tertiary/5 border border-tertiary/20">
                    <div className="flex justify-between text-label-sm mb-1">
                      <span className="text-on-surface-variant font-mono">{c.source} → {c.destination}</span>
                      <span className="text-on-surface-variant">{c.timestamp}</span>
                    </div>
                    {c.data && (
                      <div className="font-mono text-xs text-tertiary break-all">{c.data}</div>
                    )}
                    <div className="text-label-sm text-on-surface-variant mt-1">{c.host}{c.uri}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Captured traffic summary */}
          {captureData?.captured_lines?.length > 0 && (
            <div>
              <div className="text-label-sm text-on-surface-variant font-mono uppercase mb-2">
                Raw Packets ({captureData.line_count})
              </div>
              <div className="bg-surface-container rounded-lg p-3 max-h-40 overflow-y-auto font-mono text-label-sm text-on-surface-variant">
                {captureData.captured_lines.slice(-10).map((line, i) => (
                  <div key={i} className="truncate hover:text-on-surface">{line}</div>
                ))}
              </div>
            </div>
          )}

          {!captureId && capturedCreds.length === 0 && (
            <div className="text-center py-6 text-on-surface-variant">
              <span className="material-symbols-outlined mb-2" style={{ fontSize: 32, opacity: 0.5 }}>radar</span>
              <div className="text-sm">Start capture to see live traffic and credentials</div>
            </div>
          )}
        </div>

        {/* Right: Action Log */}
        <div className="card p-5">
          <div className="font-semibold text-on-surface mb-4">Action History</div>
          {actionLog.length === 0 ? (
            <div className="text-center py-12 text-on-surface-variant">
              <span className="material-symbols-outlined mb-2" style={{ fontSize: 32, opacity: 0.5 }}>history</span>
              <div className="text-sm">No actions yet</div>
            </div>
          ) : (
            <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
              {[...actionLog].reverse().map((entry, i) => (
                <div key={i} className={`p-3 rounded-lg border ${
                  entry.type === 'error' 
                    ? 'bg-tertiary/5 border-tertiary/20' 
                    : 'bg-surface-container border-outline-variant'
                }`}>
                  <div className="flex justify-between mb-1">
                    <span className="font-medium text-sm text-on-surface">{entry.action}</span>
                    <span className="text-label-md text-on-surface-variant font-mono">{entry.time}</span>
                  </div>
                  <span className={`text-label-md ${entry.type === 'error' ? 'text-tertiary' : 'text-on-surface-variant'}`}>
                    {entry.result}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Credential Modal */}
      {credOpen && (
        <div className="modal-overlay" onClick={() => setCredOpen(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Set Client Credentials</h3>
              <button onClick={() => setCredOpen(false)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="modal-body">
              <div className="flex items-start gap-3 p-3 mb-4 bg-warning/10 border border-warning/30 rounded-lg">
                <span className="material-symbols-outlined text-warning" style={{ fontSize: 20 }}>warning</span>
                <div className="text-sm text-on-surface-variant">
                  Credentials sent as plaintext HTTP POST - visible in packet capture. False values OK.
                </div>
              </div>
              <div className="mb-4">
                <label className="label">Username</label>
                <input className="input" type="text" placeholder="e.g. admin@corp.com"
                  value={credForm.username}
                  onChange={e => setCredForm({ ...credForm, username: e.target.value })} />
              </div>
              <div className="mb-4">
                <label className="label">Password</label>
                <input className="input" type="text" placeholder="e.g. hunter2"
                  value={credForm.password}
                  onChange={e => setCredForm({ ...credForm, password: e.target.value })} />
              </div>
              <div className="mb-4">
                <label className="label">Target URL</label>
                <input className="input" type="text" placeholder="http://10.0.1.1/login"
                  value={credForm.target_url}
                  onChange={e => setCredForm({ ...credForm, target_url: e.target.value })} />
              </div>
              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={credForm.submit_and_reconnect}
                  onChange={e => setCredForm({ ...credForm, submit_and_reconnect: e.target.checked })}
                  className="w-4 h-4" style={{ accentColor: 'var(--primary)' }} />
                <span className="text-sm text-on-surface-variant">Submit + reconnect (generates new WPA handshake)</span>
              </label>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setCredOpen(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={submitCreds} disabled={submitting}>
                {submitting ? (
                  <>
                    <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>sync</span>
                    Submitting...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>key</span>
                    Save & Submit
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Detail({ label, value, accent }) {
  return (
    <div>
      <div className="text-label-sm text-on-surface-variant uppercase mb-1 font-mono">{label}</div>
      <div className={`text-sm font-mono ${accent ? 'text-primary font-medium' : 'text-on-surface'}`}>
        {value || '—'}
      </div>
    </div>
  )
}

function StatMini({ label, value, icon, color }) {
  const colorMap = {
    primary: 'text-primary bg-primary/10',
    secondary: 'text-secondary bg-secondary/10',
    warning: 'text-warning bg-warning/10',
    muted: 'text-on-surface-variant bg-surface-container',
  }
  
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${colorMap[color]}`}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{icon}</span>
        </div>
        <span className="text-label-md text-on-surface-variant font-mono uppercase">{label}</span>
      </div>
      <div className={`text-xl font-bold ${color === 'muted' ? 'text-on-surface-variant' : `text-${color}`}`}>
        {value}
      </div>
    </div>
  )
}

function ActionButton({ icon, label, desc, onClick, danger }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 p-3 rounded-lg w-full text-left transition-all border ${
        danger 
          ? 'bg-tertiary/5 border-tertiary/20 hover:bg-tertiary/10 hover:border-tertiary/40' 
          : 'bg-surface-container border-outline-variant hover:bg-surface-container-high hover:border-on-surface-variant'
      }`}
    >
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${
        danger ? 'bg-tertiary/10' : 'bg-primary/10'
      }`}>
        <span className={`material-symbols-outlined ${danger ? 'text-tertiary' : 'text-primary'}`} style={{ fontSize: 20 }}>
          {icon}
        </span>
      </div>
      <div>
        <div className="font-medium text-sm text-on-surface">{label}</div>
        <div className="text-label-md text-on-surface-variant">{desc}</div>
      </div>
    </button>
  )
}

function formatDuration(sec) {
  if (!sec || sec < 0) return '—'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export default ClientDetail
