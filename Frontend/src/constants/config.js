export const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '8000'

export const BACKEND_WS_URL =
  import.meta.env.VITE_BACKEND_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:${BACKEND_PORT}/ws/agent`

export const INITIAL_TERMINAL_OUTPUT = 'ZETO // agent terminal\nAwaiting request...\n'

export const CONNECTION_LABELS = {
  connecting: 'Connecting',
  connected: 'Backend connected',
  disconnected: 'Backend disconnected',
  error: 'Connection error',
}

export const RUN_STATUS_LABELS = {
  idle: 'Not started',
  running: 'Running',
  completed: 'Completed',
  failed: 'Needs attention',
}
