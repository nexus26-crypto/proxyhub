import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { logService } from '../services/domain'

const LEVEL_COLORS = {
  debug: 'text-slate-500',
  info: 'text-accent',
  warning: 'text-warn',
  error: 'text-bad',
  critical: 'text-bad font-bold',
}

export default function LogsPage() {
  const [level, setLevel] = useState('')

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['logs', level],
    queryFn: () => logService.list({ level: level || undefined, limit: 300 }).then((r) => r.data),
    refetchInterval: 8000,
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Logs</h1>
        <select value={level} onChange={(e) => setLevel(e.target.value)}
          className="bg-panel border border-border rounded-lg px-3 py-2 text-sm">
          <option value="">Todos os níveis</option>
          <option value="debug">Debug</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      <div className="card font-mono text-xs max-h-[70vh] overflow-y-auto space-y-1">
        {isLoading && <p className="text-slate-500">Carregando...</p>}
        {logs.map((log) => (
          <div key={log.id} className="flex gap-3 py-1 border-b border-border/30">
            <span className="text-slate-600 whitespace-nowrap">{new Date(log.created_at).toLocaleString('pt-BR')}</span>
            <span className={`uppercase font-bold ${LEVEL_COLORS[log.level] || 'text-slate-400'}`}>{log.level}</span>
            {log.source && <span className="text-slate-500">[{log.source}]</span>}
            <span className="text-slate-300">{log.message}</span>
          </div>
        ))}
        {!isLoading && logs.length === 0 && <p className="text-slate-500">Nenhum log encontrado</p>}
      </div>
    </div>
  )
}
