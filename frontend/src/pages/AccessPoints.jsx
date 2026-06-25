import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apApi, clientApi } from '../services/api'
import eventSocket from '../services/websocket'

const CHANNELS = [1,2,3,4,5,6,7,8,9,10,11]
const SECURITY_OPTIONS = [
  { value: 'open', label: 'Open', desc: 'No authentication' },
  { value: 'wep', label: 'WEP', desc: 'Legacy encryption' },
  { value: 'wpa2-psk', label: 'WPA2-PSK', desc: 'Pre-shared key' },
  { value: 'wpa2-enterprise', label: 'WPA2-Enterprise', desc: 'RADIUS auth' },
]

function AccessPoints() {
  const [aps, setAps] = useState([])
  const [showCreate, setCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)
  const [expandedAp, setExpanded] = useState(null)
  const [apClients, setApClients] = useState({})
  const [form, setForm] = useState({
    ssid: '', security: 'wpa2-psk', password: '', wep_key: '',
    channel: 6, hidden: false, num_clients: 2,
  })
  const [actionResult, setActionResult] = useState(null)
  const [backendEvents, setBackendEvents] = useState([])

  const load = async () => {
    try { setAps(await apApi.list()); setError(null) }
    catch (e) { setError(e.message) }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    eventSocket.connect()
    const unsub = eventSocket.subscribe((msg) => {
      if (msg.type !== 'event' || !msg.data) return
      const event = msg.data
      if (!['ap', 'adapter', 'client', 'cmd', 'radius', 'error'].includes(event.source)) return
      setBackendEvents(prev => [event, ...prev].slice(0, 8))
    })
    return () => unsub()
  }, [])

  const loadClients = async (apId) => {
    if (expandedAp === apId) { setExpanded(null); return }
    try {
      const data = await apApi.clients(apId)
      setApClients(prev => ({ ...prev, [apId]: data }))
      setExpanded(apId)
    } catch (e) { setError(e.message) }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setCreating(true); setError(null)
    try {
      const payload = { ...form, channel: Number(form.channel), num_clients: Number(form.num_clients) }
      if (payload.security === 'open') { delete payload.password; delete payload.wep_key }
      if (payload.security === 'wep') { delete payload.password }
      if (payload.security !== 'wep') { delete payload.wep_key }
      await apApi.create(payload)
      setCreate(false)
      setForm({ ssid: '', security: 'wpa2-psk', password: '', wep_key: '', channel: 6, hidden: false, num_clients: 2 })
      await load()
    } catch (e) { setError(e.message) }
    finally { setCreating(false) }
  }

  const handleStop = async (id, ssid) => {
    if (!window.confirm(`Stop AP "${ssid}" and disconnect all its clients?`)) return
    try { await apApi.stop(id); setExpanded(null); await load() }
    catch (e) { setError(e.message) }
  }

  const doClientAction = async (apId, clientId, action, extra = {}) => {
    try {
      const r = await clientApi.action(clientId, { action, ...extra })
      setActionResult({ type: 'success', msg: r.message || 'Action performed' })
      setTimeout(() => setActionResult(null), 4000)
    } catch (e) {
      setActionResult({ type: 'error', msg: e.message })
    }
  }

  const handleFloodTraffic = async (apId, ssid, security) => {
    try {
      const r = await apApi.floodTraffic(apId)
      setActionResult({ 
        type: 'success', 
        msg: `${r.message} - ${security === 'wep' ? 'IVs generating rapidly!' : 'High traffic for handshake capture'}` 
      })
      setTimeout(() => setActionResult(null), 6000)
    } catch (e) {
      setActionResult({ type: 'error', msg: e.message })
    }
  }

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Access Points</h1>
          <p className="page-subtitle">{aps.length} active network{aps.length !== 1 ? 's' : ''}</p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreate(true)}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
          New Access Point
        </button>
      </div>

      {/* Errors / results */}
      {error && (
        <div className="flex items-center gap-3 p-4 mb-4 bg-tertiary/10 border border-tertiary/30 rounded-lg">
          <span className="material-symbols-outlined text-tertiary">error</span>
          <span className="text-tertiary flex-1">{error}</span>
          <button onClick={() => setError(null)} className="text-tertiary hover:text-on-surface">
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
          </button>
        </div>
      )}
      {actionResult && (
        <div className={`flex items-center gap-3 p-4 mb-4 rounded-lg ${
          actionResult.type === 'error' 
            ? 'bg-tertiary/10 border border-tertiary/30' 
            : 'bg-secondary/10 border border-secondary/30'
        }`}>
          <span className={`material-symbols-outlined ${actionResult.type === 'error' ? 'text-tertiary' : 'text-secondary'}`}>
            {actionResult.type === 'error' ? 'error' : 'check_circle'}
          </span>
          <span className={actionResult.type === 'error' ? 'text-tertiary' : 'text-secondary'}>
            {actionResult.msg}
          </span>
        </div>
      )}

      {(creating || backendEvents.length > 0) && (
        <LiveOperationPanel events={backendEvents} compact={!creating} />
      )}

      {/* Create AP Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setCreate(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Create Access Point</h3>
              <button onClick={() => setCreate(false)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="modal-body">
                {/* SSID */}
                <div className="mb-4">
                  <label className="label">Network Name (SSID)</label>
                  <input 
                    className="input" 
                    type="text" 
                    required 
                    maxLength={32}
                    value={form.ssid} 
                    onChange={e => setForm({ ...form, ssid: e.target.value })}
                    placeholder="e.g. CoffeeShop_WiFi" 
                  />
                </div>

                {/* Security Type */}
                <div className="mb-4">
                  <label className="label">Security Type</label>
                  <div className="grid grid-cols-2 gap-2">
                    {SECURITY_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setForm({ ...form, security: opt.value })}
                        className={`p-3 rounded-lg border text-left transition-all ${
                          form.security === opt.value
                            ? 'border-primary bg-primary/10'
                            : 'border-outline-variant hover:border-on-surface-variant'
                        }`}
                      >
                        <div className={`font-medium text-sm ${form.security === opt.value ? 'text-primary' : 'text-on-surface'}`}>
                          {opt.label}
                        </div>
                        <div className="text-label-sm text-on-surface-variant">{opt.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Password field for WPA2-PSK */}
                {form.security === 'wpa2-psk' && (
                  <div className="mb-4">
                    <label className="label">Password</label>
                    <input 
                      className="input" 
                      type="text" 
                      required 
                      minLength={8} 
                      maxLength={63}
                      value={form.password} 
                      onChange={e => setForm({ ...form, password: e.target.value })}
                      placeholder="Minimum 8 characters" 
                    />
                    <div className="text-label-sm text-on-surface-variant mt-1">8-63 characters required</div>
                  </div>
                )}

                {/* WEP Key field */}
                {form.security === 'wep' && (
                  <div className="mb-4">
                    <label className="label">WEP Key</label>
                    <input 
                      className="input" 
                      type="text" 
                      required
                      value={form.wep_key} 
                      onChange={e => setForm({ ...form, wep_key: e.target.value })}
                      placeholder="5/13 chars or 10/26 hex" 
                    />
                    <div className="text-label-sm text-on-surface-variant mt-1">
                      5 or 13 ASCII characters, or 10 or 26 hex digits
                    </div>
                  </div>
                )}

                {/* Channel and Clients */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="label">Channel</label>
                    <select 
                      className="input" 
                      value={form.channel}
                      onChange={e => setForm({ ...form, channel: parseInt(e.target.value) })}
                    >
                      {CHANNELS.map(c => <option key={c} value={c}>Channel {c}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="label">Simulated Clients: {form.num_clients}</label>
                    <input 
                      type="range" 
                      min={0} 
                      max={8} 
                      step={1}
                      value={form.num_clients}
                      onChange={e => setForm({ ...form, num_clients: parseInt(e.target.value) })}
                      className="w-full mt-2"
                      style={{ accentColor: 'var(--primary)' }}
                    />
                    <div className="flex justify-between text-label-sm text-on-surface-variant mt-1">
                      <span>0</span>
                      <span>4</span>
                      <span>8</span>
                    </div>
                  </div>
                </div>

                {/* Hidden SSID */}
                <label className="flex items-center gap-3 cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={form.hidden}
                    onChange={e => setForm({ ...form, hidden: e.target.checked })}
                    className="w-4 h-4"
                    style={{ accentColor: 'var(--primary)' }}
                  />
                  <span className="text-sm text-on-surface-variant">Hidden SSID (does not broadcast)</span>
                </label>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setCreate(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={creating}>
                  {creating ? (
                    <>
                      <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>sync</span>
                      Creating...
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>cell_tower</span>
                      Deploy AP
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AP List */}
      {aps.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <span className="material-symbols-outlined" style={{ fontSize: 48 }}>cell_tower</span>
            <div className="font-semibold text-on-surface">No Access Points</div>
            <div className="text-sm text-on-surface-variant max-w-xs">
              Create an AP to start broadcasting. Simulated clients will be generated automatically.
            </div>
            <button className="btn btn-primary mt-2" onClick={() => setCreate(true)}>
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
              New Access Point
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {aps.map(ap => (
            <APCard
              key={ap.id}
              ap={ap}
              expanded={expandedAp === ap.id}
              clients={apClients[ap.id] || []}
              onExpand={() => loadClients(ap.id)}
              onStop={() => handleStop(ap.id, ap.ssid)}
              onClientAction={doClientAction}
              onFloodTraffic={() => handleFloodTraffic(ap.id, ap.ssid, ap.security)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

const DEPLOY_STEPS = [
  { key: 'creating', label: 'Creating virtual interface', match: /creating ap/i },
  { key: 'config', label: 'Generating hostapd config', match: /hostapd config/i },
  { key: 'hostapd', label: 'Starting hostapd (Wi-Fi AP)', match: /^hostapd\s/ },
  { key: 'dnsmasq', label: 'Starting DHCP server (dnsmasq)', match: /dnsmasq -C/i },
  { key: 'clients', label: 'Connecting client bots (wpa_supplicant)', match: /wpa_supplicant/i },
  { key: 'running', label: 'AP is live and broadcasting', match: /running/i },
]

function computeProgress(events) {
  if (!events.length) return { step: 0, label: 'Starting...', total: DEPLOY_STEPS.length }
  let maxStep = 0
  let label = 'Starting...'
  for (const ev of events) {
    for (let i = DEPLOY_STEPS.length - 1; i >= 0; i--) {
      if (DEPLOY_STEPS[i].match.test(ev.message) && i + 1 > maxStep) {
        maxStep = i + 1
        label = DEPLOY_STEPS[Math.min(i + 1, DEPLOY_STEPS.length - 1)].label
      }
    }
  }
  return { step: maxStep, label, total: DEPLOY_STEPS.length }
}

function LiveOperationPanel({ events, compact }) {
  if (!events.length && compact) return null
  const prog = computeProgress(events)
  const pct = Math.round((prog.step / prog.total) * 100)
  const isError = events.some(e => e.level === 'error')
  const done = prog.step >= prog.total

  return (
    <div className="card p-4 mb-4" style={{ borderColor: isError ? 'var(--tertiary)' : 'var(--primary)' }}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined" style={{ fontSize: 18, color: isError ? 'var(--tertiary)' : 'var(--primary)' }}>
            {done ? 'check_circle' : isError ? 'error' : 'terminal'}
          </span>
          <span className="font-semibold text-on-surface" style={{ fontSize: 13 }}>
            {done ? 'Deployment Complete' : 'Deploying Access Point'}
          </span>
        </div>
        {!done && !compact && (
          <span className="text-label-sm text-primary font-mono">{pct}%</span>
        )}
      </div>

      {/* Progress Bar */}
      {!done && (
        <div className="w-full h-2 bg-surface-container rounded-full overflow-hidden mb-3">
          <div
            className="h-full rounded-full transition-all duration-500 ease-out"
            style={{
              width: `${pct}%`,
              background: isError
                ? 'var(--tertiary)'
                : 'linear-gradient(90deg, var(--primary), var(--secondary))',
            }}
          />
        </div>
      )}

      {/* Current step label */}
      {!done && (
        <div className="text-label-sm text-on-surface-variant font-mono mb-2">{prog.label}</div>
      )}

      {/* Event log (collapsible) */}
      {events.length > 0 && (
        <div className="flex flex-col gap-1.5 max-h-32 overflow-y-auto">
          {events.map((event, idx) => (
            <div key={`${event.timestamp}-${idx}`} className="flex items-start gap-2" style={{ fontSize: 11 }}>
              <span className={`badge ${
                event.level === 'error' ? 'badge-tertiary' :
                event.level === 'warning' ? 'badge-warning' :
                event.source === 'cmd' ? 'badge-primary' : 'badge-muted'
              }`}>
                {event.source}
              </span>
              <span className="font-mono" style={{
                color: event.level === 'error' ? 'var(--tertiary)' :
                       event.level === 'warning' ? '#fbbf24' : 'var(--text-secondary)',
                overflowWrap: 'anywhere'
              }}>
                {event.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function APCard({ ap, expanded, clients, onExpand, onStop, onClientAction, onFloodTraffic }) {
  const running = ap.status === 'running'
  
  const securityColors = {
    'open': 'badge-warning',
    'wep': 'badge-tertiary',
    'wpa2-psk': 'badge-secondary',
    'wpa2-enterprise': 'badge-primary',
  }

  // Get password/key to display
  const getCredential = () => {
    if (ap.security === 'open') return null
    if (ap.security === 'wep') return ap.wep_key || ap.password
    if (ap.security === 'wpa2-psk') return ap.password
    if (ap.security === 'wpa2-enterprise') return 'RADIUS'
    return ap.password
  }
  const credential = getCredential()

  // Show flood button for WEP and WPA2 networks (not open)
  const showFloodButton = ap.security !== 'open' && ap.clients_connected > 0

  return (
    <div className="card overflow-hidden animate-fade-in">
      {/* Header */}
      <div className={`flex items-center justify-between p-4 ${running ? 'bg-primary/5' : 'bg-tertiary/5'}`}>
        <div className="flex items-center gap-4">
          {/* Status indicator */}
          <div className="relative">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${running ? 'bg-secondary/20' : 'bg-tertiary/20'}`}>
              <span className={`material-symbols-outlined ${running ? 'text-secondary' : 'text-tertiary'}`} style={{ fontSize: 22 }}>
                cell_tower
              </span>
            </div>
            <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-surface ${
              running ? 'status-dot-active' : 'status-dot-error'
            }`} />
          </div>

          {/* AP Info */}
          <div>
            <div className="flex items-center gap-3">
              <Link to={`/access-points/${ap.id}`} className="font-semibold text-on-surface hover:text-primary transition-colors" style={{ textDecoration: 'none' }}>
                {ap.hidden && <span className="text-on-surface-variant italic">[hidden] </span>}
                {ap.ssid}
              </Link>
              <span className={`badge ${securityColors[ap.security] || 'badge-muted'}`}>
                {ap.security.toUpperCase()}
              </span>
              {!running && <span className="badge badge-tertiary">FAILED</span>}
            </div>
            <div className="flex items-center gap-4 mt-1">
              <span className="text-label-md text-on-surface-variant font-mono">{ap.bssid || 'unknown'}</span>
              <span className="text-label-md text-on-surface-variant">CH {ap.channel}</span>
              <span className="text-label-md text-primary font-mono">{ap.interface}</span>
            </div>
            {/* Password/Key display */}
            {credential && (
              <div className="flex items-center gap-2 mt-2">
                <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--tertiary)' }}>key</span>
                <span className="text-label-md font-mono" style={{ 
                  color: ap.security === 'wpa2-enterprise' ? 'var(--primary)' : 'var(--tertiary)',
                  background: ap.security === 'wpa2-enterprise' ? 'rgba(137,206,255,0.1)' : 'rgba(255,178,183,0.1)',
                  padding: '2px 8px',
                  borderRadius: 4,
                  border: ap.security === 'wpa2-enterprise' ? '1px solid rgba(137,206,255,0.2)' : '1px solid rgba(255,178,183,0.2)'
                }}>
                  {credential}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          <Link 
            to={`/access-points/${ap.id}`}
            className="btn btn-ghost btn-sm"
            title="View Details"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>info</span>
          </Link>
          {showFloodButton && (
            <button
              onClick={onFloodTraffic}
              className="btn btn-sm"
              style={{ 
                background: ap.security === 'wep' ? 'rgba(255,178,183,0.2)' : 'rgba(78,222,163,0.2)',
                color: ap.security === 'wep' ? 'var(--tertiary)' : 'var(--secondary)',
                border: `1px solid ${ap.security === 'wep' ? 'rgba(255,178,183,0.4)' : 'rgba(78,222,163,0.4)'}`
              }}
              title={ap.security === 'wep' ? 'Generate IVs for WEP cracking' : 'Generate traffic for handshake capture'}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>bolt</span>
              {ap.security === 'wep' ? 'Gen IVs' : 'Flood'}
            </button>
          )}
          <button
            onClick={onExpand}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-primary/10 border border-primary/30 text-primary text-label-md font-mono hover:bg-primary/20 transition-all"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>devices</span>
            {ap.clients_connected} client{ap.clients_connected !== 1 ? 's' : ''}
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
              {expanded ? 'expand_less' : 'expand_more'}
            </span>
          </button>
          <button className="btn btn-danger btn-sm" onClick={onStop}>
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>stop</span>
            Stop
          </button>
        </div>
      </div>

      {/* Expanded Clients */}
      {expanded && (
        <div className="p-4 border-t border-outline-variant animate-fade-in">
          <div className="text-label-md text-on-surface-variant font-mono uppercase mb-3">
            Connected Clients
          </div>
          {clients.length === 0 ? (
            <div className="text-center py-6 text-on-surface-variant">
              <span className="material-symbols-outlined mb-2" style={{ fontSize: 32, opacity: 0.5 }}>devices_off</span>
              <div className="text-sm">No clients connected</div>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {clients.map(client => (
                <ClientRow key={client.id} client={client} ap={ap} onAction={onClientAction} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ClientRow({ client, ap, onAction }) {
  const deviceIcons = {
    laptop: 'laptop_mac',
    macbook: 'laptop_mac',
    smartphone: 'smartphone',
    tablet: 'tablet_mac',
    server: 'dns',
    iot: 'settings_remote',
  }
  const icon = deviceIcons[client.device_type] || 'devices'
  const state = client.connection_state || (client.ip_address ? 'connected' : 'unknown')

  return (
    <div className="flex items-center justify-between p-3 bg-surface-container rounded-lg border border-outline-variant">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>{icon}</span>
        </div>
        <div>
          <div className="font-medium text-on-surface text-sm">{client.persona || client.id}</div>
          <div className="flex items-center gap-3 mt-0.5">
            {client.hostname && (
              <span className="text-label-sm text-on-surface-variant font-mono">{client.hostname}</span>
            )}
            <span className="text-label-sm text-on-surface-variant font-mono">{client.mac_address}</span>
            <span className="text-label-sm text-primary font-mono">{client.ip_address || 'no ip'}</span>
            <span className={`badge ${state === 'connected' ? 'badge-secondary' : 'badge-warning'}`}>
              {state.replaceAll('_', ' ')}
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Link to={`/clients/${client.id}`} className="btn btn-ghost btn-sm">
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>open_in_new</span>
          Details
        </Link>
        <button className="btn btn-ghost btn-sm" onClick={() => onAction(ap.id, client.id, 'reconnect')}>
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>refresh</span>
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => onAction(ap.id, client.id, 'browse_url', { url: 'http://example.com' })}>
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>language</span>
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => onAction(ap.id, client.id, 'open_captive')}>
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>captive_portal</span>
        </button>
      </div>
    </div>
  )
}

export default AccessPoints
