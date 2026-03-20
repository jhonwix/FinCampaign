import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, Activity, Network, Upload } from 'lucide-react'
import { api } from '../api/client'

export function Layout() {
  const navigate = useNavigate()
  const location = useLocation()

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 30_000,
  })

  return (
    <div className="min-h-screen bg-slate-100">
      {/* Nav */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2.5 hover:opacity-80 transition-opacity"
          >
            <div className="bg-indigo-600 p-1.5 rounded-lg">
              <BrainCircuit className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-slate-900 text-sm">FinCampaign</span>
              <span className="text-slate-400 text-xs ml-1.5">RAG Agent</span>
            </div>
          </button>

          <div className="flex items-center gap-4">
            <nav className="flex gap-1 text-sm">
              <button
                onClick={() => navigate('/')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  location.pathname === '/'
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                Customers
              </button>
              <button
                onClick={() => navigate('/customers/import')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1.5 ${
                  location.pathname === '/customers/import'
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <Upload className="w-3.5 h-3.5" />
                Importar
              </button>
              <button
                onClick={() => navigate('/campaigns')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  location.pathname.startsWith('/campaigns')
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                Campañas
              </button>
              <button
                onClick={() => navigate('/architecture')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1.5 ${
                  location.pathname === '/architecture'
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <Network className="w-3.5 h-3.5" />
                Arquitectura
              </button>
            </nav>

            {health && (
              <div className="flex items-center gap-1.5 text-xs text-emerald-600">
                <Activity className="w-3.5 h-3.5" />
                <span>API {health.status}</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
