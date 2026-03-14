import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Search,
  Link as LinkIcon,
  Loader2
} from 'lucide-react'

interface JobInputProps {
  onJobSubmitted: (jobId: string) => void
}

import { API_HEADERS } from '../api_config'

const JobInput = ({ onJobSubmitted }: JobInputProps) => {
  const [url, setUrl] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!url) return

    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: API_HEADERS,
        body: JSON.stringify({ job_url: url, provider: 'gemini' }),
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Failed to submit job')
      }

      const data = await response.json()
      onJobSubmitted(data.job_id)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <h1 className="text-hero mb-4">Job Intelligence in Seconds</h1>
        <p className="subtext-hero">
          Paste any job URL and get AI-powered salary data, company insights, and interview prep — all in one report.
        </p>
      </div>

      {/* Main Search Bar */}
      <div className="w-full max-w-3xl mb-16">
        <div className="search-container-vibrant">
          <LinkIcon className="search-icon-left" size={20} />
          <input
            type="url"
            placeholder="Paste LinkedIn or job board URL here..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            className="search-input-vibrant"
            disabled={isLoading}
          />
          <button
            onClick={() => handleSubmit()}
            disabled={isLoading || !url}
            className="btn-vibrant px-8 py-3 rounded-2xl"
          >
            {isLoading ? (
              <Loader2 className="animate-spin" size={20} />
            ) : (
              <>
                <Search size={20} />
                <span className="hidden sm:inline">Analyze Job</span>
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-100 text-red-600 rounded-xl text-sm flex items-center gap-2">
            <span className="text-lg">⚠️</span>
            {error}
          </div>
        )}

        <div className="mt-8 flex flex-col items-center gap-4">
          <div className="flex items-center gap-4 opacity-40">
            <div className="h-px w-12 bg-slate-300"></div>
            <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
              Works with
            </span>
            <div className="h-px w-12 bg-slate-300"></div>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3">
            {['LinkedIn', 'Greenhouse', 'Lever', 'Workday', 'Indeed'].map((platform) => (
              <span key={platform} className="platform-badge">
                {platform}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Feature Grid */}
      <div className="feature-grid">
        <div className="card-vibrant p-8 text-center flex flex-col items-center">
          <span className="text-4xl mb-4">💰</span>
          <h3 className="text-lg font-bold mb-2 font-heading">Salary Intelligence</h3>
          <p className="text-sm text-slate-500 leading-relaxed">
            Real H1B + market data for the specific role and location.
          </p>
        </div>

        <div className="card-vibrant p-8 text-center flex flex-col items-center">
          <span className="text-4xl mb-4">🏢</span>
          <h3 className="text-lg font-bold mb-2 font-heading">Company Intel</h3>
          <p className="text-sm text-slate-500 leading-relaxed">
            Deep dive into culture, financials, and recent news.
          </p>
        </div>

        <div className="card-vibrant p-8 text-center flex flex-col items-center">
          <span className="text-4xl mb-4">🎯</span>
          <h3 className="text-lg font-bold mb-2 font-heading">Interview Prep</h3>
          <p className="text-sm text-slate-500 leading-relaxed">
            Personalized Q&A based on the actual job requirements.
          </p>
        </div>
      </div>
    </div>
  )
}

export default JobInput
