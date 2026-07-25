import React, { useState, useEffect, useRef } from 'react'
import { attackApi, apApi, adapterApi } from '../services/api'

const ATTACK_TYPES = [
  {
    id: 'deauth',
    name: 'Deauthentication',
    tool: 'aireplay-ng',
    icon: 'block',
    description: 'Send deauth frames to disconnect clients from target AP. Forces reconnection which generates a WPA handshake.',
    needs_monitor: true,
  },
  {
    id: 'capture_handshake',
    name: 'Handshake Capture',
    tool: 'airodump-ng',
    icon: 'radar',
    description: 'Capture WPA 4-way handshake with airodump-ng. Run deauth simultaneously to force client reconnection.',
    needs_monitor: true,
  },
  {
    id: 'pmkid_capture',
    name: 'PMKID Capture',
    tool: 'hcxdumptool',
    icon: 'key',
    description: 'Capture PMKID from AP — no client needed! Only the first EAPOL frame from the AP is required.',
    needs_monitor: true,
  },
]

function Attacks() {
  const [attacks, setAttacks] = useState([])
  const [aps, setAps] = useState([])
  const [adapters, setAdapters] = useState([])
  const [wordlists, setWordlists] = useState([])
  const [captures, setCaptures] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [showCrack, setShowCrack] = useState(false)
  const [launching, setLaunching] = useState(false)
  const [error, setError] = useState(null)
  const [selectedLog, setSelectedLog] = useState(null)
  const [logContent, setLogContent] = useState('')
  const [crackStatus, setCrackStatus] = useState({})
  const crackPollRef = useRef(null)

  const [form, setForm] = useState({
    attack_type: 'deauth',
    target_ap_id: '',
    adapter_id: '',
    duration: 30,
  })

  const [crackForm, setCrackForm] = useState({
    target_ap_id: '',
    cap_file: '',
    wordlist: '',
  })

  const load = async () => {
    try {
      const [a, ap, ad, wl, caps] = await Promise.all([
        attackApi.list(),
        apApi.list(),
        adapterApi.list(),
        attackApi.wordlists().catch(() => ({ wordlists: [] })),
        attackApi.captures().catch(() => ({ captures: [] })),
      ])
      setAttacks(a); setAps(ap); setAdapters(ad)
      setWordlists(wl.wordlists || [])
      setCaptures(caps.captures || [])
      setError(null)
    } catch (e) { setError(e.message) }
  }

  useEffect(() => {
    load()
    const i = setInterval(load, 3000)
    return () => {
      clearInterval(i)
      if (crackPollRef.current) clearInterval(crackPollRef.current)
    }
  }, [])

  // Poll crack status for any running crack attacks
  useEffect(() => {
    const runningCracks = attacks.filter(a => a.attack_type === 'crack' && a.status === 'running')
    if (runningCracks.length > 0 && !crackPollRef.current) {
      crackPollRef.current = setInterval(async () => {
        // Re-fetch attacks to get updated list
        try {
          const updated = await attackApi.list()
          const currentRunning = updated.filter(a => a.attack_type === 'crack' && a.status === 'running')
          for (const crack of currentRunning) {
            try {
              const status = await attackApi.crackStatus(crack.id)
              setCrackStatus(prev => ({ ...prev, [crack.id]: status }))
            } catch {}
          }
          if (currentRunning.length === 0 && crackPollRef.current) {
            clearInterval(crackPollRef.current)
            crackPollRef.current = null
          }
        } catch {}
      }, 2000)
    } else if (runningCracks.length === 0 && crackPollRef.current) {
      clearInterval(crackPollRef.current)
      crackPollRef.current = null
    }
  }, [attacks])

  const handleLaunch = async (e) => {
    e.preventDefault()
    setLaunching(true); setError(null)
    try {
      await attackApi.launch({
        ...form,
        duration: Number(form.duration),
      })
      setShowForm(false)
      setForm({ attack_type: 'deauth', target_ap_id: '', adapter_id: '', duration: 30 })
      await load()
    } catch (e) { setError(e.message) }
    finally { setLaunching(false) }
  }

  const handleCrack = async (e) => {
    e.preventDefault()
    setLaunching(true); setError(null)
    try {
      await attackApi.launch({
        attack_type: 'crack',
        target_ap_id: crackForm.target_ap_id,
        cap_file: crackForm.cap_file,
        wordlist: crackForm.wordlist,
        adapter_id: '',
        duration: 0,
      })
      setShowCrack(false)
      await load()
    } catch (e) { setError(e.message) }
    finally { setLaunching(false) }
  }

  const handleStop = async (id) => {
    try { await attackApi.stop(id); await load() }
    catch (e) { setError(e.message) }
  }

  const handleDelete = async (id) => {
    try { await attackApi.delete(id); await load() }
    catch (e) { setError(e.message) }
  }

  const viewLog = async (id) => {
    if (selectedLog === id) { setSelectedLog(null); return }
    try {
      const data = await attackApi.log(id)
      setLogContent(data.log || 'no output yet')
      setSelectedLog(id)
    } catch (e) { setLogContent(`error: ${e.message}`); setSelectedLog(id) }
  }

  const checkHandshake = async (id) => {
    try {
      const data = await attackApi.checkHandshake(id)
      setError(data.message)
    } catch (e) { setError(e.message) }
  }

  const monitorAdapters = adapters.filter(a => a.mode === 'monitor' && !a.in_use)
  const runningAPs = aps.filter(a => a.status === 'running')
  const selectedAttackType = ATTACK_TYPES.find(t => t.id === form.attack_type)

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Attacks</h1>
          <p className="page-subtitle">
            {attacks.length} attack{attacks.length !== 1 ? 's' : ''} | {attacks.filter(a => a.status === 'running').length} running
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-ghost" onClick={() => { setShowCrack(!showCrack); setShowForm(false) }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>key</span>
            Crack
          </button>
          <button className="btn btn-primary" onClick={() => { setShowForm(!showForm); setShowCrack(false) }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
              {showForm ? 'close' : 'add'}
            </span>
            {showForm ? 'Cancel' : 'New Attack'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 p-4 mb-4 bg-tertiary/10 border border-tertiary/30 rounded-lg">
          <span className="material-symbols-outlined text-tertiary">error</span>
          <span className="text-tertiary flex-1">{error}</span>
          <button onClick={() => setError(null)} className="text-tertiary hover:text-on-surface">
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
          </button>
        </div>
      )}

      {/* Attack Generator Form */}
      {showForm && (
        <div className="card p-5 mb-4 animate-fade-in">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>security</span>
            <span className="font-semibold text-on-surface">Configure Attack</span>
          </div>

          <form onSubmit={handleLaunch}>
            {/* Attack type selection */}
            <div className="mb-4">
              <label className="label">Attack Type</label>
              <div className="grid grid-cols-3 gap-2">
                {ATTACK_TYPES.map(type => (
                  <button
                    key={type.id}
                    type="button"
                    onClick={() => setForm({...form, attack_type: type.id})}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      form.attack_type === type.id
                        ? 'border-primary bg-primary/10'
                        : 'border-outline-variant hover:border-on-surface-variant'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="material-symbols-outlined text-tertiary" style={{ fontSize: 18 }}>{type.icon}</span>
                      <span className={`font-medium text-sm ${form.attack_type === type.id ? 'text-primary' : 'text-on-surface'}`}>
                        {type.name}
                      </span>
                    </div>
                    <div className="text-label-sm text-on-surface-variant mb-1">{type.description}</div>
                    <div className="text-label-sm text-on-surface-variant font-mono">[{type.tool}]</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Config fields */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="label">Target Access Point</label>
                <select
                  required
                  value={form.target_ap_id}
                  onChange={e => setForm({...form, target_ap_id: e.target.value})}
                  className="input"
                >
                  <option value="">Select target...</option>
                  {runningAPs.map(ap => (
                    <option key={ap.id} value={ap.id}>{ap.ssid} ({ap.bssid || ap.interface})</option>
                  ))}
                </select>
                {runningAPs.length === 0 && (
                  <div className="text-label-sm text-warning mt-1">No running APs — create one first</div>
                )}
              </div>

              <div>
                <label className="label">Adapter (Monitor Mode)</label>
                <select
                  required
                  value={form.adapter_id}
                  onChange={e => setForm({...form, adapter_id: e.target.value})}
                  className="input"
                >
                  <option value="">Select adapter...</option>
                  {monitorAdapters.map(a => (
                    <option key={a.id} value={a.id}>{a.interface} ({a.mac_address})</option>
                  ))}
                </select>
                {monitorAdapters.length === 0 && (
                  <div className="text-label-sm text-warning mt-1">No monitor adapters — switch one in Adapters tab</div>
                )}
              </div>

              <div>
                <label className="label">Duration (seconds, 0 = continuous)</label>
                <input
                  type="number"
                  min={0}
                  max={600}
                  value={form.duration}
                  onChange={e => setForm({...form, duration: parseInt(e.target.value)})}
                  className="input"
                />
              </div>
            </div>

            {/* Command preview */}
            {selectedAttackType && form.target_ap_id && form.adapter_id && (
              <div className="bg-surface-container rounded-lg p-3 mb-4 font-mono text-label-sm">
                <span className="text-on-surface-variant">$ </span>
                <span className="text-secondary">
                  {form.attack_type === 'deauth' && `aireplay-ng --deauth 0 -a [BSSID] ${monitorAdapters.find(a => a.id === form.adapter_id)?.interface || '[ADAPTER]'}`}
                  {form.attack_type === 'capture_handshake' && `airodump-ng --bssid [BSSID] --channel [CH] --write capture [ADAPTER]`}
                  {form.attack_type === 'pmkid_capture' && `hcxdumptool --device [ADAPTER] --channel [CH] --target_ap [BSSID] -o pmkid.pcapng`}
                </span>
              </div>
            )}

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={launching || !form.target_ap_id || !form.adapter_id}
                className="btn btn-danger"
              >
                {launching ? (
                  <>
                    <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>sync</span>
                    Launching...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>rocket_launch</span>
                    Execute Attack
                  </>
                )}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="btn btn-ghost">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Crack Form */}
      {showCrack && (
        <div className="card p-5 mb-4 animate-fade-in" style={{ borderColor: 'var(--secondary)' }}>
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-secondary" style={{ fontSize: 20 }}>key</span>
            <span className="font-semibold text-on-surface">Crack Capture File</span>
          </div>

          <form onSubmit={handleCrack}>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="label">Target AP (for BSSID filter)</label>
                <select
                  required
                  value={crackForm.target_ap_id}
                  onChange={e => setCrackForm({...crackForm, target_ap_id: e.target.value})}
                  className="input"
                >
                  <option value="">Select AP...</option>
                  {aps.map(ap => (
                    <option key={ap.id} value={ap.id}>{ap.ssid} ({ap.bssid || 'unknown'})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="label">Capture File</label>
                <select
                  required
                  value={crackForm.cap_file}
                  onChange={e => setCrackForm({...crackForm, cap_file: e.target.value})}
                  className="input"
                >
                  <option value="">Select capture...</option>
                  {captures.map((cap, i) => (
                    <option key={i} value={cap.path}>{cap.filename} ({cap.size_human || cap.size + 'B'})</option>
                  ))}
                </select>
                {captures.length === 0 && (
                  <div className="text-label-sm text-warning mt-1">No captures — run a handshake capture first</div>
                )}
              </div>

              <div>
                <label className="label">Wordlist</label>
                <select
                  required
                  value={crackForm.wordlist}
                  onChange={e => setCrackForm({...crackForm, wordlist: e.target.value})}
                  className="input"
                >
                  <option value="">Select wordlist...</option>
                  {wordlists.map((wl, i) => (
                    <option key={i} value={wl.path}>{wl.filename} ({wl.size_human || wl.size + 'B'})</option>
                  ))}
                </select>
                {wordlists.length === 0 && (
                  <div className="text-label-sm text-warning mt-1">No wordlists found in /opt/tools/wordlists/</div>
                )}
              </div>
            </div>

            <div className="bg-surface-container rounded-lg p-3 mb-4 font-mono text-label-sm">
              <span className="text-on-surface-variant">$ </span>
              <span className="text-secondary">
                aircrack-ng -w [wordlist] [capture.cap]
              </span>
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={launching || !crackForm.cap_file || !crackForm.wordlist || !crackForm.target_ap_id}
                className="btn btn-secondary"
              >
                {launching ? (
                  <>
                    <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>sync</span>
                    Starting...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>vpn_key</span>
                    Start Cracking
                  </>
                )}
              </button>
              <button type="button" onClick={() => setShowCrack(false)} className="btn btn-ghost">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Running/completed attacks */}
      {attacks.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <span className="material-symbols-outlined" style={{ fontSize: 48 }}>security</span>
            <div className="font-semibold text-on-surface">No Attacks Executed</div>
            <div className="text-sm text-on-surface-variant max-w-xs">
              Launch a deauth, handshake capture, PMKID capture, or crack a captured handshake.
            </div>
            <button className="btn btn-primary mt-2" onClick={() => setShowForm(true)}>
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
              New Attack
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {attacks.map(attack => (
            <AttackCard
              key={attack.id}
              attack={attack}
              crackStatus={crackStatus[attack.id]}
              selectedLog={selectedLog}
              logContent={logContent}
              onToggleLog={() => viewLog(attack.id)}
              onStop={() => handleStop(attack.id)}
              onDelete={() => handleDelete(attack.id)}
              onCheckHandshake={() => checkHandshake(attack.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function AttackCard({ attack, crackStatus, selectedLog, logContent, onToggleLog, onStop, onDelete, onCheckHandshake }) {
  const isRunning = attack.status === 'running'
  const isCrack = attack.attack_type === 'crack'
  const isCracked = attack.status === 'cracked'
  const statusColors = {
    running: 'badge-warning',
    completed: 'badge-secondary',
    stopped: 'badge-muted',
    starting: 'badge-warning',
    failed: 'badge-tertiary',
    cracked: 'badge-secondary',
  }
  const dotColors = {
    running: 'status-dot-warning',
    completed: 'bg-secondary',
    stopped: 'bg-on-surface-variant',
    starting: 'status-dot-warning',
    failed: 'status-dot-error',
    cracked: 'status-dot-active',
  }

  const attackTypeLabels = {
    deauth: 'Deauthentication',
    capture_handshake: 'Handshake Capture',
    pmkid_capture: 'PMKID Capture',
    crack: 'Cracking',
  }

  const attackIcons = {
    deauth: 'block',
    capture_handshake: 'radar',
    pmkid_capture: 'key',
    crack: 'vpn_key',
  }

  return (
    <div className={`card overflow-hidden animate-fade-in ${isCracked ? 'border-l-4 border-l-secondary' : ''}`}>
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-4">
          {/* Status indicator */}
          <div className="relative">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              isCracked ? 'bg-secondary/20' : 'bg-surface-container'
            }`}>
              <span className={`material-symbols-outlined ${isCracked ? 'text-secondary' : 'text-tertiary'}`} style={{ fontSize: 22 }}>
                {attackIcons[attack.attack_type] || 'security'}
              </span>
            </div>
            <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-surface ${
              isRunning ? 'status-dot-warning animate-pulse' : dotColors[attack.status] || 'bg-tertiary'
            }`} />
          </div>

          {/* Info */}
          <div>
            <div className="flex items-center gap-3">
              <span className="font-semibold text-on-surface">
                {attackTypeLabels[attack.attack_type] || attack.attack_type}
              </span>
              <span className={`badge ${statusColors[attack.status] || 'badge-muted'}`}>
                {attack.status}
              </span>
              {isCracked && attack.result && (
                <span className="badge badge-secondary font-mono">
                  KEY: {attack.result}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-label-md text-on-surface-variant font-mono">
                target: {attack.target_ap_id}
              </span>
              <span className="text-label-md text-on-surface-variant">
                {new Date(attack.started_at).toLocaleTimeString()}
              </span>
              {attack.stopped_at && (
                <span className="text-label-md text-on-surface-variant">
                  → {new Date(attack.stopped_at).toLocaleTimeString()}
                </span>
              )}
              {attack.output_file && (
                <span className="text-label-md text-on-surface-variant font-mono truncate" style={{ maxWidth: 200 }}>
                  {attack.output_file.split('/').pop()}
                </span>
              )}
            </div>

            {/* Crack progress */}
            {isCrack && crackStatus && crackStatus.status === 'running' && (
              <div className="mt-2">
                <div className="text-label-sm text-on-surface-variant font-mono mb-1">
                  {crackStatus.message || 'Testing keys...'}
                </div>
                {crackStatus.total > 0 && (
                  <div className="progress-bar" style={{ height: 4 }}>
                    <div
                      className="progress-fill"
                      style={{
                        width: `${Math.min(100, (crackStatus.tested / crackStatus.total) * 100)}%`,
                        background: 'var(--secondary)',
                      }}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleLog}
            className="btn btn-ghost btn-sm"
            title="View log"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>terminal</span>
            Log
          </button>
          {(attack.attack_type === 'capture_handshake' || attack.attack_type === 'pmkid_capture') && !isRunning && (
            <button
              onClick={onCheckHandshake}
              className="btn btn-sm"
              style={{
                background: 'rgba(78,222,163,0.15)',
                color: 'var(--secondary)',
                border: '1px solid rgba(78,222,163,0.3)'
              }}
              title="Check if handshake/PMKID was captured"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>check_circle</span>
              Check
            </button>
          )}
          {isRunning && (
            <button onClick={onStop} className="btn btn-danger btn-sm">
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>stop</span>
              Stop
            </button>
          )}
          {!isRunning && (
            <button onClick={onDelete} className="btn btn-ghost btn-sm" title="Delete">
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>delete</span>
            </button>
          )}
        </div>
      </div>

      {/* Log output */}
      {selectedLog && (
        <div className="border-t border-outline-variant bg-surface-container p-3 max-h-40 overflow-y-auto">
          <div className="font-mono text-label-sm text-on-surface-variant whitespace-pre-wrap">
            {logContent || 'No output yet...'}
          </div>
        </div>
      )}
    </div>
  )
}

export default Attacks
