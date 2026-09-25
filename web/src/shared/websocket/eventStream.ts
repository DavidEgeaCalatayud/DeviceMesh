import { getToken } from '../api/session'
import type { DeviceEvent } from '../../entities/event/types'

export type EventEnvelope = { type: string; payload: unknown }

export function isDeviceEventEnvelope(event: EventEnvelope): event is { type: 'device.event'; payload: DeviceEvent } {
  if (event.type !== 'device.event' || typeof event.payload !== 'object' || event.payload === null) return false
  return 'deviceId' in event.payload && 'name' in event.payload && 'timestamp' in event.payload
}

export function connectEventStream(onEvent: (event: EventEnvelope) => void): () => void {
  const url = import.meta.env.VITE_WS_BASE_URL ?? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
  let stopped = false
  let socket: WebSocket | null = null
  let reconnectTimer: number | null = null
  let heartbeatTimer: number | null = null
  let retryDelay = 1000

  const clearHeartbeat = () => {
    if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }

  const connect = () => {
    if (stopped) return
    socket = new WebSocket(`${url}/ws/events`)
    socket.onopen = () => {
      retryDelay = 1000
      if (getToken()) socket?.send(JSON.stringify({ token: getToken() }))
      clearHeartbeat()
      heartbeatTimer = window.setInterval(() => {
        if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
      }, 25000)
    }
    socket.onmessage = (message) => onEvent(JSON.parse(message.data) as EventEnvelope)
    socket.onerror = () => socket?.close()
    socket.onclose = () => {
      clearHeartbeat()
      if (stopped) return
      reconnectTimer = window.setTimeout(connect, retryDelay)
      retryDelay = Math.min(retryDelay * 2, 10000)
    }
  }

  connect()
  return () => {
    stopped = true
    clearHeartbeat()
    if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
    socket?.close()
  }
}
