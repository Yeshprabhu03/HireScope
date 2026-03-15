import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  FileText,
  ExternalLink,
  Search,
  Loader2,
  AlertCircle,
  Briefcase,
  RefreshCw
} from 'lucide-react'
import { API_HEADERS } from '../api_config'

interface Job {
  job_id: string
  job_url: string
  status: string
  job_title?: string
  company?: string
  progress?: {
    percent: number
    current_step_label: string
  }
}

interface DashboardProps {
  onViewReport: (jobId: string) => void
  onAnalyzeNew: () => void
  highlightJobId?: string | null
  sessionId: string
}

const Dashboard = ({ onViewReport, onAnalyzeNew, highlightJobId, sessionId }: DashboardProps) => {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [limit, setLimit] = useState(15)
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)

  const fetchJobs = async (isInitial = false, isPolling = false) => {
    try {
      if (isInitial) setLoading(true)

      const currentLimit = isInitial ? 15 : limit
      const currentOffset = isInitial ? 0 : offset

      const response = await fetch(`/api/jobs?limit=${currentLimit}&offset=${currentOffset}&session_id=${sessionId}`, {
        headers: API_HEADERS
      })
      if (!response.ok) throw new Error('Failed to fetch jobs')
      const data: Job[] = await response.json()

      if (isInitial) {
        setJobs(data)
        setOffset(0)
        setLimit(15)
      } else if (isPolling) {
        const pollResponse = await fetch(`/api/jobs?limit=${offset + limit}&offset=0&session_id=${sessionId}`, {
          headers: API_HEADERS
        })
        const pollData: Job[] = await pollResponse.json()
        setJobs(pollData)
      } else {
        setJobs((prev: Job[]) => [...prev, ...data])
        setOffset((prev: number) => prev + limit)
      }

      if (data.length < currentLimit) {
        setHasMore(false)
      } else {
        setHasMore(true)
      }
    } catch (err: any) {
      if (!isPolling) setError(err.message)
    } finally {
      if (isInitial) setLoading(false)
    }
  }

  useEffect(() => {
    fetchJobs(true)
  }, [])

  useEffect(() => {
    // Smart Polling: Only poll if there's an active job (queued or processing)
    const hasActiveJobs = jobs.some(j => j.status === 'processing' || j.status === 'queued' || j.status === 'created')

    if (!hasActiveJobs) return // No active jobs, stop polling

    const interval = setInterval(() => {
      fetchJobs(false, true)
    }, 5000)

    return () => clearInterval(interval)
  }, [jobs, offset, limit])

  const handleRetry = async (url: string) => {
    try {
      setLoading(true)
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: API_HEADERS,
        body: JSON.stringify({ job_url: url, provider: 'gemini' }),
      })
      if (!response.ok) throw new Error('Failed to restart analysis')
      fetchJobs()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading && jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <Loader2 className="animate-spin text-indigo-600 mb-4" size={48} />
        <p className="text-slate-500 font-medium">Accessing Intelligence Vault...</p>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-6">
      <div className="flex items-center justify-between mb-12">
        <div>
          <h2 className="text-4xl font-extrabold text-slate-900 font-heading tracking-tight">My Jobs Vault</h2>
          <p className="text-slate-500 mt-2 text-lg">Manage and access your AI-powered job intelligence reports.</p>
        </div>
        <button onClick={onAnalyzeNew} className="btn-vibrant shadow-indigo-200">
          <Search size={20} />
          Analyze New Job
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 p-4 rounded-2xl flex items-center gap-3 text-red-700 mb-8 animate-fade-in shadow-sm">
          <AlertCircle size={20} />
          <p className="text-sm font-semibold">{error}</p>
        </div>
      )}

      {jobs.length === 0 ? (
        <div className="card-vibrant p-16 text-center flex flex-col items-center bg-white border-2 border-dashed border-slate-200">
          <div className="w-20 h-20 bg-slate-50 rounded-3xl flex items-center justify-center mb-6">
            <Briefcase className="text-slate-300" size={40} />
          </div>
          <h3 className="text-2xl font-bold text-slate-900 mb-3">No jobs analyzed yet</h3>
          <p className="text-slate-500 mb-8 max-w-sm text-lg leading-relaxed">
            Paste a job URL on the home page to start generating your first intelligence report.
          </p>
          <button onClick={onAnalyzeNew} className="btn-vibrant px-10 py-4 text-lg">
            Get Started
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-12">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {jobs.map((job) => (
              <motion.div
                key={job.job_id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className={`card-vibrant p-6 flex flex-col h-full overflow-hidden relative group ${
                  highlightJobId === job.job_id ? 'ring-4 ring-indigo-500/20 border-indigo-500' : ''
                }`}
              >
                {/* Background Glow */}
                <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-50/50 rounded-full blur-3xl group-hover:bg-indigo-100/50 transition-colors" />

                <div className="flex items-start justify-between mb-6 relative z-10">
                  <div className="bg-indigo-50 text-indigo-600 p-3 rounded-2xl shadow-sm border border-indigo-100/50 group-hover:scale-110 transition-transform">
                    <FileText size={24} />
                  </div>
                  <div className={`status-badge ${
                    job.status === 'completed' ? 'status-completed' :
                    job.status === 'failed' ? 'status-failed' : 'status-processing shadow-sm ring-1 ring-blue-100'
                  }`}>
                    {job.status}
                  </div>
                </div>

                <div className="flex-1 relative z-10">
                  <h3 className="text-xl font-bold text-slate-900 line-clamp-1 mb-1 font-heading group-hover:text-indigo-600 transition-colors">
                    {job.status === 'failed' ? 'Analysis Failed' : (job.job_title || 'Analyzing Role...')}
                  </h3>
                  <p className="text-sm text-indigo-600 font-bold mb-4 flex items-center gap-1.5">
                    {job.status !== 'failed' && <span className="w-1.5 h-1.5 bg-indigo-600 rounded-full animate-pulse" />}
                    {job.status === 'failed' ? 'Connection Blocked' : (job.company || 'Fetching Intelligence...')}
                  </p>
                  <div className="flex items-center gap-2 text-slate-400 mb-6 group/link">
                    <ExternalLink size={14} className="group-hover/link:text-indigo-400 transition-colors" />
                    <span className="text-xs font-medium truncate group-hover/link:text-slate-600 transition-colors">{job.job_url}</span>
                  </div>
                </div>

                <div className="space-y-5 relative z-10 pt-4 border-t border-slate-50">
                  {(job.status === 'processing' || job.status === 'queued' || job.status === 'created') && (
                    <div className="space-y-3">
                      <div className="flex justify-between text-[11px] font-bold text-slate-500 uppercase tracking-widest">
                        <span className="flex items-center gap-2">
                          <Loader2 size={12} className="animate-spin text-indigo-500" />
                          {job.progress?.current_step_label || 'Initiating...'}
                        </span>
                        <span className="text-indigo-600">{job.progress?.percent || 0}%</span>
                      </div>
                      <div className="progress-container shadow-inner">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${job.progress?.percent || 0}%` }}
                          className="progress-bar-vibrant shadow-[0_0_12px_rgba(99,102,241,0.5)]"
                        />
                      </div>
                    </div>
                  )}

                  {job.status === 'failed' ? (
                    <div className="flex flex-col gap-3">
                      <div className="p-3 bg-red-50/50 border border-red-100 rounded-xl text-xs text-red-600 font-medium leading-relaxed">
                        Intelligence synthesis interrupted. This can happen with restricted job boards.
                      </div>
                      <button
                        onClick={() => handleRetry(job.job_url)}
                        className="w-full py-3 rounded-xl font-bold text-sm bg-slate-900 text-white hover:bg-black transition-all flex items-center justify-center gap-2 shadow-sm active:scale-95"
                      >
                        <RefreshCw size={16} />
                        Retry Analysis
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => onViewReport(job.job_id)}
                      disabled={job.status !== 'completed'}
                      className={`w-full py-3.5 rounded-xl font-bold text-sm transition-all flex items-center justify-center gap-2 ${
                        job.status === 'completed'
                          ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-md shadow-indigo-100 hover:shadow-indigo-200'
                          : 'bg-slate-50 text-slate-400 cursor-not-allowed border border-slate-100'
                      }`}
                    >
                      <FileText size={18} />
                      View Intelligence Report
                    </button>
                  )}
                </div>
              </motion.div>
            ))}
          </div>

          {hasMore && (
            <div className="flex justify-center pb-12">
              <button
                onClick={() => fetchJobs(false, false)}
                disabled={loading}
                className="flex items-center gap-2 px-8 py-3 bg-white border border-slate-200 rounded-xl font-bold text-slate-600 hover:bg-slate-50 transition-all shadow-sm hover:shadow-md active:scale-95 disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 size={18} className="animate-spin text-indigo-500" />
                ) : (
                  <RefreshCw size={18} className="text-indigo-500" />
                )}
                Load More Reports
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default Dashboard
