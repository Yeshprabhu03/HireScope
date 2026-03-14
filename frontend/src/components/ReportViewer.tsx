import { useState, useEffect, useRef } from 'react'
import { API_HEADERS } from '../api_config'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  Download,
  FileText,
  Printer,
  ChevronRight,
  RefreshCw,
  AlertTriangle
} from 'lucide-react'

interface ReportData {
  job_id: string
  html_report: string
  parsed_jd?: Record<string, unknown>
  salary_intelligence?: Record<string, unknown>
  company_intelligence?: Record<string, unknown>
  interview_intelligence?: Record<string, unknown>
}

interface Props {
  jobId: string
  onBack: () => void
}

export default function ReportViewer({ jobId, onBack }: Props) {
  const [report, setReport] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}/report`, {
          headers: API_HEADERS
        })
        if (!res.ok) {
          const data = await res.json()
          throw new Error(data.detail || 'Failed to load report')
        }
        const data: ReportData = await res.json()
        setReport(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load report')
      } finally {
        setLoading(false)
      }
    }
    fetchReport()
  }, [jobId])

  useEffect(() => {
    if (report && report.parsed_jd) {
      const jd = report.parsed_jd as any;
      const originalTitle = document.title;
      const newTitle = `${jd.company || 'Company'} - ${jd.job_title || 'Position'}`;
      document.title = newTitle;
      return () => {
        document.title = originalTitle;
      };
    }
  }, [report]);

  const handleDownload = () => {
    if (!report) return
    const jd = report.parsed_jd as any
    const filename = `${jd?.company || 'Company'} - ${jd?.job_title || 'Position'}.html`
    const blob = new Blob([report.html_report], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handlePrint = () => {
    if (iframeRef.current?.contentWindow) {
      const jd = report?.parsed_jd as any;
      const title = `${jd?.company || 'Company'} - ${jd?.job_title || 'Position'}`;

      document.title = title;
      iframeRef.current.contentWindow.document.title = title;

      const titleTag = iframeRef.current.contentWindow.document.getElementsByTagName('title')[0];
      if (titleTag) {
        titleTag.innerText = title;
      }

      iframeRef.current.contentWindow.print()
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-500 space-y-4">
        <RefreshCw className="animate-spin text-indigo-500" size={32} />
        <p className="text-sm font-medium italic">Synthesizing intelligence report...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto glass-card p-12 text-center mt-12">
        <div className="w-16 h-16 rounded-full bg-red-400/5 flex items-center justify-center mx-auto mb-6 border border-red-400/20">
          <AlertTriangle className="text-red-400" size={32} />
        </div>
        <h3 className="text-lg font-bold text-white mb-2">Analysis Retrieval Failed</h3>
        <p className="text-slate-400 mb-8">{error}</p>
        <button onClick={onBack} className="px-6 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-white font-bold transition-all flex items-center gap-2 mx-auto border border-white/5">
          <ArrowLeft size={18} />
          Go Back
        </button>
      </div>
    )
  }

  if (!report) return null

  const jd = report.parsed_jd as any

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 'calc(100vh - 64px)' }}>
      {/* Premium Toolbar */}
      <div style={{
        position: 'sticky', top: '64px', zIndex: 40,
        background: 'rgba(241,245,249,0.95)', backdropFilter: 'blur(12px)',
        borderBottom: '1px solid #e2e8f0', padding: '0.75rem 2rem',
        marginBottom: '1.5rem'
      }}>
        <div style={{ maxWidth: '80rem', margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button
              onClick={onBack}
              style={{
                padding: '0.5rem', borderRadius: '0.75rem', background: '#f1f5f9',
                border: '1px solid #e2e8f0', color: '#64748b', cursor: 'pointer',
                display: 'flex', alignItems: 'center', transition: 'all 0.2s ease'
              }}
              onMouseEnter={e => (e.currentTarget.style.background = '#e2e8f0')}
              onMouseLeave={e => (e.currentTarget.style.background = '#f1f5f9')}
            >
              <ArrowLeft size={20} />
            </button>
            <div style={{ minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '10px', fontWeight: 700, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.25rem' }}>
                <span>Intelligence Report</span>
                <ChevronRight size={10} />
                <span>{jd?.company || 'Global Entity'}</span>
              </div>
              <h2 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '28rem' }}>
                {jd?.job_title || 'Parsed Position Results'}
              </h2>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              onClick={handleDownload}
              style={{
                padding: '0.5rem 1rem', borderRadius: '0.75rem', background: '#f8fafc',
                border: '1px solid #e2e8f0', color: '#475569', fontSize: '0.875rem',
                fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f1f5f9')}
              onMouseLeave={e => (e.currentTarget.style.background = '#f8fafc')}
            >
              <FileText size={16} />
              <span>Download HTML</span>
            </button>

            <button
              onClick={() => {
                alert("Pro Tip: To save as high-quality PDF, select 'Save as PDF' in the destination dropdown of the print dialog.");
                handlePrint();
              }}
              style={{
                padding: '0.5rem 1.25rem', borderRadius: '0.75rem',
                background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                border: 'none', color: 'white', fontSize: '0.875rem',
                fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={e => { e.currentTarget.style.filter = 'brightness(1.1)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { e.currentTarget.style.filter = ''; e.currentTarget.style.transform = ''; }}
            >
              <Printer size={16} />
              <span>Export Intelligence</span>
            </button>
          </div>
        </div>
      </div>

      {/* Report Canvas */}
      <div style={{ flex: 1, maxWidth: '80rem', margin: '0 auto', width: '100%', padding: '0 2rem 3rem' }}>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            position: 'relative', overflow: 'hidden', borderRadius: '20px',
            height: 'calc(100vh - 220px)',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.12)',
            border: '1px solid #e2e8f0', background: '#fff'
          }}
        >
          {/* Top accent bar */}
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '3px', background: 'linear-gradient(to right, #6366f1, #a855f7, #6366f1)', zIndex: 1 }} />

          <iframe
            ref={iframeRef}
            srcDoc={report.html_report}
            style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
            title={`${jd?.company || 'Company'} Report`}
          />
        </motion.div>
      </div>
    </div>
  )
}
