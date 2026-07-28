import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Copy, Check, Radio, ShieldAlert, ShieldCheck } from 'lucide-react'
import api from '../services/api'

export default function GatewayPage() {
  const [copied, setCopied] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['gateway-info'],
    queryFn: () => api.get('/gateway/info').then((r) => r.data),
  })

  const host = window.location.hostname
  const gatewayUrl = data
    ? `http://${data.username}:${data.password}@${host}:${data.port}`
    : ''
  const encodedUrl = data
    ? `http://${encodeURIComponent(data.username)}:${encodeURIComponent(data.password)}@${host}:${data.port}`
    : ''

  const copy = (text, label) => {
    navigator.clipboard.writeText(text)
    setCopied(label)
    setTimeout(() => setCopied(''), 2000)
  }

  if (isLoading) {
    return <p className="text-slate-400">Carregando...</p>
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Radio className="text-accent" size={24} /> Gateway de Proxy Rotativo
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Aponte seu bot/script para este endereço único. Cada conexão nova é roteada
          automaticamente por um proxy diferente dentre os ativos, com retry automático
          em caso de falha.
        </p>
      </div>

      {!data?.configured && (
        <div className="card border-warn/50 bg-warn/5 flex items-start gap-3">
          <ShieldAlert className="text-warn shrink-0 mt-0.5" size={18} />
          <div className="text-sm text-warn">
            O gateway está sem usuário/senha configurados (<code>GATEWAY_USERNAME</code> /{' '}
            <code>GATEWAY_PASSWORD</code> no <code>.env</code>) — está aberto para qualquer um
            que descubra o IP e a porta. Configure uma senha antes de usar em produção.
          </div>
        </div>
      )}

      {data?.configured && (
        <div className="card border-good/50 bg-good/5 flex items-start gap-3">
          <ShieldCheck className="text-good shrink-0 mt-0.5" size={18} />
          <div className="text-sm text-good">Gateway protegido por autenticação.</div>
        </div>
      )}

      <div className="card space-y-4">
        <div>
          <label className="text-xs text-slate-400 mb-1 block">
            URL completa (usar em variáveis HTTP_PROXY / HTTPS_PROXY, requests, etc.)
          </label>
          <div className="flex gap-2">
            <input
              readOnly
              value={gatewayUrl}
              className="flex-1 bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono text-slate-300"
              onFocus={(e) => e.target.select()}
            />
            <button
              onClick={() => copy(gatewayUrl, 'raw')}
              className="flex items-center gap-1 bg-accent hover:bg-accent/90 text-white text-sm px-3 py-2 rounded-lg shrink-0"
            >
              {copied === 'raw' ? <Check size={14} /> : <Copy size={14} />}
              {copied === 'raw' ? 'Copiado!' : 'Copiar'}
            </button>
          </div>
        </div>

        <div>
          <label className="text-xs text-slate-400 mb-1 block">
            URL com senha codificada (usar se a senha tiver caracteres especiais em ferramentas
            sensíveis a isso, ex: curl -x, algumas libs de URL)
          </label>
          <div className="flex gap-2">
            <input
              readOnly
              value={encodedUrl}
              className="flex-1 bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono text-slate-300"
              onFocus={(e) => e.target.select()}
            />
            <button
              onClick={() => copy(encodedUrl, 'encoded')}
              className="flex items-center gap-1 bg-panel border border-border hover:bg-white/5 text-sm px-3 py-2 rounded-lg shrink-0"
            >
              {copied === 'encoded' ? <Check size={14} /> : <Copy size={14} />}
              {copied === 'encoded' ? 'Copiado!' : 'Copiar'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 pt-2 border-t border-border text-sm">
          <div>
            <div className="text-xs text-slate-500">Host</div>
            <div className="font-mono text-slate-300">{host}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Porta</div>
            <div className="font-mono text-slate-300">{data?.port}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Usuário</div>
            <div className="font-mono text-slate-300">{data?.username || '(sem auth)'}</div>
          </div>
        </div>
      </div>

      <div className="card space-y-2">
        <h2 className="text-sm font-medium text-white">Como usar</h2>
        <div className="text-sm text-slate-400 space-y-2">
          <p><span className="text-slate-300">Terminal (Linux/Mac):</span></p>
          <pre className="bg-bg border border-border rounded-lg p-2 text-xs overflow-x-auto font-mono">
{`export HTTP_PROXY="${gatewayUrl}"\nexport HTTPS_PROXY="${gatewayUrl}"`}
          </pre>
          <p><span className="text-slate-300">Python (requests):</span></p>
          <pre className="bg-bg border border-border rounded-lg p-2 text-xs overflow-x-auto font-mono">
{`proxies = {"http": "${gatewayUrl}", "https": "${gatewayUrl}"}\nrequests.get(url, proxies=proxies)`}
          </pre>
        </div>
      </div>
    </div>
  )
}
