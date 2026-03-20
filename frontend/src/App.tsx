import { Component, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { CustomerDetail } from './pages/CustomerDetail'
import { CampaignList } from './pages/CampaignList'
import { CreateCampaign } from './pages/CreateCampaign'
import { CampaignDetail } from './pages/CampaignDetail'
import { ArchitecturePage } from './pages/ArchitecturePage'
import { CustomerImport } from './pages/CustomerImport'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 10_000, retry: 1 },
  },
})

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50">
          <div className="bg-white border border-red-200 rounded-xl p-8 max-w-lg text-center shadow">
            <p className="text-lg font-semibold text-red-600 mb-2">Error inesperado</p>
            <p className="text-sm text-slate-500 font-mono mb-4">
              {(this.state.error as Error).message}
            </p>
            <button
              onClick={() => { this.setState({ error: null }); window.location.reload() }}
              className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700"
            >
              Recargar página
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/customers/import" element={<CustomerImport />} />
              <Route path="/customers/:id" element={<CustomerDetail />} />
              <Route path="/campaigns" element={<CampaignList />} />
              <Route path="/campaigns/new" element={<CreateCampaign />} />
              <Route path="/campaigns/:id" element={<CampaignDetail />} />
              <Route path="/architecture" element={<ArchitecturePage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
