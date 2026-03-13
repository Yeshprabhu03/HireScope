import { useState, useEffect, useRef } from 'react'

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
          headers: {
            'X-Pinggy-No-Screen': 'true'
          }
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
      
      // Force change the title in both documents
      document.title = title;
      iframeRef.current.contentWindow.document.title = title;
      
      // Even try to update any existing title tag in the head
      const titleTag = iframeRef.current.contentWindow.document.getElementsByTagName('title')[0];
      if (titleTag) {
        titleTag.innerText = title;
      }

      iframeRef.current.contentWindow.print()
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0', color: '#64748b' }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>📊</div>
        Loading report...
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>❌</div>
        <p style={{ color: '#dc2626', marginBottom: '16px' }}>{error}</p>
        <button onClick={onBack} style={backBtnStyle}>← Back</button>
      </div>
    )
  }

  if (!report) return null

  const jd = report.parsed_jd as Record<string, unknown> | undefined


  return (
    <div style={{ width: '100%', margin: '0 auto' }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button onClick={onBack} style={backBtnStyle}>← Back</button>
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: '700', color: '#1e293b' }}>
              {(jd?.job_title as string) || 'Job Report'}
            </h2>
            {!!jd?.company && (
              <p style={{ color: '#64748b', fontSize: '14px' }}>{jd.company as string}</p>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={handleDownload}
            style={{
              background: '#f8fafc',
              color: '#334155',
              border: '1px solid #e2e8f0',
              padding: '8px 16px',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: '500',
            }}
          >
            📄 HTML
          </button>
          
          <button
            onClick={() => {
              alert("Tip: In the next window, set the 'Destination' to 'Save as PDF' to download this report.");
              handlePrint();
            }}
            style={{
              background: '#2563eb',
              color: 'white',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: '600',
              boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              cursor: 'pointer'
            }}
          >
            💾 Export as PDF
          </button>
        </div>
      </div>

      {/* Report display */}
      <div style={{
        background: 'white',
        borderRadius: '12px',
        border: '1px solid #e2e8f0',
        overflow: 'hidden',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}>
        <iframe
          ref={iframeRef}
          srcDoc={report.html_report}
          style={{
            width: '100%',
            height: '800px',
            border: 'none',
          }}
          title={`${(report.parsed_jd as any)?.company || 'Company'} - ${(report.parsed_jd as any)?.job_title || 'Position'}`}
        />
      </div>
    </div>
  )
}

const backBtnStyle: React.CSSProperties = {
  background: 'white',
  color: '#374151',
  border: '1px solid #e2e8f0',
  padding: '8px 16px',
  borderRadius: '6px',
  fontSize: '13px',
  fontWeight: '500',
}
