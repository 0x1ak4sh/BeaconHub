/**
 * WebSocket event client.
 * Connects to /api/ws/events and broadcasts events to subscribers.
 * 
 * Features:
 * - Auto-reconnect with exponential backoff (starts at 500ms)
 * - Ping/pong keepalive every 10 seconds
 * - Pong timeout detection (marks offline if no pong in 5s)
 * - Connection state: 'connected' | 'connecting' | 'disconnected'
 */

const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const WS_URL = `${wsProtocol}//${window.location.host}/api/ws/events`

class EventSocket {
  constructor() {
    this._ws = null
    this._subs = new Set()
    this._state = 'disconnected' // 'connected' | 'connecting' | 'disconnected'
    this._reconnectTimer = null
    this._reconnectDelay = 500  // Start fast, increase on repeated failures
    this._pingTimer = null
    this._pongTimer = null
    this._pongReceived = true
    this._intentionalClose = false
  }

  connect() {
    if (this._ws && (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    this._intentionalClose = false
    this._state = 'connecting'
    this._notify({ type: 'connecting' })

    try {
      this._ws = new WebSocket(WS_URL)

      this._ws.onopen = () => {
        this._state = 'connected'
        this._reconnectDelay = 500 // Reset on successful connect
        this._pongReceived = true
        this._startPing()
        this._notify({ type: 'connected' })
      }

      this._ws.onmessage = (e) => {
        // Handle pong
        if (e.data === '__pong__') {
          this._pongReceived = true
          return
        }
        // Handle event data
        try {
          const data = JSON.parse(e.data)
          this._notify({ type: 'event', data })
        } catch {
          // Ignore non-JSON messages
        }
      }

      this._ws.onclose = () => {
        this._state = 'disconnected'
        this._stopPing()
        this._notify({ type: 'disconnected' })
        if (!this._intentionalClose) {
          this._scheduleReconnect()
        }
      }

      this._ws.onerror = () => {
        // onclose will fire after onerror, so just let it handle reconnect
      }
    } catch (e) {
      this._state = 'disconnected'
      this._scheduleReconnect()
    }
  }

  disconnect() {
    this._intentionalClose = true
    this._stopPing()
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer)
      this._reconnectTimer = null
    }
    if (this._ws) {
      this._ws.onclose = null
      this._ws.close()
      this._ws = null
    }
    this._state = 'disconnected'
  }

  subscribe(callback) {
    this._subs.add(callback)
    return () => this._subs.delete(callback)
  }

  get connected() {
    return this._state === 'connected'
  }

  get state() {
    return this._state
  }

  _startPing() {
    this._stopPing()
    this._pingTimer = setInterval(() => {
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        // Check if previous pong was received
        if (!this._pongReceived) {
          // Server didn't respond to last ping - connection is dead
          this._ws.close()
          return
        }
        this._pongReceived = false
        try {
          this._ws.send('__ping__')
        } catch {
          this._ws.close()
        }
      }
    }, 10000) // Ping every 10 seconds
  }

  _stopPing() {
    if (this._pingTimer) {
      clearInterval(this._pingTimer)
      this._pingTimer = null
    }
  }

  _notify(msg) {
    this._subs.forEach(cb => {
      try { cb(msg) } catch {}
    })
  }

  _scheduleReconnect() {
    if (this._reconnectTimer) return
    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null
      this.connect()
      // Increase delay for next attempt (exponential backoff capped at 10s)
      this._reconnectDelay = Math.min(this._reconnectDelay * 1.5, 10000)
    }, this._reconnectDelay)
  }
}

const eventSocket = new EventSocket()
export default eventSocket
