import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api/v1/ws'

export function useRealtime() {
  const queryClient = useQueryClient()
  const wsRef = useRef(null)
  const accessToken = useAuthStore((s) => s.accessToken)

  const invalidate = useCallback(
    (type) => {
      if (type?.startsWith('proxy_')) queryClient.invalidateQueries({ queryKey: ['proxies'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    [queryClient]
  )

  useEffect(() => {
    if (!accessToken) return undefined

    let reconnectTimeout
    const connect = () => {
      const ws = new WebSocket(`${WS_URL}?token=${accessToken}`)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          invalidate(data.type)
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        reconnectTimeout = setTimeout(connect, 3000)
      }
    }

    connect()

    return () => {
      clearTimeout(reconnectTimeout)
      wsRef.current?.close()
    }
  }, [accessToken, invalidate])
}
