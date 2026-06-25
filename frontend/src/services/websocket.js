/**
 * WebSocket event client.
 * Connects to /api/ws/events and broadcasts events to subscribers.
 */

const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const WS_URL = `${wsProtocol}//${window.location.host}/api/ws/events`

class EventSocket {
  constructor() {
    this._ws       = null
    this._subs     = new Set()
    this._connected = false
    this._reconnectTimer = null
    this._reconnectDelay = 2000
    this._pingTimer = null
  }

  connect() {
    if (this._ws && (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    try {
      this._ws = new WebSocket(WS_URL)

      this._ws.onopen = () => {
        this._connected = true
        this._reconnectDelay = 2000
        this._startPing()
        this._notify({ type: 'connected' })
      }

      this._ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          this._notify({ type: 'event', data })
        } catch {}
      }

      this._ws.onclose = () => {
        this._connected = false
        this._stopPing()
        this._notify({ type: 'disconnected' })
        this._scheduleReconnect()
      }

      this._ws.onerror = () => {
        this._ws?.close()
      }
    } catch (e) {
      this._scheduleReconnect()
    }
  }

  disconnect() {
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
  }

  subscribe(callback) {
    this._subs.add(callback)
    return () => this._subs.delete(callback)
  }

  get connected() {
    return this._connected
  }

  _startPing() {
    this._stopPing()
    this._pingTimer = setInterval(() => {
      if (this._ws && this._ws.readyState === WebSocket.OPEN) {
        try { this._ws.send('__ping__') } catch {}
      }
    }, 15000)
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
      this._reconnectDelay = Math.min(this._reconnectDelay * 1.5, 15000)
      this.connect()
    }, this._reconnectDelay)
  }
}

const eventSocket = new EventSocket()
export default eventSocket
