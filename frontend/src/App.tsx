import { useState } from 'react'
import JobInput from './components/JobInput'
import Dashboard from './components/Dashboard'
import ReportViewer from './components/ReportViewer'

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
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      {/* Nav */}
      <nav style={{
        background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
        padding: '0 24px',
        height: '60px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
      }}>
        <div
          style={{ color: 'white', fontSize: '20px', fontWeight: '700', cursor: 'pointer' }}
          onClick={() => setView('input')}
        >
          🔍 HireScope
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <button
            onClick={() => setView('input')}
            style={{
              background: view === 'input' ? 'rgba(255,255,255,0.3)' : 'transparent',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.4)',
              padding: '6px 16px',
              borderRadius: '6px',
              fontSize: '14px',
            }}
          >
            Analyze Job
          </button>
          <button
            onClick={() => setView('dashboard')}
            style={{
              background: view === 'dashboard' ? 'rgba(255,255,255,0.3)' : 'transparent',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.4)',
              padding: '6px 16px',
              borderRadius: '6px',
              fontSize: '14px',
            }}
          >
            My Jobs
          </button>
        </div>
      </nav>

      {/* Main content */}
      <main style={{ padding: '32px 24px', maxWidth: '1100px', margin: '0 auto' }}>
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
      </main>
    </div>
  )
}

export default App
