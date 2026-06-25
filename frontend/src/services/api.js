/**
 * BeaconHub API service
 */

const BASE = '/api'

async function req(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

const get   = (path)        => req('GET',    path)
const post  = (path, body)  => req('POST',   path, body)
const del   = (path)        => req('DELETE', path)
const put   = (path, body)  => req('PUT',    path, body)
const patch = (path, body)  => req('PATCH',  path, body)


// ── System ──────────────────────────────────────────────────────────────
export const systemApi = {
  health: ()      => get('/health'),
  status: ()      => get('/status'),
  reset:  ()      => post('/reset'),
  logs:   (n=50)  => get(`/logs?count=${n}`),
}


// ── Access Points ─────────────────────────────────────────────────────
export const apApi = {
  list:    ()          => get('/ap'),
  get:     (id)        => get(`/ap/${id}`),
  create:  (body)      => post('/ap', body),
  stop:    (id)        => del(`/ap/${id}`),
  clients: (id)        => get(`/ap/${id}/clients`),
  log:     (id)        => get(`/ap/${id}/log`),
  
  /** Update AP settings (password, hidden, channel) */
  update:  (id, body)  => patch(`/ap/${id}`, body),
  
  /** Start aggressive traffic flood on all clients (for WEP IV generation) */
  floodTraffic: (id)   => post(`/ap/${id}/flood-traffic`),
  
  /** Stop traffic flood */
  stopFlood: (id)      => post(`/ap/${id}/stop-flood`),
  
  /** Get WEP IV generation status */
  wepStatus: (id)      => get(`/ap/${id}/wep-status`),

  /** Force beacon re-broadcast (useful for hidden SSIDs) */
  beacon: (id)         => post(`/ap/${id}/beacon`),
}


// ── Adapters ──────────────────────────────────────────────────────────
export const adapterApi = {
  list:    ()           => get('/adapters'),
  get:     (id)         => get(`/adapters/${id}`),
  create:  ()           => post('/adapters'),
  delete:  (id)         => del(`/adapters/${id}`),
  setMode: (id, mode)   => post(`/adapters/${id}/mode`, { mode }),
}


// ── Clients ───────────────────────────────────────────────────────────
export const clientApi = {
  /** List all clients across all APs */
  listAll: ()           => get('/clients'),

  /** Get a single client's full details */
  detail:  (id)         => get(`/clients/${id}`),

  /**
   * Create a standalone client that connects to any WiFi.
   * @param {Object} body - { ssid, security, password, ap_id, persona, device_type, hostname, eap_identity, eap_password }
   */
  create: (body)        => post('/clients', body),

  /** Delete/disconnect a client */
  delete: (id)          => del(`/clients/${id}`),

  /** Start continuous background traffic (aggressive=true for WEP IV generation) */
  startTraffic: (id, intervalSeconds = 10, aggressive = false) =>
    post(`/clients/${id}/traffic/start`, { interval_seconds: intervalSeconds, traffic_types: ['dns', 'ping', 'browse'], aggressive }),

  /** Stop background traffic */
  stopTraffic:  (id)    => post(`/clients/${id}/traffic/stop`),

  /**
   * Set credentials (username / password / url can be fake).
   * If submit_and_reconnect is true: submits via HTTP POST + reconnects.
   */
  setCredentials: (id, { username, password, target_url, submit_and_reconnect = true }) =>
    post(`/clients/${id}/credentials`, { username, password, target_url, submit_and_reconnect }),

  /**
   * Trigger a one-off action.
   * action: 'reconnect' | 'browse_url' | 'submit_credentials' | 'open_captive' | 'dns_lookup'
   * extra: { url, username, password }
   */
  action: (id, body)    => post(`/clients/${id}/action`, body),
}


// ── Scenarios ─────────────────────────────────────────────────────────
export const scenarioApi = {
  /** List all available scenarios */
  list:       ()              => get('/scenarios'),

  /** Get scenario details */
  get:        (id)            => get(`/scenarios/${id}`),

  /** Deploy a scenario */
  deploy:     (id)            => post(`/scenarios/${id}/deploy`),

  /** Stop a running scenario */
  stop:       (id)            => post(`/scenarios/${id}/stop`),

  /** Mark an objective as completed */
  completeObjective: (scenarioId, objId) =>
    post(`/scenarios/${scenarioId}/objectives/${objId}/complete`),

  /** Get global scoreboard */
  scoreboard: ()              => get('/scenarios/scoreboard'),
}


// ── Attacks ───────────────────────────────────────────────────────────
export const attackApi = {
  /** List available attack types */
  types:      ()              => get('/attacks/types'),

  /** List running attacks */
  list:       ()              => get('/attacks'),

  /** Start an attack */
  start:      (body)          => post('/attacks', body),
  launch:     (body)          => post('/attacks', body),

  /** Stop an attack */
  stop:       (id)            => post(`/attacks/${id}/stop`),
  delete:     (id)            => del(`/attacks/${id}`),

  /** Get attack status */
  status:     (id)            => get(`/attacks/${id}`),

  /** Read attack process output */
  log:        (id)            => get(`/attacks/${id}/log`),

  /** Check capture for a WPA handshake */
  checkHandshake: (id)        => get(`/attacks/${id}/check-handshake`),
}


// ── Packet Capture ────────────────────────────────────────────────────
export const captureApi = {
  /** Start packet capture on an interface */
  start:   (interface_name)    => post('/capture/start', { interface: interface_name }),

  /** Stop capture and get results */
  stop:    (id)                => post(`/capture/${id}/stop`),

  /** Get capture status and detected data */
  status:  (id)                => get(`/capture/${id}`),

  /** List all captures */
  list:    ()                  => get('/capture'),

  /** Get capture for a specific interface */
  forInterface: (iface)        => get(`/capture/interface/${iface}`),
}
