import { useState, useEffect, useCallback } from 'react'

interface Progress {
  current_step: string
  current_step_label: string
  completed_steps: string[]
  total_steps: number
  percent: number
}

interface Job {
  job_id: string
  job_url: string
  status: 'created' | 'processing' | 'completed' | 'failed'
  job_title?: string
  company?: string
  error?: string
  progress?: Progress
}

interface Props {
  highlightJobId: string | null
  onViewReport: (jobId: string) => void
  onAnalyzeNew: () => void
}

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  created: { bg: '#f1f5f9', color: '#64748b', label: '⏳ Queued' },
  completed: { bg: '#f0fdf4', color: '#16a34a', label: '✅ Complete' },
  failed: { bg: '#fef2f2', color: '#dc2626', label: '❌ Failed' },
}

const STEP_LABELS: Record<string, string> = {
  fetch_html: '🌐 Fetch Page',
  parse_jd: '📋 Parse JD',
  fetch_company: '🏢 Company Intel',
  fetch_salary: '💰 Salary Data',
  fetch_interviews: '🎯 Interview Prep',
  generate_report: '📊 Generate Report',
}

const STEP_ORDER = ['fetch_html', 'parse_jd', 'fetch_company', 'fetch_salary', 'fetch_interviews', 'generate_report']

function ProgressBar({ progress }: { progress: Progress }) {
  const completed = progress.completed_steps || []
  const percent = progress.percent || 0

  return (
    <div style={{ width: '100%', marginTop: '12px' }}>
      {/* Current step label */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '8px',
      }}>
        <span style={{
          fontSize: '13px',
          fontWeight: '600',
          color: '#2563eb',
          animation: 'pulse 2s ease-in-out infinite',
        }}>
          {progress.current_step_label}
        </span>
        <span style={{
          fontSize: '12px',
          fontWeight: '600',
          color: '#64748b',
        }}>
          {percent}%
        </span>
      </div>

      {/* Progress bar */}
      <div style={{
        width: '100%',
        height: '8px',
        background: '#e2e8f0',
        borderRadius: '4px',
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${percent}%`,
          height: '100%',
          background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
          borderRadius: '4px',
          transition: 'width 0.5s ease-in-out',
        }} />
      </div>

      {/* Step indicators */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: '10px',
        gap: '4px',
      }}>
        {STEP_ORDER.map(step => {
          const isDone = completed.includes(step)
          const isCurrent = progress.current_step === step && !isDone
          return (
            <div key={step} style={{
              flex: 1,
              textAlign: 'center',
            }}>
              <div style={{
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                margin: '0 auto 4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: '700',
                background: isDone ? '#16a34a' : isCurrent ? '#2563eb' : '#e2e8f0',
                color: isDone || isCurrent ? 'white' : '#94a3b8',
                transition: 'all 0.3s ease',
                ...(isCurrent ? {
                  boxShadow: '0 0 0 3px rgba(37,99,235,0.2)',
                  animation: 'pulse 2s ease-in-out infinite',
                } : {}),
              }}>
                {isDone ? '✓' : isCurrent ? '⋯' : ''}
              </div>
              <div style={{
                fontSize: '10px',
                color: isDone ? '#16a34a' : isCurrent ? '#2563eb' : '#94a3b8',
                fontWeight: isDone || isCurrent ? '600' : '400',
                lineHeight: '1.2',
              }}>
                {STEP_LABELS[step]}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
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
    const interval = setInterval(() => {
      fetchJobs()
    }, 2000) // poll every 2s for smoother progress updates
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
            const isProcessing = job.status === 'processing' || job.status === 'created'
            const style = isProcessing ? null : (STATUS_STYLES[job.status] || STATUS_STYLES.created)
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
                }}
              >
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: '600', fontSize: '16px', color: '#1e293b', marginBottom: '2px' }}>
                      {job.job_title || (isProcessing ? 'Analyzing...' : 'Unknown Job')}
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

                  {!isProcessing && style && (
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
                  )}

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

                {/* Progress bar for processing jobs */}
                {isProcessing && job.progress && (
                  <ProgressBar progress={job.progress} />
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Pulse animation keyframes */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  )
}

