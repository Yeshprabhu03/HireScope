import { useState, useRef, ChangeEvent } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  Link as LinkIcon,
  Loader2,
  Upload,
  FileText,
  X
} from 'lucide-react'

interface JobInputProps {
  onJobSubmitted: (jobId: string) => void
  sessionId: string
}

import { API_HEADERS } from '../api_config'

const JobInput = ({ onJobSubmitted, sessionId }: JobInputProps) => {
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isResumeLoading, setIsResumeLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [userContext, setUserContext] = useState('')
  const [showContext, setShowContext] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const resumeFileInputRef = useRef<HTMLInputElement>(null)
  const isSubmittingRef = useRef(false)  // synchronous guard against double-submit

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setUrl('') // Mutually exclusive
    }
  }

  const handleUrlChange = (e: ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value)
    setFile(null) // Mutually exclusive
  }

  const handleResumeUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const resumeFile = e.target.files[0]
      setIsResumeLoading(true)
      setError(null)

      try {
        const formData = new FormData()
        formData.append('file', resumeFile)

        const uploadHeaders: Record<string, string> = { ...API_HEADERS }
        delete uploadHeaders['Content-Type']

        const response = await fetch('/api/utils/parse-resume', {
          method: 'POST',
          headers: uploadHeaders,
          body: formData,
        })

        if (!response.ok) {
          throw new Error('Failed to parse resume')
        }

        const data = await response.json()
        setUserContext(data.text)
        if (!showContext) setShowContext(true)
      } catch (err: any) {
        setError(err.message)
      } finally {
        setIsResumeLoading(false)
        if (resumeFileInputRef.current) {
          resumeFileInputRef.current.value = ''
        }
      }
    }
  }

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if ((!url && !file) || isSubmittingRef.current) return

    isSubmittingRef.current = true
    setIsLoading(true)
    setError(null)

    try {
      let response;
      if (file) {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('provider', 'openai')
        if (sessionId) formData.append('session_id', sessionId)

        const uploadHeaders: Record<string, string> = { ...API_HEADERS }
        delete uploadHeaders['Content-Type']

        response = await fetch('/api/analyze/pdf', {
          method: 'POST',
          headers: uploadHeaders,
          body: formData,
        })
      } else {
        response = await fetch('/api/analyze', {
          method: 'POST',
          headers: API_HEADERS,
          body: JSON.stringify({
            job_url: url,
            provider: 'openai',
            session_id: sessionId,
            user_context: userContext || undefined
          }),
        })
      }

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Failed to submit job')
      }

      const data = await response.json()
      setUrl('')
      setFile(null)
      onJobSubmitted(data.job_id)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsLoading(false)
      isSubmittingRef.current = false
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
        <form onSubmit={handleSubmit} className="search-container-vibrant flex-col sm:flex-row gap-4">
          {!file ? (
            <>
              <LinkIcon className="search-icon-left hidden sm:block" size={20} />
              <input
                type="url"
                placeholder="Paste LinkedIn or job board URL here..."
                value={url}
                onChange={handleUrlChange}
                className="search-input-vibrant"
                disabled={isLoading}
              />
            </>
          ) : (
            <div className="flex-1 flex items-center justify-between bg-white border border-slate-200 rounded-2xl px-6 py-4 mr-0 sm:mr-2 shadow-sm w-full">
              <div className="flex items-center gap-3 text-indigo-700 font-medium overflow-hidden">
                <FileText size={24} className="text-indigo-500 flex-shrink-0" />
                <span className="truncate max-w-[200px] sm:max-w-xs">{file.name}</span>
              </div>
              <button
                type="button"
                onClick={() => setFile(null)}
                className="text-slate-400 hover:text-red-500 transition-colors flex-shrink-0 ml-2"
                disabled={isLoading}
              >
                <X size={20} />
              </button>
            </div>
          )}

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="application/pdf"
            className="hidden"
          />

          <div className="flex gap-2 w-full sm:w-auto mt-4 sm:mt-0 justify-end">
            {!file && !url && (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
                className="bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-colors px-6 py-3 rounded-2xl flex items-center justify-center whitespace-nowrap shadow-sm hover:shadow-md"
                title="Upload PDF Job Description"
              >
                <Upload size={20} />
              </button>
            )}

            <button
              type="submit"
              disabled={isLoading || (!url && !file)}
              className="btn-vibrant px-8 py-3 rounded-2xl w-full sm:w-auto flex-1 sm:flex-none justify-center"
            >
              {isLoading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <>
                  <Search size={20} />
                  <span className="hidden sm:inline">Analyze Job</span>
                  <span className="sm:hidden">Analyze</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Personalized Context (Career-Ops) */}
        {!file && (
          <div className="mt-4 w-full">
            <button
              type="button"
              onClick={() => setShowContext(!showContext)}
              className="text-[11px] font-bold text-slate-400 uppercase tracking-widest hover:text-indigo-500 transition-colors flex items-center gap-2 mb-3"
            >
              {showContext ? '− Hide Personalized Context' : '+ Add Resume / Skills (for Fit Score)'}
            </button>
            <input
              type="file"
              ref={resumeFileInputRef}
              onChange={handleResumeUpload}
              accept="application/pdf"
              className="hidden"
            />
            <AnimatePresence>
              {showContext && (
                <motion.div
                  key="user-context-area"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden space-y-3 pb-2"
                >
                  <div className="flex items-center justify-between px-1">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-tight">
                      Resume Content / Skills Gap Analysis
                    </p>
                    <button
                      type="button"
                      onClick={() => resumeFileInputRef.current?.click()}
                      disabled={isLoading || isResumeLoading}
                      className="bg-indigo-600 text-white hover:bg-indigo-700 transition-all px-3 py-1.5 rounded-lg shadow-sm hover:shadow-md flex items-center gap-2 text-[10px] font-bold"
                    >
                      {isResumeLoading ? (
                        <Loader2 className="animate-spin" size={14} />
                      ) : (
                        <>
                          <Upload size={14} />
                          <span>UPLOAD PDF RESUME</span>
                        </>
                      )}
                    </button>
                  </div>

                  <textarea
                    placeholder="Paste your resume summary here, or click 'Upload PDF' to extract it automatically..."
                    value={userContext}
                    onChange={(e) => setUserContext(e.target.value)}
                    className="w-full bg-white border border-slate-200 rounded-2xl p-4 text-sm text-slate-600 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all min-h-[140px] shadow-sm"
                    disabled={isLoading || isResumeLoading}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

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
