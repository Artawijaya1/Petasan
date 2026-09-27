import { useState } from 'react'
import './App.css'
import {
  Header,
  Intro,
  ControlPanel,
  ActivityPanel,
  TerminalPanel,
  Footer,
} from './components'
import {
  BACKEND_WS_URL,
  CONNECTION_LABELS,
  RUN_STATUS_LABELS,
} from './constants/config'
import { useAgentSocket } from './hooks/useAgentSocket'

function App() {
  const [repoPath, setRepoPath] = useState('')
  const [trusted, setTrusted] = useState(false)

  const {
    connectionState,
    isRunning,
    runStatus,
    events,
    terminalOutput,
    reconnect,
    startProvisioning,
  } = useAgentSocket(BACKEND_WS_URL)

  function handleStart(event) {
    event.preventDefault()
    startProvisioning(repoPath, trusted)
  }

  const connectionLabel = CONNECTION_LABELS[connectionState]
  const runLabel = RUN_STATUS_LABELS[runStatus]

  return (
      <div className="app-shell">
        <Header
          connectionState={connectionState}
          connectionLabel={connectionLabel}
          onReconnect={reconnect}
        />

        <main id="top">
          <Intro backendUrl={BACKEND_WS_URL} />

          <section className="workspace" aria-label="Agent control and activity">
          <ControlPanel
            repoPath={repoPath}
            setRepoPath={setRepoPath}
            trusted={trusted}
            setTrusted={setTrusted}
            isRunning={isRunning}
            runStatus={runStatus}
            runLabel={runLabel}
            connectionState={connectionState}
            onSubmit={handleStart}
          />

          <ActivityPanel events={events} />
        </section>

        <TerminalPanel
          isRunning={isRunning}
          terminalOutput={terminalOutput}
        />
      </main>

      <Footer />
    </div>
  )
}

export default App
