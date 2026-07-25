import React, { useState, useEffect } from 'react'
import { scenarioApi } from '../services/api'

const DIFFICULTY_COLORS = {
  beginner: { badge: 'badge-secondary', text: 'text-secondary' },
  intermediate: { badge: 'badge-warning', text: 'text-warning' },
  advanced: { badge: 'badge-tertiary', text: 'text-tertiary' },
}

function Scenarios() {
  const [scenarios, setScenarios] = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [scoreboard, setScoreboard] = useState(null)
  const [deploying, setDeploying] = useState(false)
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      const [s, sb] = await Promise.all([scenarioApi.list(), scenarioApi.scoreboard()])
      setScenarios(s); setScoreboard(sb); setError(null)
    } catch (e) { setError(e.message) }
  }

  useEffect(() => { load(); const i = setInterval(load, 5000); return () => clearInterval(i) }, [])

  const loadDetail = async (id) => {
    try {
      const d = await scenarioApi.get(id)
      setDetail(d); setSelected(id)
    } catch (e) { setError(e.message) }
  }

  const deploy = async (id) => {
    setDeploying(true); setError(null)
    try {
      await scenarioApi.deploy(id)
      await loadDetail(id); await load()
    } catch (e) { setError(e.message) }
    finally { setDeploying(false) }
  }

  const stop = async (id) => {
    try { await scenarioApi.stop(id); setDetail(null); setSelected(null); await load() }
    catch (e) { setError(e.message) }
  }

  const completeObj = async (scenarioId, objId) => {
    try { await scenarioApi.completeObjective(scenarioId, objId); await loadDetail(scenarioId); await load() }
    catch (e) { setError(e.message) }
  }

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Scenarios</h1>
          <p className="page-subtitle">Pre-configured attack training environments</p>
        </div>
        {scoreboard && (
          <div className="flex items-center gap-4">
            <div className="card p-3 flex items-center gap-3">
              <span className="material-symbols-outlined text-secondary" style={{ fontSize: 24 }}>emoji_events</span>
              <div>
                <div className="text-xl font-bold text-secondary">{scoreboard.total_points}<span className="text-on-surface-variant">/{scoreboard.max_points}</span></div>
                <div className="text-label-sm text-on-surface-variant font-mono">TOTAL POINTS</div>
              </div>
            </div>
            <div className="card p-3 flex items-center gap-3">
              <span className="material-symbols-outlined text-primary" style={{ fontSize: 24 }}>check_circle</span>
              <div>
                <div className="text-xl font-bold text-primary">{scoreboard.scenarios_completed}<span className="text-on-surface-variant">/{scoreboard.scenarios_total}</span></div>
                <div className="text-label-sm text-on-surface-variant font-mono">COMPLETED</div>
              </div>
            </div>
          </div>
        )}
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

      {/* Main Content */}
      <div className="flex gap-6">
        {/* Scenario List - Bento Grid */}
        <div className="w-80 flex-shrink-0">
          <div className="text-label-md text-on-surface-variant font-mono uppercase mb-3">Available Scenarios</div>
          <div className="flex flex-col gap-2">
            {scenarios.map(s => (
              <ScenarioCard
                key={s.id}
                scenario={s}
                selected={selected === s.id}
                onClick={() => loadDetail(s.id)}
              />
            ))}
          </div>
        </div>

        {/* Detail Panel */}
        <div className="flex-1 min-w-0">
          {!detail ? (
            <div className="card">
              <div className="empty-state">
                <span className="material-symbols-outlined" style={{ fontSize: 48 }}>science</span>
                <div className="font-semibold text-on-surface">Select a Scenario</div>
                <div className="text-sm text-on-surface-variant">
                  Choose a scenario from the list to view details and deploy
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {/* Scenario Header */}
              <div className="card p-5">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-xl font-bold text-on-surface mb-2">{detail.name}</h2>
                    <div className="flex items-center gap-3">
                      <span className={`badge ${DIFFICULTY_COLORS[detail.difficulty]?.badge}`}>
                        {detail.difficulty}
                      </span>
                      <span className="badge badge-muted">{detail.category}</span>
                      <span className="text-label-md text-primary font-mono">{detail.points_total} PTS</span>
                    </div>
                  </div>
                  {detail.status === 'available' && (
                    <button
                      onClick={() => deploy(detail.id)}
                      disabled={deploying}
                      className="btn btn-secondary"
                    >
                      {deploying ? (
                        <>
                          <span className="material-symbols-outlined animate-spin" style={{ fontSize: 16 }}>sync</span>
                          Deploying...
                        </>
                      ) : (
                        <>
                          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>rocket_launch</span>
                          Deploy Scenario
                        </>
                      )}
                    </button>
                  )}
                  {detail.status === 'active' && (
                    <button onClick={() => stop(detail.id)} className="btn btn-danger">
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>stop</span>
                      Stop
                    </button>
                  )}
                </div>
                <p className="text-sm text-on-surface-variant leading-relaxed">{detail.description}</p>
              </div>

              {/* Attack Flow */}
              <div className="card p-5">
                <div className="text-label-md text-on-surface-variant font-mono uppercase mb-4">Attack Flow</div>
                <div className="flex flex-col">
                  {detail.attack_flow.map((step, i) => (
                    <div key={i} className="flex items-start gap-4">
                      <div className="flex flex-col items-center">
                        <div className="w-3 h-3 rounded-full bg-primary flex items-center justify-center">
                          <div className="w-1.5 h-1.5 rounded-full bg-surface" />
                        </div>
                        {i < detail.attack_flow.length - 1 && (
                          <div className="w-px h-8 bg-outline-variant" />
                        )}
                      </div>
                      <div className="text-sm text-on-surface-variant pb-4">{step}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Objectives */}
              <div className="card p-5">
                <div className="text-label-md text-on-surface-variant font-mono uppercase mb-4">Objectives</div>
                <div className="flex flex-col gap-2">
                  {detail.objectives.map(obj => (
                    <div
                      key={obj.id}
                      className={`p-4 rounded-lg border transition-all ${
                        obj.status === 'completed'
                          ? 'bg-secondary/5 border-secondary/30'
                          : 'bg-surface-container border-outline-variant'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`w-6 h-6 rounded flex items-center justify-center flex-shrink-0 ${
                          obj.status === 'completed' ? 'bg-secondary/20' : 'bg-surface-container-high'
                        }`}>
                          <span className={`material-symbols-outlined ${obj.status === 'completed' ? 'text-secondary' : 'text-on-surface-variant'}`} style={{ fontSize: 16 }}>
                            {obj.status === 'completed' ? 'check' : 'radio_button_unchecked'}
                          </span>
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-1">
                            <span className={`font-medium text-sm ${obj.status === 'completed' ? 'text-secondary' : 'text-on-surface'}`}>
                              {obj.title}
                            </span>
                            <span className="text-label-md text-primary font-mono">+{obj.points}</span>
                          </div>
                          <p className="text-label-md text-on-surface-variant">{obj.description}</p>
                          {obj.hint && obj.status !== 'completed' && (
                            <div className="flex items-center gap-2 mt-2 text-warning text-label-md">
                              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>lightbulb</span>
                              {obj.hint}
                            </div>
                          )}
                        </div>
                        {detail.status === 'active' && obj.status !== 'completed' && (
                          <button
                            onClick={() => completeObj(detail.id, obj.id)}
                            className="btn btn-ghost btn-sm"
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>done</span>
                            Complete
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Personas */}
              {detail.personas.length > 0 && (
                <div className="card p-5">
                  <div className="text-label-md text-on-surface-variant font-mono uppercase mb-4">Connected Personas</div>
                  <div className="grid grid-cols-2 gap-3">
                    {detail.personas.map((p, i) => (
                      <div key={i} className="p-4 rounded-lg bg-surface-container border border-outline-variant">
                        <div className="flex items-center gap-3 mb-3">
                          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                            <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>person</span>
                          </div>
                          <div>
                            <div className="font-medium text-on-surface">{p.name}</div>
                            <div className="text-label-md text-on-surface-variant">{p.role}</div>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-label-md">
                          <div>
                            <span className="text-on-surface-variant">Device: </span>
                            <span className="text-on-surface">{p.device_type}</span>
                          </div>
                          <div>
                            <span className="text-on-surface-variant">OS: </span>
                            <span className="text-on-surface">{p.os}</span>
                          </div>
                          <div className="col-span-2">
                            <span className="text-on-surface-variant">Hostname: </span>
                            <span className="text-primary font-mono">{p.hostname}</span>
                          </div>
                          <div className="col-span-2">
                            <span className="text-on-surface-variant">Behavior: </span>
                            <span className="text-on-surface">{p.behavior}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ScenarioCard({ scenario, selected, onClick }) {
  const diffColors = DIFFICULTY_COLORS[scenario.difficulty] || DIFFICULTY_COLORS.beginner

  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-4 rounded-lg border transition-all ${
        selected
          ? 'border-primary bg-primary/5'
          : 'border-outline-variant bg-surface-container hover:border-on-surface-variant'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <span className="font-medium text-on-surface">{scenario.name}</span>
        <span className={`text-label-sm font-mono ${diffColors.text}`}>{scenario.difficulty}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-label-md text-on-surface-variant">{scenario.category}</span>
        <span className="text-label-md text-primary font-mono">{scenario.points_total} pts</span>
      </div>
      {scenario.status === 'active' && (
        <div className="flex items-center gap-1 mt-2 text-secondary text-label-md">
          <div className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
          <span>Active</span>
        </div>
      )}
    </button>
  )
}

export default Scenarios
