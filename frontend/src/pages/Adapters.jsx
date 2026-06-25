import React, { useState, useEffect } from 'react'
import { adapterApi } from '../services/api'

const MODE_INFO = {
  managed: { color: 'primary', icon: 'wifi', label: 'Managed', desc: 'Can connect to APs or host clients' },
  monitor: { color: 'secondary', icon: 'sensors', label: 'Monitor', desc: 'Passive capture, injection capable' },
  ap: { color: 'tertiary', icon: 'cell_tower', label: 'AP Mode', desc: 'Hosting an access point' },
}

function Adapters() {
  const [adapters, setAdapters] = useState([])
  const [error, setError] = useState(null)
  const [switching, setSwitching] = useState({})
  const [creating, setCreating] = useState(false)

  const load = async () => {
    try { setAdapters(await adapterApi.list()); setError(null) }
    catch (e) { setError(e.message) }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [])

  const switchMode = async (id, mode) => {
    setSwitching(p => ({ ...p, [id]: true }))
    setError(null)
    try { await adapterApi.setMode(id, mode); await load() }
    catch (e) { setError(e.message) }
    finally { setSwitching(p => ({ ...p, [id]: false })) }
  }

  const createAdapter = async () => {
    setCreating(true); setError(null)
    try { await adapterApi.create(); await load() }
    catch (e) { setError(e.message) }
    finally { setCreating(false) }
  }

  const deleteAdapter = async (id) => {
    if (!window.confirm('Delete this adapter? It will be permanently removed.')) return
    setError(null)
    try { await adapterApi.delete(id); await load() }
    catch (e) { setError(e.message) }
  }

  const free = adapters.filter(a => !a.in_use)
  const monCnt = adapters.filter(a => a.mode === 'monitor').length

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Virtual Adapters</h1>
          <p className="page-subtitle">
            {adapters.length} total | {free.length} available | {monCnt} monitor
          </p>
        </div>
        <button className="btn btn-primary" onClick={createAdapter} disabled={creating}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
            {creating ? 'sync' : 'add'}
          </span>
          {creating ? 'Creating...' : 'New Adapter'}
        </button>
      </div>

      {/* Info Banner */}
      <div className="card p-4 mb-6 bg-primary/5 border-primary/20">
        <div className="flex items-center gap-3 mb-3">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>info</span>
          <span className="font-medium text-on-surface">mac80211_hwsim Virtual Radios</span>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <InfoChip icon="wifi" color="primary" label="Managed" desc="Default mode - join APs or run clients" />
          <InfoChip icon="sensors" color="secondary" label="Monitor" desc="Passive sniff + frame injection" />
          <InfoChip icon="warning" color="warning" label="In Use" desc="Allocated to AP, client, or attack" />
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

      {/* Adapter Grid */}
      {adapters.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <span className="material-symbols-outlined" style={{ fontSize: 48 }}>settings_input_antenna</span>
            <div className="font-semibold text-on-surface">No Adapters</div>
            <div className="text-sm text-on-surface-variant">
              mac80211_hwsim not loaded or no radios found
            </div>
            <button className="btn btn-primary mt-2" onClick={createAdapter} disabled={creating}>
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
              Create Adapter
            </button>
          </div>
        </div>
      ) : (
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
          {adapters.map(adapter => (
            <AdapterCard
              key={adapter.id}
              adapter={adapter}
              switching={switching[adapter.id]}
              onSwitchMode={switchMode}
              onDelete={deleteAdapter}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function AdapterCard({ adapter, switching, onSwitchMode, onDelete }) {
  const modeInfo = MODE_INFO[adapter.mode] || MODE_INFO.managed
  
  const borderColors = {
    managed: adapter.in_use ? 'border-l-warning' : 'border-l-outline-variant',
    monitor: 'border-l-secondary',
    ap: 'border-l-tertiary',
  }
  
  const bgColors = {
    managed: adapter.in_use ? 'bg-warning/10' : 'bg-primary/10',
    monitor: 'bg-secondary/10',
    ap: 'bg-tertiary/10',
  }
  
  const iconColors = {
    managed: adapter.in_use ? 'text-warning' : 'text-primary',
    monitor: 'text-secondary',
    ap: 'text-tertiary',
  }

  return (
    <div className={`card p-4 border-l-2 ${borderColors[adapter.mode]} animate-fade-in`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg ${bgColors[adapter.mode]} flex items-center justify-center`}>
            <span className={`material-symbols-outlined ${iconColors[adapter.mode]}`} style={{ fontSize: 22 }}>
              {modeInfo.icon}
            </span>
          </div>
          <div>
            <div className="font-mono font-semibold text-on-surface">{adapter.interface}</div>
            <div className="text-label-sm text-on-surface-variant">{adapter.phy}</div>
          </div>
        </div>
        <span className={`badge badge-${modeInfo.color}`}>{modeInfo.label}</span>
      </div>

      {/* Info */}
      <div className="flex flex-col gap-2 mb-4">
        <div className="flex justify-between text-sm">
          <span className="text-on-surface-variant">MAC</span>
          <span className="font-mono text-label-md text-on-surface">{adapter.mac_address}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-on-surface-variant">Status</span>
          {adapter.in_use ? (
            <span className="text-warning flex items-center gap-1">
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>lock</span>
              {adapter.used_by}
            </span>
          ) : (
            <span className="text-secondary flex items-center gap-1">
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>check_circle</span>
              Available
            </span>
          )}
        </div>
      </div>

      {/* Signal Visualizer */}
      <div className="flex items-end gap-1 h-5 mb-4">
        {[4, 7, 10, 14, 18].map((h, i) => (
          <div
            key={i}
            className={`w-1 rounded-sm transition-all ${
              adapter.mode === 'monitor' 
                ? 'bg-secondary' 
                : adapter.in_use 
                  ? 'bg-warning' 
                  : i < 3 ? 'bg-primary' : 'bg-outline-variant'
            }`}
            style={{ height: h, opacity: adapter.mode === 'managed' && !adapter.in_use ? 0.5 : 1 }}
          />
        ))}
        <span className="text-label-sm text-on-surface-variant ml-2">
          {adapter.mode === 'monitor' ? 'Listening...' : adapter.in_use ? 'Active' : 'Idle'}
        </span>
      </div>

      {/* Actions */}
      {!adapter.in_use ? (
        <div className="flex gap-2">
          <button
            className={`btn btn-sm flex-1 ${adapter.mode === 'managed' ? 'btn-primary' : 'btn-ghost'}`}
            disabled={adapter.mode === 'managed' || switching}
            onClick={() => onSwitchMode(adapter.id, 'managed')}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>wifi</span>
            Managed
          </button>
          <button
            className={`btn btn-sm flex-1 ${adapter.mode === 'monitor' ? 'btn-secondary' : 'btn-ghost'}`}
            disabled={adapter.mode === 'monitor' || switching}
            onClick={() => onSwitchMode(adapter.id, 'monitor')}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
              {switching ? 'sync' : 'sensors'}
            </span>
            Monitor
          </button>
          <button className="btn btn-danger btn-sm btn-icon" onClick={() => onDelete(adapter.id)}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
          </button>
        </div>
      ) : (
        <div className="text-label-md text-on-surface-variant italic">
          Stop the process using this adapter to unlock it.
        </div>
      )}
    </div>
  )
}

function InfoChip({ icon, color, label, desc }) {
  const colorMap = {
    primary: 'text-primary bg-primary/10',
    secondary: 'text-secondary bg-secondary/10',
    warning: 'text-warning bg-warning/10',
  }
  
  return (
    <div className="flex items-center gap-3">
      <div className={`w-8 h-8 rounded-lg ${colorMap[color]} flex items-center justify-center`}>
        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{icon}</span>
      </div>
      <div>
        <div className="font-medium text-sm text-on-surface">{label}</div>
        <div className="text-label-sm text-on-surface-variant">{desc}</div>
      </div>
    </div>
  )
}

export default Adapters
