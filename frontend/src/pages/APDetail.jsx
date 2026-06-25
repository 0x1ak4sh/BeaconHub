import React, { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apApi, clientApi } from '../services/api'

function APDetail() {
  const { apId } = useParams()
  const [ap, setAp] = useState(null)
  const [clients, setClients] = useState([])
  const [log, setLog] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionResult, setActionResult] = useState(null)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editForm, setEditForm] = useState({ password: '', hidden: false, channel: 6 })
  const [wepStatus, setWepStatus] = useState(null)
  const wepPollRef = useRef(null)

  const load = async () => {
    try {
      const [apData, clientsData, logData] = await Promise.all([
        apApi.get(apId),
        apApi.clients(apId),
        apApi.log(apId).catch(() => ({ log: '' }))
      ])
      setAp(apData)
      setClients(clientsData)
      setLog(logData.log || '')
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 4000)
    return () => {
      clearInterval(t)
      if (wepPollRef.current) clearInterval(wepPollRef.current)
    }
  }, [apId])

  const handleStop = async () => {
    if (!window.confirm(`Stop AP "${ap?.ssid}" and disconnect all clients?`)) return
    try {
      await apApi.stop(apId)
      window.location.href = '/access-points'
    } catch (e) {
      setError(e.message)
    }
  }

  const doClientAction = async (clientId, action, extra = {}) => {
    try {
      const r = await clientApi.action(clientId, { action, ...extra })
      setActionResult({ type: 'success', msg: r.message || 'Action performed' })
      setTimeout(() => setActionResult(null), 3000)
      await load()
    } catch (e) {
      setActionResult({ type: 'error', msg: e.message })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ height: 200 }}>
        <span className="material-symbols-outlined animate-spin" style={{ fontSize: 32, color: 'var(--text-muted)' }}>sync</span>
      </div>
    )
  }

  if (error || !ap) {
    return (
      <div className="card">
        <div className="empty-state">
          <span className="material-symbols-outlined" style={{ fontSize: 48, color: 'var(--tertiary)' }}>error</span>
          <div>{error || 'Access Point not found'}</div>
          <Link to="/access-points" className="btn btn-ghost">Back to Access Points</Link>
        </div>
      </div>
    )
  }

  const isRunning = ap.status === 'running'
  const securityLabels = {
    'open': { label: 'OPEN', color: 'warning' },
    'wep': { label: 'WEP', color: 'tertiary' },
    'wpa2-psk': { label: 'WPA2-PSK', color: 'secondary' },
    'wpa2-enterprise': { label: 'WPA2-ENT', color: 'primary' },
  }
  const secInfo = securityLabels[ap.security] || { label: ap.security, color: 'muted' }

  return (
    <div className="animate-fade-in">
      {/* Breadcrumb */}
      <div className="flex items-center gap-3 mb-4">
        <Link to="/access-points" className="flex items-center gap-1" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: 12 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_back</span>
          Access Points
        </Link>
        <span style={{ color: 'var(--border)' }}>/</span>
        <span style={{ fontWeight: 600 }}>{ap.ssid}</span>
        {isRunning && (
          <span className="flex items-center gap-1" style={{ color: 'var(--secondary)', fontSize: 11 }}>
            <div className="status-dot status-dot-active" />
            Broadcasting
          </span>
        )}
      </div>

      {/* Action Result */}
      {actionResult && (
        <div className={`flex items-center gap-3 p-3 mb-4 rounded-lg ${
          actionResult.type === 'error' ? 'bg-tertiary/10 border border-tertiary/30' : 'bg-secondary/10 border border-secondary/30'
        }`} style={{ fontSize: 12 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 16, color: actionResult.type === 'error' ? 'var(--tertiary)' : 'var(--secondary)' }}>
            {actionResult.type === 'error' ? 'error' : 'check_circle'}
          </span>
          <span style={{ color: actionResult.type === 'error' ? 'var(--tertiary)' : 'var(--secondary)' }}>{actionResult.msg}</span>
        </div>
      )}

      {/* Main Info Card */}
      <div className="card p-5 mb-4">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-4">
            <div style={{
              width: 56, height: 56, borderRadius: 12,
              background: isRunning ? 'rgba(78,222,163,0.15)' : 'rgba(255,178,183,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <span className="material-symbols-outlined" style={{ fontSize: 28, color: isRunning ? 'var(--secondary)' : 'var(--tertiary)' }}>
                cell_tower
              </span>
            </div>
            <div>
              <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>
                {ap.hidden && <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>[hidden] </span>}
                {ap.ssid}
              </h1>
              <div className="flex items-center gap-3">
                <span className={`badge badge-${secInfo.color}`}>{secInfo.label}</span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Channel {ap.channel}</span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{ap.interface}</span>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button 
              className="btn btn-ghost" 
              onClick={async () => {
                try {
                  await apApi.beacon(apId)
                  setActionResult({ type: 'success', msg: 'Beacon refresh triggered' })
                } catch (e) {
                  setActionResult({ type: 'error', msg: e.message })
                }
              }}
              title="Force beacon re-broadcast"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>cell_tower</span>
              Beacon
            </button>
            <button 
              className="btn btn-ghost" 
              onClick={() => {
                setEditForm({ 
                  password: ap.password || '', 
                  hidden: ap.hidden, 
                  channel: ap.channel 
                })
                setShowEditModal(true)
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>edit</span>
              Edit
            </button>
            <button className="btn btn-danger" onClick={handleStop}>
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>stop</span>
              Stop AP
            </button>
          </div>
        </div>

        {/* Network Details */}
        <div className="info-box">
          <div className="info-row">
            <span className="info-label">BSSID</span>
            <span className="info-value">{ap.bssid || 'Unknown'}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Security</span>
            <span className="info-value">{ap.security.toUpperCase()}</span>
          </div>
          {(ap.security === 'wpa2-psk' || ap.security === 'wep') && ap.password && (
            <div className="info-row">
              <span className="info-label">Password</span>
              <span className="info-value secret">{ap.password}</span>
            </div>
          )}
          {ap.security === 'wpa2-enterprise' && (
            <div className="info-row">
              <span className="info-label">Auth</span>
              <span className="info-value">RADIUS (EAP)</span>
            </div>
          )}
          <div className="info-row">
            <span className="info-label">Channel</span>
            <span className="info-value">{ap.channel}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Interface</span>
            <span className="info-value">{ap.interface}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Hidden SSID</span>
            <span className="info-value">{ap.hidden ? 'Yes' : 'No'}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Connected Clients</span>
            <span className="info-value" style={{ color: 'var(--primary)' }}>{clients.length}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Created</span>
            <span className="info-value">{new Date(ap.created_at).toLocaleString()}</span>
          </div>
        </div>

        {/* WPA2-Enterprise Users */}
        {ap.security === 'wpa2-enterprise' && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8, fontFamily: 'JetBrains Mono, monospace' }}>
              RADIUS Test Users
            </div>
            <div className="info-box" style={{ marginBottom: 0 }}>
              <div className="info-row">
                <span className="info-label">User 1</span>
                <span className="info-value secret">employee@corp.local / Welcome123</span>
              </div>
              <div className="info-row">
                <span className="info-label">User 2</span>
                <span className="info-value secret">admin@corp.local / Admin@123</span>
              </div>
              <div className="info-row">
                <span className="info-label">User 3</span>
                <span className="info-value secret">guest / guest123</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* WEP IV Generation Controls */}
      {ap.security === 'wep' && (
        <div className="card p-5 mb-4" style={{ background: 'rgba(186,159,255,0.05)', borderColor: 'var(--tertiary)' }}>
          <div className="flex items-center gap-3 mb-4">
            <span className="material-symbols-outlined" style={{ fontSize: 22, color: 'var(--tertiary)' }}>key</span>
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--tertiary)' }}>WEP Cracking</h3>
              <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>Generate IVs for aircrack-ng attack</p>
            </div>
          </div>

          {/* IV Progress Bar */}
          {wepStatus && wepStatus.status === 'running' && (
            <div style={{ marginBottom: 16 }}>
              <div className="flex justify-between text-label-sm mb-1">
                <span className="text-tertiary font-mono">
                  {wepStatus.iv_count} / 5000 IVs
                  {wepStatus.iv_rate_per_sec > 0 && (
                    <span className="text-on-surface-variant"> ({wepStatus.iv_rate_per_sec}/s)</span>
                  )}
                </span>
                <span className="text-on-surface-variant font-mono">
                  {wepStatus.eta_seconds > 0
                    ? `ETA ${Math.ceil(wepStatus.eta_seconds / 60)}m ${wepStatus.eta_seconds % 60}s`
                    : 'Collecting...'}
                </span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${Math.min(100, (wepStatus.iv_count / 5000) * 100)}%`,
                    background: 'linear-gradient(90deg, var(--tertiary), var(--secondary))',
                  }}
                />
              </div>
              <div className="flex gap-4 mt-2 text-label-sm text-on-surface-variant font-mono">
                <span>Elapsed: {wepStatus.elapsed_seconds}s</span>
                <span>Replays: {wepStatus.replays?.filter(r => r.running).length || 0} active</span>
              </div>
            </div>
          )}

          <div className="flex gap-3 flex-wrap">
            <button
              className={`btn ${wepStatus?.status === 'running' ? 'btn-danger' : 'btn-tertiary'}`}
              onClick={async () => {
                try {
                  if (wepStatus?.status === 'running') {
                    const r = await apApi.stopFlood(apId)
                    setActionResult({ type: 'success', msg: r.message })
                    if (wepPollRef.current) { clearInterval(wepPollRef.current); wepPollRef.current = null }
                    setWepStatus(null)
                  } else {
                    const r = await apApi.floodTraffic(apId)
                    setActionResult({ type: 'success', msg: `IV flood: ${r.message}` })
                    // Poll IV status every 2s
                    if (wepPollRef.current) clearInterval(wepPollRef.current)
                    wepPollRef.current = setInterval(async () => {
                      try {
                        const s = await apApi.wepStatus(apId)
                        setWepStatus(s)
                      } catch {}
                    }, 2000)
                  }
                } catch (e) {
                  setActionResult({ type: 'error', msg: e.message })
                }
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                {wepStatus?.status === 'running' ? 'stop_circle' : 'bolt'}
              </span>
              {wepStatus?.status === 'running' ? 'Stop & Collect' : 'Speed Up IVs'}
            </button>
          </div>

          {/* IV collected summary */}
          {wepStatus && wepStatus.iv_count > 0 && (
            <div className="info-box" style={{ marginTop: 16 }}>
              <div className="info-row">
                <span className="info-label">IVs Collected</span>
                <span className="info-value" style={{ fontFamily: 'JetBrains Mono', color: 'var(--tertiary)' }}>
                  {wepStatus.iv_count}
                </span>
              </div>
              <div className="info-row">
                <span className="info-label">IV Rate</span>
                <span className="info-value" style={{ fontFamily: 'JetBrains Mono' }}>
                  {wepStatus.iv_rate_per_sec || 0} IVs/sec
                </span>
              </div>
              {wepStatus.capture_file && (
                <div className="info-row">
                  <span className="info-label">Capture File</span>
                  <span className="info-value" style={{ fontFamily: 'JetBrains Mono', fontSize: 11 }}>
                    {wepStatus.capture_file}
                  </span>
                </div>
              )}
            </div>
          )}

          <div className="info-box" style={{ marginTop: 16 }}>
            <div className="info-row">
              <span className="info-label">Crack Command</span>
              <span className="info-value" style={{ fontFamily: 'JetBrains Mono' }}>
                aircrack-ng -b {ap.bssid} /opt/beaconhub/captures/wep_capture_*.cap
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Connected Clients */}
      <div className="card p-5 mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 style={{ fontSize: 14, fontWeight: 600 }}>
            Connected Clients ({clients.length})
          </h2>
        </div>

        {clients.length === 0 ? (
          <div className="empty-state" style={{ padding: '32px 16px' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 36 }}>devices_off</span>
            <div style={{ fontSize: 13 }}>No clients connected</div>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {clients.map(client => (
              <ClientRow 
                key={client.id} 
                client={client} 
                onAction={doClientAction}
                isEnterprise={ap.security === 'wpa2-enterprise'}
              />
            ))}
          </div>
        )}
      </div>

      {/* Hostapd Log */}
      <div className="card overflow-hidden">
        <div style={{ 
          padding: '12px 16px', 
          borderBottom: '1px solid var(--border)',
          fontSize: 12, fontWeight: 600
        }}>
          Hostapd Log
        </div>
        <div style={{ 
          padding: 16, 
          fontFamily: 'JetBrains Mono, monospace', 
          fontSize: 11,
          maxHeight: 250,
          overflowY: 'auto',
          background: 'var(--bg-base)',
          whiteSpace: 'pre-wrap',
          color: 'var(--text-secondary)'
        }}>
          {log || 'No log output yet...'}
        </div>
      </div>

      {/* Edit AP Modal */}
      {showEditModal && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <h3>Edit AP Settings</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowEditModal(false)}>
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <form onSubmit={async (e) => {
              e.preventDefault()
              try {
                const updates = {}
                if (editForm.password && editForm.password !== ap.password) {
                  updates.password = editForm.password
                }
                if (editForm.hidden !== ap.hidden) {
                  updates.hidden = editForm.hidden
                }
                if (editForm.channel !== ap.channel) {
                  updates.channel = editForm.channel
                }
                
                if (Object.keys(updates).length === 0) {
                  setShowEditModal(false)
                  return
                }
                
                await apApi.update(apId, updates)
                setActionResult({ type: 'success', msg: 'AP settings updated' })
                setShowEditModal(false)
                await load()
              } catch (err) {
                setActionResult({ type: 'error', msg: err.message })
              }
            }}>
              <div className="modal-body">
                {(ap.security === 'wpa2-psk' || ap.security === 'wep') && (
                  <div className="mb-4">
                    <label className="label">Password / Key</label>
                    <input
                      className="input"
                      type="text"
                      value={editForm.password}
                      onChange={e => setEditForm({ ...editForm, password: e.target.value })}
                      placeholder={ap.security === 'wep' ? '5/13 chars or 10/26 hex' : 'Min 8 characters'}
                    />
                    <span className="text-label-sm text-on-surface-variant mt-1">
                      {ap.security === 'wep' ? 'WEP key (5/13 ASCII or 10/26 hex)' : 'WPA2 passphrase (8-63 chars)'}
                    </span>
                  </div>
                )}
                
                <div className="mb-4">
                  <label className="label">Channel</label>
                  <select
                    className="input"
                    value={editForm.channel}
                    onChange={e => setEditForm({ ...editForm, channel: parseInt(e.target.value) })}
                  >
                    {[1,2,3,4,5,6,7,8,9,10,11,12,13,14].map(ch => (
                      <option key={ch} value={ch}>Channel {ch}</option>
                    ))}
                  </select>
                </div>
                
                <div className="mb-4">
                  <label className="flex items-center gap-2" style={{ cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={editForm.hidden}
                      onChange={e => setEditForm({ ...editForm, hidden: e.target.checked })}
                      style={{ width: 16, height: 16 }}
                    />
                    <span>Hidden SSID</span>
                  </label>
                  <span className="text-label-sm text-on-surface-variant mt-1">SSID won't appear in network scans</span>
                </div>
              </div>
              
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowEditModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>save</span>
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function ClientRow({ client, onAction, isEnterprise }) {
  const deviceIcons = {
    laptop: 'laptop_mac', macbook: 'laptop_mac', smartphone: 'smartphone',
    tablet: 'tablet_mac', server: 'dns', iot: 'settings_remote',
  }
  const icon = deviceIcons[client.device_type] || 'devices'
  const state = client.connection_state || (client.ip_address ? 'connected' : 'unknown')

  return (
    <div className="info-box" style={{ marginBottom: 0, padding: 12 }}>
      <div className="flex items-center gap-3">
        <div style={{
          width: 40, height: 40, borderRadius: 8,
          background: 'rgba(137,206,255,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 22, color: 'var(--primary)' }}>{icon}</span>
        </div>
        
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="flex items-center gap-2 mb-1">
            <span style={{ fontWeight: 600, fontSize: 13 }}>{client.persona || client.id}</span>
            {client.device_type && <span className="badge badge-muted">{client.device_type}</span>}
            {client.traffic_running && (
              <span className="badge badge-secondary">
                <span className="material-symbols-outlined" style={{ fontSize: 10 }}>play_arrow</span>
                Traffic
              </span>
            )}
            <span className={`badge ${state === 'connected' ? 'badge-secondary' : 'badge-warning'}`}>
              {state.replaceAll('_', ' ')}
            </span>
          </div>
          <div className="flex items-center gap-4" style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>
            <span style={{ color: 'var(--text-muted)' }}>{client.mac_address}</span>
            <span style={{ color: 'var(--primary)' }}>{client.ip_address || 'No IP'}</span>
            {client.hostname && <span style={{ color: 'var(--text-muted)' }}>{client.hostname}</span>}
          </div>
          {state !== 'connected' && client.last_error && (
            <div style={{ marginTop: 6, color: 'var(--warning)', fontSize: 10 }}>
              {client.last_error}
            </div>
          )}
          
          {/* Show credentials if set */}
          {client.credentials && (
            <div style={{ 
              marginTop: 8, padding: '6px 10px', borderRadius: 4,
              background: 'rgba(255,178,183,0.08)', border: '1px solid rgba(255,178,183,0.2)',
              fontSize: 10, fontFamily: 'JetBrains Mono, monospace'
            }}>
              <span style={{ color: 'var(--tertiary)' }}>Creds: </span>
              <span style={{ color: 'var(--text-primary)' }}>{client.credentials.username} : {client.credentials.password}</span>
              <span style={{ color: 'var(--text-muted)' }}> → {client.credentials.url}</span>
            </div>
          )}
          
          {/* Show EAP identity for enterprise */}
          {isEnterprise && client.eap_identity && (
            <div style={{ 
              marginTop: 8, padding: '6px 10px', borderRadius: 4,
              background: 'rgba(137,206,255,0.08)', border: '1px solid rgba(137,206,255,0.2)',
              fontSize: 10, fontFamily: 'JetBrains Mono, monospace'
            }}>
              <span style={{ color: 'var(--primary)' }}>EAP Identity: </span>
              <span style={{ color: 'var(--text-primary)' }}>{client.eap_identity}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button className="btn btn-ghost btn-sm" onClick={() => onAction(client.id, 'reconnect')} title="Reconnect">
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>refresh</span>
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => onAction(client.id, 'browse_url', { url: 'http://example.com' })} title="Browse">
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>language</span>
          </button>
          <Link to={`/clients/${client.id}`} className="btn btn-primary btn-sm">
            Details
          </Link>
        </div>
      </div>
    </div>
  )
}

export default APDetail
