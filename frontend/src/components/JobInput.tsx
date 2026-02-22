import { useState, FormEvent } from 'react'

interface Props {
  onJobSubmitted: (jobId: string) => void
}


export default function JobInput({ onJobSubmitted }: Props) {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedModel, setSelectedModel] = useState('gemini')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!url.trim()) {
      setError('Please enter a job URL')
      return
    }
    setError('')
    setLoading(true)

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_url: url.trim(),
          provider: selectedModel
        }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to submit job')
      }
      const data = await res.json()
      onJobSubmitted(data.job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit job')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: '680px', margin: '40px auto' }}>
      {/* Hero */}
      <div style={{ textAlign: 'center', marginBottom: '40px' }}>
        <h1 style={{ fontSize: '36px', fontWeight: '800', color: '#1e293b', marginBottom: '12px' }}>
          Job Intelligence in Seconds
        </h1>
        <p style={{ fontSize: '18px', color: '#64748b', lineHeight: '1.6' }}>
          Paste any job URL and get AI-powered salary data, company insights, and interview prep — all in one report.
        </p>
      </div>

      {/* Input card */}
      <div style={{
        background: 'white',
        borderRadius: '16px',
        padding: '32px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
        border: '1px solid #e2e8f0',
      }}>
        <form onSubmit={handleSubmit}>

          {/* Model Selector */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontWeight: '600', marginBottom: '8px', color: '#374151', fontSize: '14px' }}>
              Choose AI Model
            </label>
            <div style={{ display: 'flex', gap: '12px' }}>
              {[
                { id: 'gemini', name: 'Gemini 2.0 Flash', desc: 'Fast & Free', icon: '⚡' },
                { id: 'anthropic', name: 'Claude 3.5 Sonnet', desc: 'Best Reasoning', icon: '🧠' },
                { id: 'openai', name: 'GPT-4o', desc: 'Standard', icon: '🤖' },
              ].map(model => (
                <div
                  key={model.id}
                  onClick={() => setSelectedModel(model.id)}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: '8px',
                    border: `2px solid ${selectedModel === model.id ? '#2563eb' : '#e2e8f0'}`,
                    background: selectedModel === model.id ? '#eff6ff' : 'white',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  <div style={{ fontWeight: '600', fontSize: '14px', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>{model.icon}</span> {model.name}
                  </div>
                  <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                    {model.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <label style={{ display: 'block', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>
            Job Posting URL
          </label>
          <div style={{ display: 'flex', gap: '12px' }}>
            <input
              type="url"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://www.linkedin.com/jobs/view/..."
              disabled={loading}
              style={{
                flex: 1,
                padding: '12px 16px',
                border: `2px solid ${error ? '#ef4444' : '#e2e8f0'}`,
                borderRadius: '8px',
                fontSize: '15px',
                outline: 'none',
                transition: 'border-color 0.2s',
              }}
              onFocus={e => { if (!error) e.target.style.borderColor = '#2563eb' }}
              onBlur={e => { if (!error) e.target.style.borderColor = '#e2e8f0' }}
            />
            <button
              type="submit"
              disabled={loading}
              style={{
                background: loading ? '#94a3b8' : 'linear-gradient(135deg, #2563eb, #7c3aed)',
                color: 'white',
                border: 'none',
                padding: '12px 24px',
                borderRadius: '8px',
                fontSize: '15px',
                fontWeight: '600',
                whiteSpace: 'nowrap',
                transition: 'opacity 0.2s',
              }}
            >
              {loading ? '⏳ Analyzing...' : '🔍 Analyze'}
            </button>
          </div>
          {error && (
            <p style={{ color: '#ef4444', fontSize: '13px', marginTop: '6px' }}>{error}</p>
          )}
        </form>

        {/* Example URLs */}
        <div style={{ marginTop: '20px' }}>
          <p style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '8px' }}>
            Supported platforms:
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {['LinkedIn', 'Greenhouse', 'Lever', 'Workday', 'Indeed'].map(platform => (
              <span key={platform} style={{
                background: '#f1f5f9',
                color: '#475569',
                padding: '4px 12px',
                borderRadius: '20px',
                fontSize: '12px',
                fontWeight: '500',
              }}>{platform}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Feature highlights */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr',
        gap: '16px',
        marginTop: '24px',
      }}>
        {[
          { icon: '💰', title: 'Salary Intelligence', desc: 'Real H1B + market data' },
          { icon: '🏢', title: 'Company Intel', desc: 'CEO, culture, news' },
          { icon: '🎯', title: 'Interview Prep', desc: 'RAG-powered Q&A' },
        ].map(f => (
          <div key={f.title} style={{
            background: 'white',
            borderRadius: '10px',
            padding: '20px',
            border: '1px solid #e2e8f0',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '28px', marginBottom: '8px' }}>{f.icon}</div>
            <div style={{ fontWeight: '600', fontSize: '14px', color: '#1e293b' }}>{f.title}</div>
            <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
