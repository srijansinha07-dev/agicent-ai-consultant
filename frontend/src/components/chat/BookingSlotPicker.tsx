/**
 * BookingSlotPicker.tsx
 * ─────────────────────
 * Calendly-style 3-step booking flow:
 *   Step 1 — Day selection  (pill per available business day)
 *   Step 2 — Time selection (grid of 30-min interval slots for the chosen day)
 *   Step 3 — Confirmation   (attendee summary + confirm button)
 */
import { useState, useMemo } from 'react'

import type { SlotOption } from '@/types/chat'
import { apiClient, USER_ID_HEADER } from '@/services/api'
import { env } from '@/config/env'

// ── Types ──────────────────────────────────────────────────────────────────

interface AttendeeInfo {
  name: string
  email: string
  company: string
  summary: string
}

interface BookingSlotPickerProps {
  slots: SlotOption[]
  consultationSummary?: string
}

interface BookingResult {
  booking_id: string
  consultant_name: string
  html_link:  string
  meet_link:  string
  summary:    string
  dayFull:    string
  timeStr:    string
  timezone:   string
}

type Step = 'day' | 'time' | 'confirm'


// ── IST display helpers ────────────────────────────────────────────────────

const IST_TZ = 'Asia/Kolkata'

/** "YYYY-MM-DD" in IST — used as the grouping key. */
function slotDayKey(startIso: string): string {
  return new Date(startIso).toLocaleDateString('en-CA', { timeZone: IST_TZ })
}

/** "Mon Jun 9" — day pill label. */
function slotDayPill(startIso: string): string {
  return new Date(startIso).toLocaleDateString('en-US', {
    weekday: 'short',
    month:   'short',
    day:     'numeric',
    timeZone: IST_TZ,
  })
}

/** "Monday, June 9" — used in step headings. */
function slotDayFull(startIso: string): string {
  return new Date(startIso).toLocaleDateString('en-US', {
    weekday: 'long',
    month:   'long',
    day:     'numeric',
    timeZone: IST_TZ,
  })
}

/** "10:00 AM" — time chip label. */
function slotTime(startIso: string): string {
  return new Date(startIso).toLocaleTimeString('en-US', {
    hour:     'numeric',
    minute:   '2-digit',
    hour12:   true,
    timeZone: IST_TZ,
  })
}

// ── Attendee helpers ───────────────────────────────────────────────────────

function loadAttendeeInfo(): AttendeeInfo | null {
  try {
    const raw = sessionStorage.getItem('agicent_attendee_info')
    if (!raw) return null
    return JSON.parse(raw) as AttendeeInfo
  } catch {
    return null
  }
}

function validateEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
}

// ── Component ──────────────────────────────────────────────────────────────

