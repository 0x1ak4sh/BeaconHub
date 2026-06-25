import React, { useState, useEffect } from 'react'
import { attackApi, apApi, adapterApi } from '../services/api'

const ATTACK_TYPES = [
  {
    id: 'deauth',
    name: 'Deauthentication',
    tool: 'aireplay-ng',
    description: 'Send deauth frames to disconnect clients from target AP. Requires monitor mode adapter.',
    needs_monitor: true,
  },
  {
    id: 'capture_handshake',
    name: 'Handshake Capture',
    tool: 'airodump-ng',
    description: 'Capture WPA 4-way handshake for offline cracking. Combine with deauth to force reconnection.',
    needs_monitor: true,
  },
]

function Attacks() {
  const [attacks, setAttacks] = useState([])
  const [aps, setAps] = useState([])
  const [adapters, setAdapters] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [launching, setLaunching] = useState(false)
  const [error, setError] = useState(null)
  const [selectedLog, setSelectedLog] = useState(null)
  const [logContent, setLogContent] = useState('')

  const [form, setForm] = useState({
    attack_type: 'deauth',
    target_ap_id: '',
    adapter_id: '',
    duration: 30,
  })

  const load = async () => {
    try {
      const [a, ap, ad] = await Promise.all([attackApi.list(), apApi.list(), adapterApi.list()])
      setAttacks(a); setAps(ap); setAdapters(ad); setError(null)
    } catch (e) { setError(e.message) }
  }

  useEffect(() => { load(); const i = setInterval(load, 3000); return () => clearInterval(i) }, [])

  const handleLaunch = async (e) => {
    e.preventDefault()
    setLaunching(true); setError(null)
    try {
      await attackApi.launch(form)
      setShowForm(false)
      setForm({ attack_type: 'deauth', target_ap_id: '', adapter_id: '', duration: 30 })
      await load()
    } catch (e) { setError(e.message) }
    finally { setLaunching(false) }
  }

  const handleStop = async (id) => {
    try { await attackApi.stop(id); await load() }
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
      alert(data.message)
    } catch (e) { alert(e.message) }
  }

  const monitorAdapters = adapters.filter(a => a.mode === 'monitor' && !a.in_use)
  const runningAPs = aps.filter(a => a.status === 'running')
  const selectedAttackType = ATTACK_TYPES.find(t => t.id === form.attack_type)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-sm text-neutral-300">attacks</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="text-xs px-3 py-1.5 border border-neutral-700 text-neutral-300 hover:border-red-500 hover:text-red-400 transition-colors"
        >
          + new attack
        </button>
      </div>

      {error && <div className="text-xs text-red-400 border border-red-900/50 bg-red-950/20 px-3 py-2">{error}</div>}

      {/* Attack Generator Form */}
      {showForm && (
        <form onSubmit={handleLaunch} className="border border-neutral-800 bg-[#0d0d0d] p-4 space-y-4">
          <div className="text-xs text-neutral-500">configure attack</div>

          {/* Attack type selection */}
          <div className="space-y-2">
            {ATTACK_TYPES.map(type => (
              <label
                key={type.id}
                className={`flex items-start gap-3 p-3 border cursor-pointer transition-colors ${
                  form.attack_type === type.id
                    ? 'border-red-500/50 bg-red-950/10'
                    : 'border-neutral-800 hover:border-neutral-700'
                }`}
              >
                <input
                  type="radio" name="attack_type" value={type.id}
                  checked={form.attack_type === type.id}
                  onChange={e => setForm({...form, attack_type: e.target.value})}
                  className="mt-0.5 accent-red-500"
                />
                <div>
                  <div className="text-xs text-neutral-200">
                    {type.name}
                    <span className="text-neutral-600 ml-2">[{type.tool}]</span>
                  </div>
                  <div className="text-[11px] text-neutral-500 mt-0.5">{type.description}</div>
                </div>
              </label>
            ))}
          </div>

          {/* Config fields */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="target access point">
              <select required value={form.target_ap_id} onChange={e => setForm({...form, target_ap_id: e.target.value})} className="input">
                <option value="">select target...</option>
                {runningAPs.map(ap => (
                  <option key={ap.id} value={ap.id}>{ap.ssid} ({ap.bssid || ap.interface})</option>
                ))}
              </select>
              {runningAPs.length === 0 && (
                <div className="text-[10px] text-amber-500 mt-1">no running APs — create one first</div>
              )}
            </Field>

            <Field label="adapter (monitor mode)">
              <select required value={form.adapter_id} onChange={e => setForm({...form, adapter_id: e.target.value})} className="input">
                <option value="">select adapter...</option>
                {monitorAdapters.map(a => (
                  <option key={a.id} value={a.id}>{a.interface} ({a.mac_address})</option>
                ))}
              </select>
              {monitorAdapters.length === 0 && (
                <div className="text-[10px] text-amber-500 mt-1">no monitor adapters — switch one in adapters tab</div>
              )}
            </Field>

            <Field label="duration (seconds)">
              <input
                type="number" min={5} max={300} value={form.duration}
                onChange={e => setForm({...form, duration: parseInt(e.target.value)})}
                className="input"
              />
            </Field>
          </div>

          {/* Command preview */}
          {selectedAttackType && form.target_ap_id && form.adapter_id && (
            <div className="bg-black border border-neutral-800 p-3 text-xs">
              <span className="text-neutral-500">$ </span>
              <span className="text-[#00ff41]">
                {form.attack_type === 'deauth' && `aireplay-ng --deauth ${form.duration * 10} -a [TARGET_BSSID] [ADAPTER]`}
                {form.attack_type === 'capture_handshake' && `airodump-ng --bssid [TARGET_BSSID] --write capture [ADAPTER]`}
              </span>
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={launching || !form.target_ap_id || !form.adapter_id}
              className="text-xs px-3 py-1.5 bg-red-600 text-white font-medium hover:bg-red-500 disabled:opacity-40 transition-colors"
            >
              {launching ? 'launching...' : 'execute'}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="text-xs px-3 py-1.5 text-neutral-400 hover:text-neutral-200">
              cancel
            </button>
          </div>
        </form>
      )}

      {/* Running/completed attacks */}
      {attacks.length === 0 ? (
        <div className="border border-neutral-800 bg-[#0d0d0d] p-8 text-center text-xs text-neutral-600">
          no attacks executed
        </div>
      ) : (
        <div className="space-y-2">
          {attacks.map(attack => (
            <div key={attack.id} className="border border-neutral-800 bg-[#0d0d0d]">
              <div className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-4">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    attack.status === 'running' ? 'bg-red-500 animate-pulse' :
                    attack.status === 'completed' ? 'bg-[#00ff41]' : 'bg-neutral-600'
                  }`} />
                  <div>
                    <span className="text-xs text-neutral-200">
                      {attack.attack_type === 'deauth' ? 'deauth' : 'capture'}
                    </span>
                    <span className="text-xs text-neutral-600 ml-3">
                      target: {attack.target_ap_id}
                    </span>
                    <span className="text-xs text-neutral-600 ml-3">
                      {new Date(attack.started_at).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => viewLog(attack.id)} className="text-xs text-neutral-500 hover:text-neutral-300 px-2 py-1 border border-neutral-800 hover:border-neutral-700">
                    log
                  </button>
                  {attack.attack_type === 'capture_handshake' && attack.status !== 'running' && (
                    <button onClick={() => checkHandshake(attack.id)} className="text-xs text-[#00ff41] hover:text-[#00cc33] px-2 py-1 border border-[#00ff41]/30 hover:border-[#00ff41]">
                      check handshake
                    </button>
                  )}
                  {attack.status === 'running' && (
                    <button onClick={() => handleStop(attack.id)} className="text-xs text-red-400 hover:text-red-300 px-2 py-1 border border-red-900/50 hover:border-red-700">
                      stop
                    </button>
                  )}
                  <span className={`text-xs px-2 py-0.5 ${
                    attack.status === 'running' ? 'text-red-400' :
                    attack.status === 'completed' ? 'text-[#00ff41]' : 'text-neutral-500'
                  }`}>
                    {attack.status}
                  </span>
                </div>
              </div>
              {selectedLog === attack.id && (
                <div className="border-t border-neutral-800 bg-black p-3 text-xs text-neutral-400 max-h-32 overflow-y-auto whitespace-pre-wrap font-mono">
                  {logContent}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[10px] text-neutral-500 uppercase tracking-wider mb-1">{label}</label>
      {children}
    </div>
  )
}

export default Attacks
