import { useQuery } from '@tanstack/react-query'
import { Cpu, MemoryStick, Database, Globe } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { dashboardService } from '../services/domain'
import { MetricCard } from '../components/Common'

const COLORS = ['#22c55e', '#eab308', '#ef4444', '#3b82f6']

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => dashboardService.get().then((r) => r.data),
    refetchInterval: 10000,
  })

  if (isLoading || !data) {
    return <p className="text-slate-400">Carregando métricas...</p>
  }

  const proxyChart = [
    { name: 'Ativos', value: data.proxies.active },
    { name: 'Inativos', value: data.proxies.inactive },
    { name: 'Bloqueados', value: data.proxies.blocked },
    { name: 'Testando', value: data.proxies.testing },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      <div>
        <h2 className="text-sm text-slate-400 mb-2 uppercase tracking-wide">Sistema</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard title="CPU" value={`${data.system.cpu_percent.toFixed(1)}%`} icon={Cpu} />
          <MetricCard title="RAM" value={`${data.system.ram_percent.toFixed(1)}%`} icon={MemoryStick}
            subtitle={`${data.system.ram_used_mb.toFixed(0)} / ${data.system.ram_total_mb.toFixed(0)} MB`} />
          <MetricCard title="Redis" value={data.system.redis_ok ? 'Online' : 'Offline'} icon={Database}
            tone={data.system.redis_ok ? 'good' : 'bad'} />
          <MetricCard title="PostgreSQL" value={data.system.postgres_ok ? 'Online' : 'Offline'} icon={Database}
            tone={data.system.postgres_ok ? 'good' : 'bad'} />
        </div>
      </div>

      <div>
        <h2 className="text-sm text-slate-400 mb-2 uppercase tracking-wide flex items-center gap-1">
          <Globe size={14} /> Proxys
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card">
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={proxyChart} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75}>
                    {proxyChart.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#121722', border: '1px solid #1f2733' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 content-start">
            <MetricCard title="Total" value={data.proxies.total} />
            <MetricCard title="Ativos" value={data.proxies.active} tone="good" />
            <MetricCard title="Testando" value={data.proxies.testing} tone="warn" />
            <MetricCard title="Bloqueados/Inativos" value={data.proxies.blocked + data.proxies.inactive} tone="bad" />
          </div>
        </div>
      </div>
    </div>
  )
}
