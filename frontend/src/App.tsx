import { useState } from 'react'
import JobInput from './components/JobInput'
import Dashboard from './components/Dashboard'
import ReportViewer from './components/ReportViewer'
import { motion, AnimatePresence } from 'framer-motion'

type View = 'input' | 'dashboard' | 'report'

function App() {
  const [view, setView] = useState<View>('input')
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const handleJobSubmitted = (jobId: string) => {
    setSelectedJobId(jobId)
    setView('dashboard')
    setRefreshKey(k => k + 1)
  }

  const handleViewReport = (jobId: string) => {
    setSelectedJobId(jobId)
    setView('report')
  }

  const handleBack = () => {
    if (view === 'report') {
      setView('dashboard')
    } else {
      setView('input')
    }
  }

  return (
    <div className="min-h-screen bg-[#f1f5f9] text-[#1e293b]">
      {/* Vibrant Header */}
      <nav className="header-vibrant sticky top-0 z-50 shadow-md">
        <div className="header-container">
          <div
            className="flex items-center gap-2 cursor-pointer group"
            onClick={() => setView('input')}
          >
            <span className="text-2xl">🔍</span>
            <span className="font-heading font-bold text-xl tracking-tight">HireScope</span>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setView('input')}
              className={`btn-vibrant-secondary px-4 py-2 ${
                view === 'input' ? 'bg-white/20 !border-white/40' : ''
              }`}
            >
              Analyze Job
            </button>
            <button
              onClick={() => setView('dashboard')}
              className={`btn-vibrant-secondary px-4 py-2 ${
                view === 'dashboard' ? 'bg-white/20 !border-white/40' : ''
              }`}
            >
              My Jobs
            </button>
          </div>
        </div>
      </nav>

      <main className={`relative pt-10 ${view === 'report' ? '' : 'max-w-7xl mx-auto px-6'}`}>
        <AnimatePresence mode="wait">
          <motion.div
            key={view}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
          >
            {view === 'input' && (
              <JobInput onJobSubmitted={handleJobSubmitted} />
            )}
            {view === 'dashboard' && (
              <Dashboard
                key={refreshKey}
                highlightJobId={selectedJobId}
                onViewReport={handleViewReport}
                onAnalyzeNew={() => setView('input')}
              />
            )}
            {view === 'report' && selectedJobId && (
              <ReportViewer jobId={selectedJobId} onBack={handleBack} />
            )}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Modern Footer */}
      {view !== 'report' && (
        <footer className="mt-20 py-12 border-t border-slate-200">
          <div className="max-w-7xl mx-auto px-6 text-center opacity-50">
            <p className="text-xs font-bold uppercase tracking-widest">
              Powered by AI Intelligence & PostgreSQL
            </p>
          </div>
        </footer>
      )}
    </div>
  )
}

export default App
