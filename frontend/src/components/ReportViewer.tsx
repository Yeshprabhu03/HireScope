import { useState, useEffect, useRef } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

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
  const [editMode, setEditMode] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}/report`)
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

  const editor = useEditor({
    extensions: [StarterKit],
    content: report?.html_report || '',
    editable: editMode,
  })

  useEffect(() => {
    if (editor && report?.html_report) {
      editor.commands.setContent(report.html_report)
    }
  }, [editor, report])

  useEffect(() => {
    if (editor) {
      editor.setEditable(editMode)
    }
  }, [editor, editMode])

  const handlePrint = () => {
    if (iframeRef.current?.contentWindow) {
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
  const sal = report.salary_intelligence as Record<string, unknown> | undefined

  const salaryChartData = sal && sal.min && sal.median && sal.max ? [
    { name: 'Min', value: sal.min as number },
    { name: 'Median', value: sal.median as number },
    { name: 'Max', value: sal.max as number },
  ] : null

  const chartColors = ['#93c5fd', '#3b82f6', '#1d4ed8']

  const fmtUSD = (v: number) =>
    v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
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
            {jd?.company && (
              <p style={{ color: '#64748b', fontSize: '14px' }}>{jd.company as string}</p>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setEditMode(e => !e)}
            style={{
              background: editMode ? '#f59e0b' : 'white',
              color: editMode ? 'white' : '#374151',
              border: '1px solid #e2e8f0',
              padding: '8px 16px',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: '500',
            }}
          >
            {editMode ? '✏️ Editing' : '✏️ Edit'}
          </button>
          <button
            onClick={handlePrint}
            style={{
              background: 'white',
              color: '#374151',
              border: '1px solid #e2e8f0',
              padding: '8px 16px',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: '500',
            }}
          >
            🖨️ Print / PDF
          </button>
        </div>
      </div>

      {/* Salary quick-view chart */}
      {salaryChartData && (
        <div style={{
          background: 'white',
          borderRadius: '12px',
          border: '1px solid #e2e8f0',
          padding: '20px 24px',
          marginBottom: '16px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        }}>
          <div style={{ fontSize: '15px', fontWeight: '600', color: '#2563eb', marginBottom: '12px' }}>
            💰 Salary Range
            {sal?.data_label && (
              <span style={{ fontSize: '12px', fontWeight: '400', color: '#d97706', marginLeft: '10px' }}>
                ⚠ {sal.data_label as string}
              </span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={salaryChartData} layout="vertical" margin={{ left: 0, right: 60 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tickFormatter={fmtUSD} tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 13, fontWeight: 600 }} width={56} />
              <Tooltip formatter={(v: number) => [`$${v.toLocaleString()}`, 'Salary']} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {salaryChartData.map((_, i) => <Cell key={i} fill={chartColors[i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
            Sources: {Array.isArray(sal?.sources_used) ? (sal.sources_used as string[]).join(', ') : 'Market estimate only'}
            &nbsp;·&nbsp; Confidence: {sal?.confidence_score ? `${Math.round((sal.confidence_score as number) * 100)}%` : 'N/A'}
          </div>
        </div>
      )}

      {/* Report display */}
      {editMode ? (
        <div style={{
          background: 'white',
          borderRadius: '12px',
          border: '2px solid #f59e0b',
          padding: '24px',
          minHeight: '600px',
        }}>
          <div style={{
            background: '#fffbeb',
            padding: '8px 12px',
            borderRadius: '6px',
            marginBottom: '16px',
            fontSize: '13px',
            color: '#92400e',
          }}>
            ✏️ Edit mode — changes are local only
          </div>
          <EditorContent editor={editor} />
        </div>
      ) : (
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
            title="HireScope Report"
          />
        </div>
      )}
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
