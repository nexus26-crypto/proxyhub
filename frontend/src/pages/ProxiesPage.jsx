import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Upload, Zap, Trash2 } from 'lucide-react'
import { proxyService } from '../services/domain'
import { StatusBadge } from '../components/Common'

const PROXY_TYPES = ['http', 'https', 'socks4', 'socks5']

export default function ProxiesPage() {
  const queryClient = useQueryClient()
  const fileRef = useRef(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ host: '', port: '', username: '', password: '', type: 'http' })

  const { data: proxies = [], isLoading } = useQuery({
    queryKey: ['proxies'],
    queryFn: () => proxyService.list({ limit: 200 }).then((r) => r.data),
    refetchInterval: 15000,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['proxies'] })

  const createMutation = useMutation({
    mutationFn: (payload) => proxyService.create(payload),
    onSuccess: () => {
      invalidate()
      setShowForm(false)
      setForm({ host: '', port: '', username: '', password: '', type: 'http' })
    },
  })

  const testMutation = useMutation({ mutationFn: (id) => proxyService.test(id), onSuccess: invalidate })
  const deleteMutation = useMutation({ mutationFn: (id) => proxyService.remove(id), onSuccess: invalidate })
  const importMutation = useMutation({ mutationFn: (file) => proxyService.import(file), onSuccess: invalidate })

  const handleImport = (e) => {
    const file = e.target.files?.[0]
    if (file) importMutation.mutate(file)
    e.target.value = ''
  }

  const handleCreate = (e) => {
    e.preventDefault()
    createMutation.mutate({ ...form, port: Number(form.port) })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Proxys</h1>
        <div className="flex gap-2">
          <button
            onClick={() => fileRef.current?.click()}
            className="flex items-center gap-1 text-sm bg-panel border border-border px-3 py-2 rounded-lg hover:bg-white/5"
          >
            <Upload size={14} /> Importar TXT/CSV
          </button>
          <input ref={fileRef} type="file" accept=".txt,.csv" className="hidden" onChange={handleImport} />
          <button
            onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-1 text-sm bg-accent px-3 py-2 rounded-lg text-white hover:bg-accent/90"
          >
            <Plus size={14} /> Novo proxy
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
          <Field label="Host" value={form.host} onChange={(v) => setForm({ ...form, host: v })} required />
          <Field label="Porta" value={form.port} onChange={(v) => setForm({ ...form, port: v })} type="number" required />
          <Field label="Usuário" value={form.username} onChange={(v) => setForm({ ...form, username: v })} />
          <Field label="Senha" value={form.password} onChange={(v) => setForm({ ...form, password: v })} type="password" />
          <div>
            <label className="text-xs text-slate-400">Tipo</label>
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
              className="w-full mt-1 bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent uppercase"
            >
              {PROXY_TYPES.map((t) => <option key={t} value={t}>{t.toUpperCase()}</option>)}
            </select>
          </div>
          <button type="submit" className="bg-accent text-white text-sm rounded-lg py-2">Salvar</button>
        </form>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-border">
              <th className="py-2 pr-4">Host:Porta</th>
              <th className="py-2 pr-4">Tipo</th>
              <th className="py-2 pr-4">País</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4">Score</th>
              <th className="py-2 pr-4">Latência</th>
              <th className="py-2 pr-4">Sucessos/Falhas</th>
              <th className="py-2 pr-4">Ações</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={8} className="py-4 text-slate-500">Carregando...</td></tr>
            )}
            {proxies.map((p) => (
              <tr key={p.id} className="border-b border-border/50 hover:bg-white/5">
                <td className="py-2 pr-4 font-mono">{p.host}:{p.port}</td>
                <td className="py-2 pr-4 uppercase text-xs text-slate-400">{p.type}</td>
                <td className="py-2 pr-4">{p.country || '—'}</td>
                <td className="py-2 pr-4"><StatusBadge status={p.status} /></td>
                <td className="py-2 pr-4">{p.score.toFixed(1)}</td>
                <td className="py-2 pr-4">{p.latency_ms ? `${p.latency_ms.toFixed(0)}ms` : '—'}</td>
                <td className="py-2 pr-4 text-xs">
                  <span className="text-good">{p.success_count}</span> / <span className="text-bad">{p.fail_count}</span>
                </td>
                <td className="py-2 pr-4">
                  <div className="flex gap-2">
                    <button onClick={() => testMutation.mutate(p.id)} title="Testar"
                      className="p-1.5 rounded hover:bg-white/10 text-accent">
                      <Zap size={14} />
                    </button>
                    <button onClick={() => deleteMutation.mutate(p.id)} title="Excluir"
                      className="p-1.5 rounded hover:bg-white/10 text-bad">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!isLoading && proxies.length === 0 && (
              <tr><td colSpan={8} className="py-6 text-center text-slate-500">Nenhum proxy cadastrado</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, type = 'text', required }) {
  return (
    <div>
      <label className="text-xs text-slate-400">{label}</label>
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-1 bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
      />
    </div>
  )
}
