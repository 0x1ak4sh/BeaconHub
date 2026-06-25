import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { clientApi, apApi } from '../services/api'

const SECURITY_OPTIONS = [
  { value: 'open', label: 'Open', desc: 'No password' },
  { value: 'wep', label: 'WEP', desc: 'Legacy' },
  { value: 'wpa2-psk', label: 'WPA2-PSK', desc: 'Password' },
  { value: 'wpa2-enterprise', label: 'WPA2-ENT', desc: 'Username/Pass' },
]

function Clients() {
  const [clients, setClients] = useState([])
  const [aps, setAps] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [credModal, setCredModal] = useState(null)
  const [credForm, setCredForm] = useState({ username: '', password: '', target_url: 'http://10.0.1.1/login', submit_and_reconnect: true })
  const [submitting, setSubmitting] = useState(false)
  const [toast, setToast] = useState(null)
  const [toggling, setToggling] = useState({})
  
  // New client creation modal
  const [showCreateClient, setShowCreateClient] = useState(false)
  const [createForm, setCreateForm] = useState({
    ssid: '',
    security: 'wpa2-psk',
    password: '',
    persona: '',
    device_type: 'laptop',
    hostname: '',
    eap_identity: '',
    eap_password: '',
    use_wrong_password: false,
    ap_id: null,  // Track selected AP ID
  })
  const [creating, setCreating] = useState(false)

  const load = async () => {
    try { 
      const [clientsData, apsData] = await Promise.all([
        clientApi.listAll(),
        apApi.list()
      ])
      setClients(clientsData)
      setAps(apsData)
      setError(null) 
    }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const toggleTraffic = async (client) => {
    const id = client.id
    setToggling(p => ({ ...p, [id]: true }))
    try {
      if (client.traffic_running) {
        await clientApi.stopTraffic(id)
        showToast(`Traffic stopped for ${client.persona}`)
      } else {
        await clientApi.startTraffic(id)
        showToast(`Traffic started for ${client.persona}`)
      }
      await load()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setToggling(p => ({ ...p, [id]: false }))
    }
  }

  const openCredModal = (client) => {
    setCredModal(client)
    const existing = client.credentials || {}
    setCredForm({
      username: existing.username || '',
      password: existing.password || '',
      target_url: existing.url || 'http://10.0.1.1/login',
      submit_and_reconnect: true,
    })
  }

  const submitCreds = async () => {
    if (!credModal) return
    setSubmitting(true)
    try {
      const r = await clientApi.setCredentials(credModal.id, credForm)
      showToast(r.reconnected ? 'Credentials submitted + WPA handshake regenerated!' : 'Credentials saved')
      setCredModal(null)
      await load()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const doAction = async (clientId, action, extra = {}) => {
    try {
      const r = await clientApi.action(clientId, { action, ...extra })
      showToast(r.message || 'Action performed')
      await load()
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  const handleCreateClient = async (e) => {
    e.preventDefault()
    setCreating(true)
    setError(null)
    try {
      const payload = {
        ssid: createForm.ssid,
        security: createForm.security,
        persona: createForm.persona || undefined,
        device_type: createForm.device_type || undefined,
        hostname: createForm.hostname || undefined,
        ap_id: createForm.ap_id || undefined,  // Include AP ID if selected
      }
      
      // Handle password based on security type and wrong password option
      if (createForm.security === 'wpa2-psk' || createForm.security === 'wep') {
        if (createForm.use_wrong_password) {
          // Generate a wrong password (different from actual)
          payload.password = 'wrongpassword123'
        } else {
          payload.password = createForm.password
        }
      } else if (createForm.security === 'wpa2-enterprise') {
        payload.eap_identity = createForm.eap_identity
        payload.eap_password = createForm.use_wrong_password ? 'wrongpassword123' : createForm.eap_password
      }
      
      await clientApi.create(payload)
      showToast(createForm.use_wrong_password 
        ? 'Client created with WRONG password — auth failure expected' 
        : 'Client created and connecting...')
      setShowCreateClient(false)
      setCreateForm({
        ssid: '', security: 'wpa2-psk', password: '', persona: '',
        device_type: 'laptop', hostname: '', eap_identity: '', eap_password: '',
        use_wrong_password: false, ap_id: null,
      })
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setCreating(false)
    }
  }

  // Pre-fill form when selecting an existing AP
  const selectAp = (ap) => {
    setCreateForm({
      ...createForm,
      ssid: ap.ssid,
      security: ap.security,
      password: ap.password || ap.wep_key || '',
      ap_id: ap.id,  // Include the AP ID
    })
  }

  // Group by AP
  const byAp = clients.reduce((acc, c) => {
    const key = c.connected_to_ap
    if (!acc[key]) acc[key] = { ssid: c.ap_ssid || key, clients: [] }
    acc[key].clients.push(c)
    return acc
  }, {})

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Clients</h1>
          <p className="page-subtitle">
            {clients.length} simulated client{clients.length !== 1 ? 's' : ''} connected
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-label-md text-on-surface-variant font-mono">
            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
            {clients.filter(c => c.traffic_running).length} generating traffic
          </div>
          <button className="btn btn-primary" onClick={() => setShowCreateClient(true)}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>person_add</span>
            Add Client
          </button>
        </div>
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

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 p-4 mb-4 bg-tertiary/10 border border-tertiary/30 rounded-lg">
          <span className="material-symbols-outlined text-tertiary">error</span>
          <span className="text-tertiary">{error}</span>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="card p-12 text-center text-on-surface-variant">
          <span className="material-symbols-outlined animate-spin mb-2" style={{ fontSize: 32 }}>sync</span>
          <div>Loading clients...</div>
        </div>
      ) : clients.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <span className="material-symbols-outlined" style={{ fontSize: 48 }}>devices</span>
            <div className="font-semibold text-on-surface">No Clients Connected</div>
            <div className="text-sm text-on-surface-variant max-w-xs">
              Create an Access Point with simulated clients to see them here.
            </div>
            <Link to="/access-points" className="btn btn-primary mt-2">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>cell_tower</span>
              Go to Access Points
            </Link>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {Object.entries(byAp).map(([apId, group]) => (
            <div key={apId}>
              {/* AP Section Header */}
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: 18 }}>cell_tower</span>
                </div>
                <span className="font-semibold text-on-surface">{group.ssid}</span>
                <span className="text-label-md text-on-surface-variant font-mono">{group.clients.length} clients</span>
              </div>

              <div className="flex flex-col gap-2">
                {group.clients.map(client => (
                  <ClientCard
                    key={client.id}
                    client={client}
                    toggling={toggling[client.id]}
                    onToggleTraffic={() => toggleTraffic(client)}
                    onSetCreds={() => openCredModal(client)}
                    onAction={doAction}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Credential Modal */}
      {credModal && (
        <div className="modal-overlay" onClick={() => setCredModal(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Set Credentials - {credModal?.persona}</h3>
              <button onClick={() => setCredModal(null)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="modal-body">
              {/* Warning */}
              <div className="flex items-start gap-3 p-3 mb-4 bg-warning/10 border border-warning/30 rounded-lg">
                <span className="material-symbols-outlined text-warning" style={{ fontSize: 20 }}>warning</span>
                <div className="text-sm text-on-surface-variant">
                  Credentials will be sent as plaintext HTTP POST and visible in packet captures.
                </div>
              </div>

              <div className="mb-4">
                <label className="label">Username</label>
                <input 
                  className="input" 
                  type="text"
                  placeholder="e.g. admin@corp.com"
                  value={credForm.username}
                  onChange={e => setCredForm({ ...credForm, username: e.target.value })} 
                />
              </div>
              <div className="mb-4">
                <label className="label">Password</label>
                <input 
                  className="input" 
                  type="text"
                  placeholder="e.g. hunter2"
                  value={credForm.password}
                  onChange={e => setCredForm({ ...credForm, password: e.target.value })} 
                />
              </div>
              <div className="mb-4">
                <label className="label">Target URL</label>
                <input 
                  className="input" 
                  type="text"
                  placeholder="http://10.0.1.1/login"
                  value={credForm.target_url}
                  onChange={e => setCredForm({ ...credForm, target_url: e.target.value })} 
                />
                <div className="text-label-sm text-on-surface-variant mt-1">Endpoint receiving the POST request</div>
              </div>
              <label className="flex items-center gap-3 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={credForm.submit_and_reconnect}
                  onChange={e => setCredForm({ ...credForm, submit_and_reconnect: e.target.checked })}
                  className="w-4 h-4"
                  style={{ accentColor: 'var(--primary)' }}
                />
                <span className="text-sm text-on-surface-variant">Submit + reconnect (generates new WPA handshake)</span>
              </label>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setCredModal(null)}>Cancel</button>
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

      {/* Create Client Modal */}
      {showCreateClient && (
        <div className="modal-overlay" onClick={() => setShowCreateClient(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <h3 className="modal-title">Connect Client to WiFi</h3>
              <button onClick={() => setShowCreateClient(false)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <form onSubmit={handleCreateClient}>
              <div className="modal-body">
                {/* Quick select from existing APs */}
                {aps.length > 0 && (
                  <div className="mb-4">
                    <label className="label">Quick Select (Existing AP)</label>
                    <div className="flex flex-wrap gap-2">
                      {aps.map(ap => (
                        <button
                          key={ap.id}
                          type="button"
                          onClick={() => selectAp(ap)}
                          className={`px-3 py-1.5 rounded-lg border text-sm transition-all ${
                            createForm.ssid === ap.ssid
                              ? 'border-primary bg-primary/10 text-primary'
                              : 'border-outline-variant hover:border-on-surface-variant text-on-surface-variant'
                          }`}
                        >
                          {ap.ssid}
                          <span className="ml-1 opacity-60">({ap.security})</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* SSID */}
                <div className="mb-4">
                  <label className="label">Network SSID</label>
                  <input
                    className="input"
                    type="text"
                    required
                    value={createForm.ssid}
                    onChange={e => setCreateForm({ ...createForm, ssid: e.target.value })}
                    placeholder="WiFi network name"
                  />
                </div>

                {/* Security Type */}
                <div className="mb-4">
                  <label className="label">Security Type</label>
                  <div className="grid grid-cols-4 gap-2">
                    {SECURITY_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setCreateForm({ ...createForm, security: opt.value })}
                        className={`p-2 rounded-lg border text-center transition-all ${
                          createForm.security === opt.value
                            ? 'border-primary bg-primary/10'
                            : 'border-outline-variant hover:border-on-surface-variant'
                        }`}
                      >
                        <div className={`font-medium text-xs ${createForm.security === opt.value ? 'text-primary' : 'text-on-surface'}`}>
                          {opt.label}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Password for WPA2-PSK or WEP */}
                {(createForm.security === 'wpa2-psk' || createForm.security === 'wep') && (
                  <div className="mb-4">
                    <label className="label">{createForm.security === 'wep' ? 'WEP Key' : 'Password'}</label>
                    <input
                      className="input"
                      type="text"
                      value={createForm.password}
                      onChange={e => setCreateForm({ ...createForm, password: e.target.value })}
                      placeholder={createForm.security === 'wep' ? '5/13 chars or 10/26 hex' : 'WiFi password'}
                      disabled={createForm.use_wrong_password}
                    />
                  </div>
                )}

                {/* EAP credentials for WPA2-Enterprise */}
                {createForm.security === 'wpa2-enterprise' && (
                  <>
                    <div className="mb-4">
                      <label className="label">EAP Identity (Username)</label>
                      <input
                        className="input"
                        type="text"
                        value={createForm.eap_identity}
                        onChange={e => setCreateForm({ ...createForm, eap_identity: e.target.value })}
                        placeholder="e.g. employee@corp.local"
                        disabled={createForm.use_wrong_password}
                      />
                    </div>
                    <div className="mb-4">
                      <label className="label">EAP Password</label>
                      <input
                        className="input"
                        type="text"
                        value={createForm.eap_password}
                        onChange={e => setCreateForm({ ...createForm, eap_password: e.target.value })}
                        placeholder="Password"
                        disabled={createForm.use_wrong_password}
                      />
                    </div>
                    {/* Show default RADIUS test users */}
                    <div className="p-3 mb-4 rounded-lg bg-primary/5 border border-primary/20">
                      <div className="text-label-sm text-primary font-mono mb-2">RADIUS Test Users:</div>
                      <div className="text-label-sm text-on-surface-variant font-mono space-y-1">
                        <div>employee@corp.local / Welcome123</div>
                        <div>admin@corp.local / Admin@123</div>
                        <div>guest / guest123</div>
                      </div>
                    </div>
                  </>
                )}

                {/* Wrong password toggle */}
                {createForm.security !== 'open' && (
                  <div className="mb-4 p-3 rounded-lg bg-tertiary/5 border border-tertiary/20">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={createForm.use_wrong_password}
                        onChange={e => setCreateForm({ ...createForm, use_wrong_password: e.target.checked })}
                        className="w-4 h-4"
                        style={{ accentColor: 'var(--tertiary)' }}
                      />
                      <div>
                        <span className="text-sm text-tertiary font-medium">Use Wrong Password</span>
                        <div className="text-label-sm text-on-surface-variant">
                          Test failed authentication handshake capture
                        </div>
                      </div>
                    </label>
                  </div>
                )}

                {/* Client persona */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="label">Persona Name</label>
                    <input
                      className="input"
                      type="text"
                      value={createForm.persona}
                      onChange={e => setCreateForm({ ...createForm, persona: e.target.value })}
                      placeholder="e.g. John's Laptop"
                    />
                  </div>
                  <div>
                    <label className="label">Device Type</label>
                    <select
                      className="input"
                      value={createForm.device_type}
                      onChange={e => setCreateForm({ ...createForm, device_type: e.target.value })}
                    >
                      <option value="laptop">Laptop</option>
                      <option value="smartphone">Smartphone</option>
                      <option value="tablet">Tablet</option>
                      <option value="iot">IoT Device</option>
                      <option value="server">Server</option>
                    </select>
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowCreateClient(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={creating || !createForm.ssid}>
                  {creating ? (
                    <>
                      <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>sync</span>
                      Connecting...
                    </>
                  ) : (
                    <>
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>wifi</span>
                      Connect Client
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function ClientCard({ client, toggling, onToggleTraffic, onSetCreds, onAction }) {
  const deviceIcons = {
    laptop: 'laptop_mac',
    macbook: 'laptop_mac',
    smartphone: 'smartphone',
    tablet: 'tablet_mac',
    server: 'dns',
    iot: 'settings_remote',
  }
  const icon = deviceIcons[client.device_type] || 'devices'
  const hasCreds = !!client.credentials
  const state = client.connection_state || (client.ip_address ? 'connected' : 'unknown')
  const stateOk = state === 'connected'
  const stateWarn = ['associated_no_ip', 'authenticating', '4way_handshake', 'scanning', 'associating'].includes(state)

  return (
    <div className="card p-4 animate-fade-in">
      <div className="flex items-center gap-4">
        {/* Device Icon */}
        <div className="w-11 h-11 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: 24 }}>{icon}</span>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-on-surface">{client.persona || client.id}</span>
            {client.hostname && (
              <span className="text-label-sm text-on-surface-variant font-mono">{client.hostname}</span>
            )}
            {client.device_type && (
              <span className="badge badge-muted">{client.device_type}</span>
            )}
            {client.traffic_running && (
              <span className="flex items-center gap-1 text-secondary text-label-md animate-pulse">
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>play_arrow</span>
                traffic
              </span>
            )}
            <span className={`badge ${stateOk ? 'badge-secondary' : stateWarn ? 'badge-warning' : 'badge-tertiary'}`}>
              {state.replaceAll('_', ' ')}
            </span>
          </div>
          <div className="flex items-center gap-4 text-label-md font-mono">
            <span className="text-on-surface-variant">{client.mac_address}</span>
            <span className="text-primary">{client.ip_address || 'no ip'}</span>
            <span className="text-on-surface-variant">{client.interface}</span>
            {client.traffic_count > 0 && (
              <span className="text-on-surface-variant">{client.traffic_count} pkts</span>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Traffic Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-label-md text-on-surface-variant">Traffic</span>
            <button
              onClick={onToggleTraffic}
              disabled={toggling}
              className={`w-10 h-5 rounded-full transition-all relative ${
                client.traffic_running ? 'bg-secondary' : 'bg-surface-container'
              }`}
            >
              <div className={`absolute w-4 h-4 rounded-full bg-on-surface top-0.5 transition-all ${
                client.traffic_running ? 'left-5' : 'left-0.5'
              }`} />
            </button>
          </div>

          <div className="w-px h-6 bg-outline-variant" />

          <button className="btn btn-ghost btn-sm" onClick={onSetCreds}>
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>key</span>
            {hasCreds ? 'Update' : 'Creds'}
          </button>

          <button className="btn btn-ghost btn-sm" onClick={() => onAction(client.id, 'reconnect')}>
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>refresh</span>
          </button>

          <button className="btn btn-ghost btn-sm" onClick={() => onAction(client.id, 'browse_url', { url: 'http://example.com' })}>
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>language</span>
          </button>

          <Link to={`/clients/${client.id}`} className="btn btn-primary btn-sm">
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>open_in_new</span>
            Details
          </Link>
        </div>
      </div>

      {/* Credential Display */}
      {hasCreds && (
        <div className="mt-3 p-3 rounded-lg bg-tertiary/5 border border-tertiary/20">
          <div className="flex items-center gap-2 text-tertiary text-label-md font-mono">
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>lock_open</span>
            <span className="font-medium">{client.credentials.username}</span>
            <span>:</span>
            <span className="font-medium">{client.credentials.password}</span>
            <span className="text-on-surface-variant ml-2">→ {client.credentials.url}</span>
          </div>
        </div>
      )}

      {/* EAP Identity for WPA2-Enterprise */}
      {client.eap_identity && (
        <div className="mt-3 p-3 rounded-lg bg-primary/5 border border-primary/20">
          <div className="flex items-center gap-2 text-primary text-label-md font-mono">
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>badge</span>
            <span className="text-on-surface-variant">EAP Identity:</span>
            <span className="font-medium">{client.eap_identity}</span>
          </div>
        </div>
      )}

      {!stateOk && client.last_error && (
        <div className="mt-3 p-3 rounded-lg bg-warning/5 border border-warning/20">
          <div className="flex items-center gap-2 text-warning text-label-md font-mono">
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>info</span>
            <span>{client.last_error}</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default Clients