export function BookingSlotPicker({ slots, consultationSummary }: BookingSlotPickerProps) {
  const [step, setStep]               = useState<Step>('day')
  const [selectedDayKey, setDayKey]   = useState<string | null>(null)
  const [selectedSlot, setSlot]       = useState<SlotOption | null>(null)
  const [status, setStatus]           = useState<'idle' | 'booking' | 'success' | 'error' | 'cancelled_success'>('idle')
  const [bookingResult, setResult]    = useState<BookingResult | null>(null)
  const [errorMsg, setError]          = useState<string | null>(null)
  
  const [isRescheduling, setIsRescheduling] = useState(false)
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null)

  const [attendee, setAttendee] = useState<AttendeeInfo>(() => {
    return loadAttendeeInfo() ?? { name: '', email: '', company: '', summary: '' }
  })

  const hasStoredAttendee = Boolean(loadAttendeeInfo())


  // ── Derived slot groupings ────────────────────────────────────────────────

  const slotsByDay = useMemo(() => {
    const map = new Map<string, SlotOption[]>()
    for (const s of slots) {
      const key = slotDayKey(s.start)
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(s)
    }
    return map
  }, [slots])

  const orderedDays = useMemo(
    () => Array.from(slotsByDay.keys()).sort(),
    [slotsByDay],
  )

  const timeSlotsForDay = useMemo(
    () => (selectedDayKey ? (slotsByDay.get(selectedDayKey) ?? []) : []),
    [selectedDayKey, slotsByDay],
  )

  // ── Booking action ────────────────────────────────────────────────────────

  const canBook =
    selectedSlot !== null &&
    attendee.name.trim().length >= 2 &&
    validateEmail(attendee.email) &&
    status !== 'booking'

  async function handleBook() {
    if (!canBook || !selectedSlot) return
    setStatus('booking')
    setError(null)
    try {
      if (isRescheduling && bookingResult?.booking_id) {
        // Cancel the old booking first
        const cancelResp = await apiClient.post(`/api/calendar/bookings/${bookingResult.booking_id}/cancel`, {}, {
          headers: { [USER_ID_HEADER]: env.userId }
        })
        if (!cancelResp.data.ok) {
          setStatus('error')
          setError(cancelResp.data.error ?? 'Failed to cancel old booking. Reschedule aborted.')
          return
        }
      }

      const { data } = await apiClient.post(
        '/api/calendar/book',
        {
          start_iso:      selectedSlot.start,
          end_iso:        selectedSlot.end,
          attendee_email: attendee.email.trim(),
          attendee_name:  attendee.name.trim(),
          topic_summary:  consultationSummary || attendee.summary || '',
        },
        { headers: { [USER_ID_HEADER]: env.userId } },
      )

      if (!data.ok) {
        setStatus('error')
        setError(data.error ?? 'Booking failed. Please try again.')
        return
      }

      const dayFull  = slotDayFull(selectedSlot.start)
      const timeStr   = slotTime(selectedSlot.start)
      const tz        = 'IST'

      setResult({
        booking_id:      data.booking_id ?? '',
        consultant_name: data.consultant_name ?? '',
        html_link:       data.html_link ?? '',
        meet_link:       data.meet_link ?? '',
        summary:         data.summary ?? '',
        dayFull,
        timeStr,
        timezone: tz,
      })

      // Persist booking state to sessionStorage so the chat assistant can access it
      try {
        const bookingState = {
          date:       dayFull,
          time:       `${timeStr} ${tz}`,
          timezone:   tz,
          consultant: data.consultant_name ?? '',
          meet_link:  data.meet_link ?? '',
          booking_id: data.booking_id ?? '',
          status:     'confirmed',
        }
        sessionStorage.setItem('agicent_active_booking', JSON.stringify(bookingState))
      } catch {
        // ignore storage errors
      }

      setIsRescheduling(false)
      setStatus('success')
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Booking failed. Please try again.')
    }
  }

  async function handleCancel() {
    if (!bookingResult?.booking_id) return
    setStatus('booking')
    setError(null)
    try {
      const { data } = await apiClient.post(`/api/calendar/bookings/${bookingResult.booking_id}/cancel`, {}, {
        headers: { [USER_ID_HEADER]: env.userId }
      })
      if (!data.ok) {
        setStatus('error')
        setError(data.error ?? 'Failed to cancel booking.')
        return
      }
      setIsRescheduling(false)
      setShowCancelConfirm(false)
      setStatus('cancelled_success')
      // Clear stored booking state so the assistant knows booking is cancelled
      try { sessionStorage.removeItem('agicent_active_booking') } catch { /* ignore */ }
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Failed to cancel booking.')
    }
  }

  function handleCopyMeetLink() {
    if (!bookingResult?.meet_link) return
    navigator.clipboard.writeText(bookingResult.meet_link)
    setCopyFeedback('Meet link copied to clipboard!')
    setTimeout(() => setCopyFeedback(null), 3000)
  }

  function handleCopyInvitation() {
    if (!bookingResult) return
    const details = [
      `Agicent Discovery Call`,
      `Date: ${bookingResult.dayFull}`,
      `Time: ${bookingResult.timeStr} ${bookingResult.timezone}`,
      bookingResult.consultant_name ? `Consultant: ${bookingResult.consultant_name}` : null,
      bookingResult.meet_link ? `Google Meet: ${bookingResult.meet_link}` : null,
    ].filter(Boolean).join('\n')

    navigator.clipboard.writeText(details)
    setCopyFeedback('Invitation details copied!')
    setTimeout(() => setCopyFeedback(null), 3000)
  }

  function reset() {
    setStep('day')
    setDayKey(null)
    setSlot(null)
    setStatus('idle')
    setResult(null)
    setError(null)
    setIsRescheduling(false)
    setShowCancelConfirm(false)
    setShowDetails(false)
    setCopyFeedback(null)
  }

  // ── Shared style constants ────────────────────────────────────────────────

  const pillBase: React.CSSProperties = {
    padding:    '8px 14px',
    borderRadius: 9,
    border:     '1px solid var(--border-strong)',
    background: 'var(--bg-2)',
    color:      'var(--text)',
    fontWeight: 500,
    fontSize:   13,
    cursor:     'pointer',
    transition: 'all 0.15s ease',
    whiteSpace: 'nowrap' as const,
  }

  const backBtn: React.CSSProperties = {
    display:     'flex',
    alignItems:  'center',
    gap:          6,
    background:  'none',
    border:      'none',
    color:       'var(--text-2)',
    fontSize:    12,
    fontWeight:  600,
    cursor:      'pointer',
    marginBottom: 10,
    padding:     0,
    letterSpacing: '0.01em',
  }

  const sectionLabel: React.CSSProperties = {
    fontSize:      11,
    fontWeight:    700,
    color:         'var(--text-2)',
    marginBottom:  8,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.07em',
  }

  const miniBtnStyle: React.CSSProperties = {
    padding: '6px 10px',
    borderRadius: 6,
    border: '1px solid var(--border-strong)',
    background: 'var(--bg-2)',
    color: 'var(--text)',
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background 0.1s ease',
  }

  const rescheduleBanner = isRescheduling && bookingResult ? (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '8px 12px',
      borderRadius: 10,
      background: 'rgba(245,158,11,0.08)',
      border: '1px solid rgba(245,158,11,0.2)',
      marginBottom: 12,
      fontSize: 12,
      color: 'var(--text)',
    }}>
      <span>🔄 Rescheduling call...</span>
      <button
        type="button"
        onClick={() => setShowCancelConfirm(true)}
        style={{
          background: 'none',
          border: 'none',
          color: '#ef4444',
          fontSize: 11,
          fontWeight: 700,
          cursor: 'pointer',
          textDecoration: 'underline',
          padding: 0,
        }}
      >
        Cancel Meeting
      </button>
    </div>
  ) : null

  // ─────────────────────────────────────────────────────────────────────────
  // Render: Cancelled / Confirmation screens
  // ─────────────────────────────────────────────────────────────────────────

  if (status === 'cancelled_success') {
    return (
      <div style={{
        marginTop:  14,
        padding:    '16px',
        borderRadius: 14,
        border:     '1px solid rgba(239,68,68,0.3)',
        background: 'rgba(239,68,68,0.08)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: 18, color: '#ef4444' }}>✓</span>
          <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>
            Booking Cancelled
          </span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 14, lineHeight: 1.5 }}>
          Your discovery call has been successfully cancelled. The Google Calendar event has been removed.
        </div>
        <button
          type="button"
          onClick={reset}
          style={{
            padding:    '9px 14px',
            borderRadius: 10,
            border:     '1px solid var(--border-strong)',
            background: 'var(--bg-2)',
            color:      'var(--text)',
            fontWeight: 600,
            fontSize:   13,
            cursor:     'pointer',
          }}
        >
          Book a New Call
        </button>
      </div>
    )
  }

  if (showCancelConfirm && bookingResult) {
    return (
      <div style={{
        marginTop: 12,
        padding: '16px',
        borderRadius: 14,
        border: '1px solid var(--border-strong)',
        background: 'var(--bg-2)',
      }}>
        <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text)', marginBottom: 10 }}>
          Cancel Booking?
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 14, lineHeight: 1.5 }}>
          Are you sure you want to cancel your discovery call scheduled for{' '}
          <strong style={{ color: 'var(--text)' }}>{bookingResult.dayFull}</strong> at{' '}
          <strong style={{ color: 'var(--text)' }}>{bookingResult.timeStr} IST</strong>?
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={handleCancel}
            style={{
              padding: '9px 14px',
              borderRadius: 10,
              border: 'none',
              background: '#ef4444',
              color: 'white',
              fontWeight: 700,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            Yes, Cancel Booking
          </button>
          <button
            type="button"
            onClick={() => setShowCancelConfirm(false)}
            style={{
              padding: '9px 14px',
              borderRadius: 10,
              border: '1px solid var(--border-strong)',
              background: 'var(--bg-2)',
              color: 'var(--text)',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            No, Keep Booking
          </button>
        </div>
      </div>
    )
  }

  if (status === 'success' && bookingResult) {
    return (
      <div style={{
        marginTop:  14,
        padding:    '16px',
        borderRadius: 14,
        border:     '1px solid rgba(34,197,94,0.3)',
        background: 'rgba(34,197,94,0.08)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: 18, color: '#22c55e' }}>✓</span>
          <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>
            Discovery Call Booked
          </span>
        </div>

        <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.75 }}>
          <ConfirmRow label="Date"  value={bookingResult.dayFull} />
          <ConfirmRow label="Time"  value={`${bookingResult.timeStr} IST`} />
          <ConfirmRow label="Name"  value={attendee.name} />
          <ConfirmRow label="Email" value={attendee.email} />
        </div>

        {/* Calendar invite note */}
        <div style={{
          marginTop: 10,
          padding: '8px 10px',
          borderRadius: 8,
          background: 'rgba(59,130,246,0.08)',
          border: '1px solid rgba(59,130,246,0.18)',
          fontSize: 12,
          color: 'var(--text-2)',
        }}>
          📧 A calendar invite has been sent to <strong style={{ color: 'var(--text)' }}>{attendee.email}</strong>
        </div>

        {showDetails && (
          <div style={{
            marginTop: 12,
            padding: '12px',
            borderRadius: 10,
            background: 'var(--bg-3, rgba(0,0,0,0.05))',
            border: '1px solid var(--border-strong)',
            fontSize: 13,
            color: 'var(--text)',
            lineHeight: 1.6,
          }}>
            <div style={{ fontWeight: 700, marginBottom: 8, fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-2)' }}>Meeting Details</div>
            <ConfirmRow label="Date" value={bookingResult.dayFull} />
            <ConfirmRow label="Time" value={bookingResult.timeStr} />
            <ConfirmRow label="Timezone" value={bookingResult.timezone} />
            {bookingResult.consultant_name && (
              <ConfirmRow label="Consultant" value={bookingResult.consultant_name} />
            )}
            {bookingResult.meet_link && (
              <div style={{ marginTop: 8 }}>
                <span style={{ opacity: 0.65, display: 'block', fontSize: 11, marginBottom: 2 }}>Google Meet Link:</span>
                <a
                  href={bookingResult.meet_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: 'var(--accent, #e23e30)',
                    textDecoration: 'underline',
                    wordBreak: 'break-all',
                    fontSize: 12,
                  }}
                >
                  {bookingResult.meet_link}
                </a>
              </div>
            )}
            
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              {bookingResult.meet_link && (
                <button
                  type="button"
                  onClick={handleCopyMeetLink}
                  style={miniBtnStyle}
                >
                  Copy Meet Link
                </button>
              )}
              <button
                type="button"
                onClick={handleCopyInvitation}
                style={miniBtnStyle}
              >
                Copy Invitation Details
              </button>
            </div>
            {copyFeedback && (
              <div style={{ fontSize: 11, color: '#22c55e', marginTop: 6, fontStyle: 'italic' }}>
                {copyFeedback}
              </div>
            )}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            style={{
              padding:        '9px 14px',
              borderRadius:   10,
              border:         'none',
              background:     'var(--agicent-gradient-trigger, var(--accent, #e23e30))',
              color:          'white',
              fontWeight:     700,
              fontSize:       13,
              cursor:         'pointer',
            }}
          >
            {showDetails ? 'Hide Details' : 'Meeting Details'}
          </button>
          <button
            type="button"
            onClick={() => {
              setIsRescheduling(true)
              setStep('day')
              setDayKey(null)
              setSlot(null)
              setStatus('idle')
              setError(null)
            }}
            style={{
              padding:    '9px 14px',
              borderRadius: 10,
              border:     '1px solid var(--border-strong)',
              background: 'var(--bg-2)',
              color:      'var(--text)',
              fontWeight: 600,
              fontSize:   13,
              cursor:     'pointer',
            }}
          >
            Reschedule Booking
          </button>
        </div>
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render: Step 1 — Day selection
  // ─────────────────────────────────────────────────────────────────────────

  if (step === 'day') {
    return (
      <div style={{ marginTop: 12 }}>
        {rescheduleBanner}
        <div style={sectionLabel}>Select a Day</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {orderedDays.map((key) => {
            const firstSlot = slotsByDay.get(key)![0]
            const label     = slotDayPill(firstSlot.start)
            const daySlots  = slotsByDay.get(key) ?? []
            const bookableCount = daySlots.filter((s) => (s.remaining_capacity ?? 0) > 0).length
            return (
              <button
                key={key}
                type="button"
                onClick={() => { setDayKey(key); setStep('time') }}
                style={pillBase}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--accent, #e23e30)'
                  e.currentTarget.style.color       = 'var(--accent, #e23e30)'
                  e.currentTarget.style.background  = 'rgba(226,62,48,0.06)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-strong)'
                  e.currentTarget.style.color       = 'var(--text)'
                  e.currentTarget.style.background  = 'var(--bg-2)'
                }}
              >
                {label}
                <span style={{ marginLeft: 6, fontSize: 11, opacity: 0.55 }}>
                  {bookableCount} slot{bookableCount !== 1 ? 's' : ''}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render: Step 2 — Time selection
  // ─────────────────────────────────────────────────────────────────────────

  if (step === 'time') {
    const firstStart = timeSlotsForDay[0]?.start ?? ''
    const dayHeading = firstStart ? slotDayFull(firstStart) : ''
    return (
      <div style={{ marginTop: 12 }}>
        {rescheduleBanner}
        <button
          type="button"
          style={backBtn}
          onClick={() => { setStep('day'); setDayKey(null) }}
        >
          ← {dayHeading}
        </button>

        <div style={sectionLabel}>Available Times · IST</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
          {timeSlotsForDay.map((s) => {
            const isFull = (s.remaining_capacity ?? 0) === 0
            return (
              <button
                key={s.start}
                type="button"
                disabled={isFull}
                onClick={() => { if (!isFull) { setSlot(s); setStep('confirm') } }}
                style={{
                  ...pillBase,
                  opacity: isFull ? 0.4 : 1,
                  cursor: isFull ? 'not-allowed' : 'pointer',
                  background: isFull ? 'rgba(0,0,0,0.05)' : 'var(--bg-2)',
                  color: isFull ? 'var(--text-3, #888)' : 'var(--text)',
                }}
                onMouseEnter={(e) => {
                  if (isFull) return
                  e.currentTarget.style.borderColor = 'var(--accent, #e23e30)'
                  e.currentTarget.style.color       = 'var(--accent, #e23e30)'
                  e.currentTarget.style.background  = 'rgba(226,62,48,0.06)'
                }}
                onMouseLeave={(e) => {
                  if (isFull) return
                  e.currentTarget.style.borderColor = 'var(--border-strong)'
                  e.currentTarget.style.color       = 'var(--text)'
                  e.currentTarget.style.background  = 'var(--bg-2)'
                }}
              >
                {slotTime(s.start)}{isFull ? ' FULL' : ''}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render: Step 3 — Confirmation
  // ─────────────────────────────────────────────────────────────────────────

  const confirmDay  = selectedSlot ? slotDayFull(selectedSlot.start)  : ''
  const confirmTime = selectedSlot ? slotTime(selectedSlot.start)      : ''

  return (
    <div style={{ marginTop: 12 }}>
      {rescheduleBanner}
      {/* Back navigation */}
      <button
        type="button"
        style={backBtn}
        onClick={() => { setStep('time'); setSlot(null) }}
      >
        ← {confirmDay} · {confirmTime} IST
      </button>

      {/* Booking summary card */}
      <div style={{
        padding:      '12px 14px',
        borderRadius: 12,
        border:       '1px solid var(--border-strong)',
        background:   'var(--bg-2)',
        marginBottom: 12,
      }}>
        <div style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 4 }}>Your discovery call</div>
        <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>{confirmDay}</div>
        <div style={{ fontSize: 13, color: 'var(--accent, #e23e30)', fontWeight: 600, marginTop: 2 }}>
          {confirmTime} IST · 45 min
        </div>
      </div>

      {/* Attendee details — inline form if not pre-filled */}
      {!hasStoredAttendee ? (
        <div style={{ marginBottom: 12 }}>
          <div style={sectionLabel}>Your Details</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <MiniInput
              placeholder="Your name"
              value={attendee.name}
              onChange={(v) => setAttendee((a) => ({ ...a, name: v }))}
            />
            <MiniInput
              placeholder="Work email"
              value={attendee.email}
              onChange={(v) => setAttendee((a) => ({ ...a, email: v }))}
            />
          </div>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 12 }}>
          Booking for{' '}
          <strong style={{ color: 'var(--text)' }}>{attendee.name}</strong>
          {' '}({attendee.email})
        </div>
      )}

      {/* Error message */}
      {errorMsg && (
        <div style={{
          marginBottom: 10,
          padding:      '8px 10px',
          borderRadius: 8,
          background:   'rgba(239,68,68,0.1)',
          border:       '1px solid rgba(239,68,68,0.2)',
          color:        '#f87171',
          fontSize:     12,
        }}>
          {errorMsg}
        </div>
      )}

      {/* Confirm button */}
      <button
        type="button"
        onClick={handleBook}
        disabled={!canBook}
        style={{
          width:        '100%',
          padding:      '11px',
          borderRadius: 10,
          border:       'none',
          background:   canBook
            ? 'var(--agicent-gradient-trigger, var(--accent, #e23e30))'
            : 'var(--bg-4, #444)',
          color:        canBook ? 'white' : 'var(--text-3)',
          fontWeight:   700,
          fontSize:     14,
          cursor:       canBook ? 'pointer' : 'not-allowed',
          transition:   'opacity 0.15s ease',
          opacity:      status === 'booking' ? 0.7 : 1,
        }}
      >
        {status === 'booking' ? 'Booking…' : isRescheduling ? 'Confirm Reschedule' : 'Confirm Discovery Call'}
      </button>
    </div>
  )
}

// ── Small helpers ──────────────────────────────────────────────────────────

function ConfirmRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: 6, marginBottom: 2 }}>
      <span style={{ minWidth: 46, opacity: 0.65 }}>{label}:</span>
      <span style={{ color: 'var(--text)', fontWeight: 500 }}>{value}</span>
    </div>
  )
}

function MiniInput({
  placeholder,
  value,
  onChange,
}: {
  placeholder: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <input
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        width:       '100%',
        padding:     '8px 10px',
        borderRadius: 8,
        border:      '1px solid var(--border-strong)',
        background:  'var(--bg)',
        color:       'var(--text)',
        fontSize:    13,
        outline:     'none',
        fontFamily:  'var(--font)',
        boxSizing:   'border-box',
      }}
    />
  )
}
