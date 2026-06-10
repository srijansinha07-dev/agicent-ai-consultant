import {
  postConsultation,
  getCalendarSlots,
} from '@/services/api'

import { useEffect, useMemo, useState } from 'react'
import { BookingSlotPicker } from './BookingSlotPicker'



type ConversationHistoryItem = { role: string; content: string }

type ConsultationCtaVariant = 'request' | 'connect'

interface ConsultationModalProps {
  open: boolean
  variant: ConsultationCtaVariant
  sessionId: string
  history: ConversationHistoryItem[]
  defaultProjectDescription?: string
  defaultBudget?: string
  defaultTimeline?: string
  onClose: () => void
  onSuccess: (payload: { consultationId: string; summary: string }) => void
}


function validateEmail(email: string): boolean {
  // Simple but robust enough for client-side gating.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
}

export function ConsultationModal({
  open,
  variant,
  sessionId,
  history,
  defaultProjectDescription,
  defaultBudget,
  defaultTimeline,
  onClose,
  onSuccess,
}: ConsultationModalProps) {

  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle')
  const [slots, setSlots] = useState<any[]>([])
  const [loadingSlots, setLoadingSlots] = useState(false)

  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [company, setCompany] = useState('')
  const [projectDescription, setProjectDescription] = useState('')
  const [budget, setBudget] = useState(defaultBudget ?? '')
  const [timeline, setTimeline] = useState(defaultTimeline ?? '')


  const title = variant === 'connect' ? 'Connect with Agicent' : 'Request Consultation'

  const payloadHistory = useMemo(() => {
    // Keep payload small enough for fast submission while preserving intent.
    const compact = history.filter((h) => h.content.trim()).slice(-20)
    return compact
  }, [history])

  useEffect(() => {
    if (!open) return

    setStatus('idle')
    setError(null)

    setName('')
    setEmail('')
    setCompany('')
    setProjectDescription(defaultProjectDescription ?? '')
    setBudget(defaultBudget ?? '')
    setTimeline(defaultTimeline ?? '')
  }, [open, defaultProjectDescription, defaultBudget, defaultTimeline])


  if (!open) return null

  const canSubmit =
    name.trim().length >= 2 &&
    validateEmail(email) &&
    company.trim().length >= 2 &&
    projectDescription.trim().length >= 10 &&
    status !== 'submitting'

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return

    setStatus('submitting')
    setError(null)

    try {
      const res = await postConsultation({
        name: name.trim(),
        email: email.trim(),
        company: company.trim(),
        project_description: projectDescription.trim(),
        budget: budget.trim() ? budget.trim() : undefined,
        timeline: timeline.trim() ? timeline.trim() : undefined,
        conversation_history: payloadHistory,
        session_id: sessionId,
      })

      if (!res.ok) {
        setStatus('error')
        setError(res.error ?? 'Submission failed. Please try again.')
        return
      }

      // Persist attendee info so BookingSlotPicker can pre-fill without re-asking.
      try {
        sessionStorage.setItem(
          'agicent_attendee_info',
          JSON.stringify({
            name: name.trim(),
            email: email.trim(),
            company: company.trim(),
            summary: projectDescription.trim(),
          }),
        )
      } catch {
        // ignore storage errors
      }

      setStatus('success')
      onSuccess({
        consultationId: res.consultation_id ?? 'unknown',
        summary: res.summary ?? '',
      })

      try {
        setLoadingSlots(true)
      
        const slotData = await getCalendarSlots()
      
        setSlots(slotData.slots ?? [])
      } catch (err) {
        console.error(err)
      } finally {
        setLoadingSlots(false)
      }
    } catch (err) {
      setStatus('error')
      const message = err instanceof Error ? err.message : 'Submission failed. Please try again.'
      setError(message)
    }
  }


  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2147485000,
        background: 'rgba(20, 18, 26, 0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '18px',
      }}
      onMouseDown={(e) => {
        if (e.currentTarget === e.target) onClose()
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '560px',
          background: 'var(--bg)',
          borderRadius: '16px',
          border: '1px solid var(--border-strong)',
          boxShadow: '0 20px 80px rgba(0,0,0,0.35)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            background: 'var(--agicent-gradient)',
            color: 'white',
            padding: '14px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          <div style={{ fontWeight: 700, letterSpacing: '-0.01em' }}>{title}</div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              border: 'none',
              background: 'rgba(255,255,255,0.18)',
              color: 'white',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
              <path d="M1.5 1.5L10.5 10.5M10.5 1.5L1.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>

        </div>

        <form onSubmit={onSubmit} style={{ padding: '16px' }}>
          {status === 'success' ? (
           <div style={{ padding: '8px 4px 16px' }}>
           <div style={{ fontWeight: 700, marginBottom: 8 }}>
             Consultation Request Submitted
           </div>
         
           <div
             style={{
               color: 'var(--text-2)',
               fontSize: 14,
               lineHeight: 1.6,
               marginBottom: 12,
             }}
           >
             Agicent has received your request. Book a discovery call below.
           </div>
         
           {loadingSlots ? (
             <div style={{ fontSize: 13, color: 'var(--text-2)', padding: '8px 0' }}>
               Loading available times…
             </div>
           ) : slots.length > 0 ? (
             <BookingSlotPicker
               slots={slots}
               consultationSummary={projectDescription.trim()}
             />
           ) : (
             <div style={{ fontSize: 13, color: 'var(--text-2)' }}>
               No slots available right now. Our team will reach out to schedule.
             </div>
           )}
         </div>
          ) : (
            <>
              {error && (
                <div
                  style={{
                    marginBottom: 12,
                    padding: '10px 12px',
                    borderRadius: 12,
                    background: 'rgba(239,68,68,0.1)',
                    border: '1px solid rgba(239,68,68,0.2)',
                    color: '#f87171',
                    fontSize: 13,
                    lineHeight: 1.4,
                  }}
                >
                  {error}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <Field label="Name" required>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                    style={inputStyle}
                    disabled={status === 'submitting'}
                  />
                </Field>
                <Field label="Email" required>
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    style={inputStyle}
                    disabled={status === 'submitting'}
                  />
                </Field>
              </div>

              <div style={{ marginTop: 12 }}>
                <Field label="Company" required>
                  <input
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="Company / Startup"
                    style={inputStyle}
                    disabled={status === 'submitting'}
                  />
                </Field>
              </div>

              <div style={{ marginTop: 12 }}>
                <Field label="Project Description" required>
                  <textarea
                    value={projectDescription}
                    onChange={(e) => setProjectDescription(e.target.value)}
                    placeholder="What are you building, what does success look like, and what constraints do you have?"
                    style={{ ...inputStyle, minHeight: 110, resize: 'vertical' }}
                    disabled={status === 'submitting'}
                  />
                </Field>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
                <Field label="Budget (optional)">
                  <input
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                    placeholder="$ range or estimate"
                    style={inputStyle}
                    disabled={status === 'submitting'}
                  />
                </Field>
                <Field label="Timeline (optional)">
                  <input
                    value={timeline}
                    onChange={(e) => setTimeline(e.target.value)}
                    placeholder="e.g. 8-12 weeks"
                    style={inputStyle}
                    disabled={status === 'submitting'}
                  />
                </Field>
              </div>

              <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={status === 'submitting'}
                  style={{
                    padding: '10px 14px',
                    borderRadius: 12,
                    border: '1px solid var(--border-strong)',
                    background: 'var(--bg-2)',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={!canSubmit}
                  style={{
                    padding: '10px 14px',
                    borderRadius: 12,
                    border: 'none',
                    background: canSubmit ? 'var(--agicent-gradient-trigger)' : 'var(--bg-4)',
                    color: canSubmit ? 'white' : 'var(--text-3)',
                    cursor: canSubmit ? 'pointer' : 'not-allowed',
                    fontWeight: 700,
                    minWidth: 170,
                  }}
                >
                  {status === 'submitting' ? 'Submitting...' : 'Submit request'}
                </button>
              </div>
            </>
          )}
        </form>
      </div>
    </div>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 12,
  border: '1px solid var(--border-strong)',
  background: 'var(--bg-2)',
  color: 'var(--text)',
  fontSize: 14,
  outline: 'none',
  fontFamily: 'var(--font)',
}

function Field({
  label,
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: 'var(--text-2)' }}>
      <div style={{ fontWeight: 700 }}>
        {label}
        {required ? <span style={{ color: 'var(--accent)' }}> *</span> : null}
      </div>
      {children}
    </label>
  )
}

