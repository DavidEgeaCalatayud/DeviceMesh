export type EventEnvelope = { type: string; payload: unknown }

export function connectEventStream(onEvent: (event: EventEnvelope) => void): () => void {
  const url = import.meta.env.VITE_WS_BASE_URL ?? 'ws://localhost:8000'
  const socket = new WebSocket(`${url}/ws/events`)
  socket.onmessage = (message) => onEvent(JSON.parse(message.data) as EventEnvelope)
  return () => socket.close()
}
