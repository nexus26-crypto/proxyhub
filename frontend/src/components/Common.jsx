import clsx from 'clsx'

const STATUS_COLORS = {
  active: 'bg-good/15 text-good',
  online: 'bg-good/15 text-good',
  running: 'bg-good/15 text-good',
  finished: 'bg-good/15 text-good',
  inactive: 'bg-warn/15 text-warn',
  testing: 'bg-warn/15 text-warn',
  paused: 'bg-warn/15 text-warn',
  queued: 'bg-slate-500/15 text-slate-300',
  offline: 'bg-slate-500/15 text-slate-300',
  stopped: 'bg-slate-500/15 text-slate-300',
  blocked: 'bg-bad/15 text-bad',
  error: 'bg-bad/15 text-bad',
  failed: 'bg-bad/15 text-bad',
  cancelled: 'bg-bad/15 text-bad',
}

export function StatusBadge({ status }) {
  return (
    <span className={clsx('badge', STATUS_COLORS[status] || 'bg-slate-500/15 text-slate-300')}>
      {status}
    </span>
  )
}

export function MetricCard({ title, value, subtitle, icon: Icon, tone = 'default' }) {
  const toneClasses = {
    default: 'text-white',
    good: 'text-good',
    warn: 'text-warn',
    bad: 'text-bad',
  }
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-slate-400">{title}</span>
        {Icon && <Icon size={16} className="text-slate-500" />}
      </div>
      <div className={clsx('text-2xl font-bold', toneClasses[tone])}>{value}</div>
      {subtitle && <div className="text-xs text-slate-500 mt-1">{subtitle}</div>}
    </div>
  )
}
