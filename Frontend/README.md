# Zeto Frontend Dashboard

React 19 + Vite 8 dashboard for the Zeto Zero-Touch Environment Provisioner.

## Development

```bash
cd Frontend
npm install
npm run dev
```

Dashboard available at: `http://localhost:5173`

## Configuration

Environment variables (via Vite):

| Variable | Default | Description |
|---|---|---|
| `VITE_BACKEND_WS_URL` | Auto-detected from `window.location` | Full WebSocket URL (e.g. `ws://localhost:8000/ws/agent`) |
| `VITE_BACKEND_PORT` | `8000` | Backend port if `VITE_BACKEND_WS_URL` not set |
| `VITE_BACKEND_URL` | `http://127.0.0.1:8000` | Used by Vite for WebSocket proxy in dev mode |

## Build

```bash
npm run build
```

## Tech Stack

- React 19
- Vite 8
- Tailwind CSS
- Oxlint for linting

## Project Structure

```
src/
├── App.jsx                 # Root component with WebSocket state
├── main.jsx                # Entry point
├── index.css               # Global styles
├── components/
│   ├── Header.jsx          # Top bar with connection status
│   ├── Intro.jsx           # Hero section
│   ├── ControlPanel.jsx    # Session control form
│   ├── ActivityPanel.jsx   # Agent events timeline
│   ├── TerminalPanel.jsx   # Streaming terminal output
│   └── Footer.jsx          # Static footer
├── constants/
│   └── config.js           # WS URL, status labels
├── hooks/
│   └── useAgentSocket.js   # WebSocket connection hook
└── App.css                 # Component styles
```
