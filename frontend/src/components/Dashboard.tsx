import { useState, useEffect, useCallback } from 'react'

interface Job {
  job_id: string
  job_url: string
  status: 'created' | 'processing' | 'completed' | 'failed'
  job_title?: string
  company?: string
  error?: string
}

interface Props {
  highlightJobId: string | null
  onViewReport: (jobId: string) => void
  onAnalyzeNew: () => void
}

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  created:    { bg: '#f1f5f9', color: '#64748b', label: '⏳ Queued' },
  processing: { bg: '#eff6ff', color: '#2563eb', label: '🔄 Analyzing...' },
  completed:  { bg: '#f0fdf4', color: '#16a34a', label: '✅ Complete' },
  failed:     { bg: '#fef2f2', color: '#dc2626', label: '❌ Failed' },
}

export default function Dashboard({ highlightJobId, onViewReport, onAnalyzeNew }: Props) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch('/api/jobs')
      if (res.ok) {
        const data: Job[] = await res.json()
        setJobs(data.reverse()) // newest first
      }
    } catch {
      // silently ignore network errors during polling
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
    // Poll every 3 seconds if any job is in progress
    const interval = setInterval(() => {
      fetchJobs()
    }, 3000)
    return () => clearInterval(interval)
  }, [fetchJobs])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0', color: '#94a3b8' }}>
        Loading your jobs...
      </div>
    )
  }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: '700', color: '#1e293b' }}>My Analyzed Jobs</h2>
          <p style={{ color: '#64748b', marginTop: '4px' }}>{jobs.length} job{jobs.length !== 1 ? 's' : ''} analyzed</p>
        </div>
        <button
          onClick={onAnalyzeNew}
          style={{
            background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
            color: 'white',
            border: 'none',
            padding: '10px 20px',
            borderRadius: '8px',
            fontWeight: '600',
            fontSize: '14px',
          }}
        >
          + Analyze New Job
        </button>
      </div>

      {jobs.length === 0 ? (
        <div style={{
          background: 'white',
          borderRadius: '12px',
          padding: '60px',
          textAlign: 'center',
          border: '2px dashed #e2e8f0',
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔍</div>
          <h3 style={{ color: '#374151', marginBottom: '8px' }}>No jobs analyzed yet</h3>
          <p style={{ color: '#94a3b8', marginBottom: '20px' }}>
            Paste a job URL to get started with AI-powered job intelligence
          </p>
          <button
            onClick={onAnalyzeNew}
            style={{
              background: '#2563eb',
              color: 'white',
              border: 'none',
              padding: '10px 24px',
              borderRadius: '8px',
              fontWeight: '600',
            }}
          >
            Analyze Your First Job
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {jobs.map(job => {
            const style = STATUS_STYLES[job.status] || STATUS_STYLES.created
            const isHighlighted = job.job_id === highlightJobId
            return (
              <div
                key={job.job_id}
                style={{
                  background: 'white',
                  borderRadius: '12px',
                  padding: '20px 24px',
                  border: isHighlighted ? '2px solid #2563eb' : '1px solid #e2e8f0',
                  boxShadow: isHighlighted ? '0 0 0 3px rgba(37,99,235,0.1)' : '0 1px 4px rgba(0,0,0,0.05)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: '600', fontSize: '16px', color: '#1e293b', marginBottom: '2px' }}>
                    {job.job_title || 'Analyzing...'}
                    {job.company && <span style={{ color: '#64748b', fontWeight: '400' }}> @ {job.company}</span>}
                  </div>
                  <div style={{
                    fontSize: '12px',
                    color: '#94a3b8',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {job.job_url}
                  </div>
                  {job.error && (
                    <div style={{ fontSize: '12px', color: '#dc2626', marginTop: '4px' }}>
                      Error: {job.error}
                    </div>
                  )}
                </div>

                <span style={{
                  background: style.bg,
                  color: style.color,
                  padding: '4px 12px',
                  borderRadius: '20px',
                  fontSize: '13px',
                  fontWeight: '500',
                  whiteSpace: 'nowrap',
                }}>
                  {style.label}
                </span>

                {job.status === 'completed' && (
                  <button
                    onClick={() => onViewReport(job.job_id)}
                    style={{
                      background: '#2563eb',
                      color: 'white',
                      border: 'none',
                      padding: '8px 16px',
                      borderRadius: '6px',
                      fontSize: '13px',
                      fontWeight: '600',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    View Report →
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
