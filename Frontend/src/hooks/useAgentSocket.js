import { useCallback, useEffect, useRef, useState } from 'react'
import { INITIAL_TERMINAL_OUTPUT } from '../constants/config'

export function useAgentSocket(backendUrl) {
  const [connectionState, setConnectionState] = useState('connecting')
  const [isRunning, setIsRunning] = useState(false)
  const [runStatus, setRunStatus] = useState('idle')
  const [events, setEvents] = useState([])
  const [terminalOutput, setTerminalOutput] = useState(INITIAL_TERMINAL_OUTPUT)
  const [reconnectKey, setReconnectKey] = useState(0)
  const socketRef = useRef(null)
  const eventId = useRef(0)

  useEffect(() => {
    const socket = new WebSocket(backendUrl)
    socketRef.current = socket

    socket.addEventListener('open', () => setConnectionState('connected'))
    socket.addEventListener('message', (message) => {
      let event
      try {
        event = JSON.parse(message.data)
      } catch {
        setTerminalOutput((output) => `${output}\nRespons backend tidak valid.\n`)
        return
      }

      if (event.type === 'terminal_log') {
        setTerminalOutput((output) => `${output}${event.content || ''}`.slice(-24000))
        return
      }

      if (event.type === 'agent_thought' || event.type === 'agent_error') {
        setEvents((current) => [
          ...current,
          { ...event, id: eventId.current++ },
        ].slice(-80))
        if (event.status === 'failed' || event.type === 'agent_error') {
          setRunStatus('failed')
        }
        if (event.type === 'agent_error') setIsRunning(false)
        return
      }

      if (event.type === 'agent_finished' || event.type === 'agent_complete') {
        setIsRunning(false)
        setRunStatus(event.status === 'completed' ? 'completed' : 'failed')
      }
    })

    socket.addEventListener('error', () => setConnectionState('error'))
    socket.addEventListener('close', () => {
      setConnectionState('disconnected')
      setIsRunning(false)
      setRunStatus((status) => (status === 'running' ? 'failed' : status))
      if (socketRef.current === socket) socketRef.current = null
    })

    return () => {
      socket.close()
      if (socketRef.current === socket) socketRef.current = null
    }
  }, [backendUrl, reconnectKey])

  const reconnect = useCallback(() => {
    setConnectionState('connecting')
    setReconnectKey((key) => key + 1)
  }, [])

  const startProvisioning = useCallback((repoPath, trusted) => {
    const socket = socketRef.current
    if (!repoPath.trim() || !trusted || socket?.readyState !== WebSocket.OPEN) return

    setEvents([])
    setTerminalOutput(`PETASAN // ${repoPath.trim()}\nMemulai sesi agent...\n`)
    setIsRunning(true)
    setRunStatus('running')
    socket.send(JSON.stringify({ action: 'start', repo_path: repoPath.trim() }))
  }, [])

  return {
    connectionState,
    isRunning,
    runStatus,
    events,
    terminalOutput,
    reconnect,
    startProvisioning,
  }
}
