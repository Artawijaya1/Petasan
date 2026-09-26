export const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '8000'

export const BACKEND_WS_URL =
  import.meta.env.VITE_BACKEND_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:${BACKEND_PORT}/ws/agent`

export const INITIAL_TERMINAL_OUTPUT = 'PETASAN // agent terminal\nMenunggu permintaan...\n'

export const CONNECTION_LABELS = {
  connecting: 'Menyambungkan',
  connected: 'Backend terhubung',
  disconnected: 'Backend terputus',
  error: 'Koneksi bermasalah',
}

export const RUN_STATUS_LABELS = {
  idle: 'Belum dijalankan',
  running: 'Sedang berjalan',
  completed: 'Selesai',
  failed: 'Perlu perhatian',
}
