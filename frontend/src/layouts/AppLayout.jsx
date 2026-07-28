import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Globe, Radio, ScrollText, LogOut,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useRealtime } from '../hooks/useRealtime'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/proxies', label: 'Proxys', icon: Globe },
  { to: '/gateway', label: 'Gateway', icon: Radio },
  { to: '/logs', label: 'Logs', icon: ScrollText },
]

export default function AppLayout() {
  useRealtime()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen bg-bg">
      <aside className="w-64 border-r border-border bg-panel flex flex-col">
        <div className="p-5 flex items-center gap-2 border-b border-border">
          <Radio className="text-accent" size={22} />
          <span className="font-bold text-lg text-white">ProxyHub</span>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-accent/15 text-accent font-medium'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-border">
          <div className="px-3 py-2 text-xs text-slate-500">
            Conectado como <span className="text-slate-300">{user?.username}</span>
            <div className="uppercase text-[10px] text-accent mt-0.5">{user?.role}</div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-bad hover:bg-white/5 rounded-lg"
          >
            <LogOut size={16} /> Sair
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="p-6 max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
