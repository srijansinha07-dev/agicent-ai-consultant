import { useState } from 'react'

import type { SlotOption } from '@/types/chat'
import { apiClient, USER_ID_HEADER } from '@/services/api'
import { env } from '@/config/env'

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
  html_link: string
  summary: string
  start: string
}

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

export function BookingSlotPicker({ slots, consultationSummary }: BookingSlotPickerProps) {
  const [selectedSlot, setSelectedSlot] = useState<SlotOption | null>(null)
  const [status, setStatus] = useState<'idle' | 'booking' | 'success' | 'error'>('idle')
  const [bookingResult, setBookingResult] = useState<BookingResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Attendee info — read from sessionStorage (set by ConsultationModal on success)
  // Fall back to an inline mini-form if not yet collected.
  const [attendee, setAttendee] = useState<AttendeeInfo>(() => {
    const stored = loadAttendeeInfo()
    return stored ?? { name: '', email: '', company: '', summary: '' }
  })

  const hasStoredAttendee = Boolean(loadAttendeeInfo())

  const canBook =
    selectedSlot !== null &&
    attendee.name.trim().length >= 2 &&
    validateEmail(attendee.email) &&
    status !== 'booking'

  async function handleBook() {
    if (!canBook || !selectedSlot) return
    setStatus('booking')
    setErrorMsg(null)

    try {
      const { data } = await apiClient.post(
        '/api/calendar/book',
        {
          start_iso: selectedSlot.start,
          end_iso: selectedSlot.end,
          attendee_email: attendee.email.trim(),
          attendee_name: attendee.name.trim(),
          topic_summary: consultationSummary || attendee.summary || '',
        },
        { headers: { [USER_ID_HEADER]: env.userId } },
      )

      if (!data.ok) {
        setStatus('error')
        setErrorMsg(data.error ?? 'Booking failed. Please try again.')
        return
      }

      setBookingResult({
        html_link: data.html_link ?? '',
        summary: data.summary ?? '',
        start: selectedSlot.display,
      })
      setStatus('success')
    } catch (err) {
      setStatus('error')
      setErrorMsg(err instanceof Error ? err.message : 'Booking failed. Please try again.')
    }
  }

  // ── Success state ─────────────────────────────────────────────────────────
  if (status === 'success' && bookingResult) {
    return (
      <div
        style={{
          marginTop: 14,
          padding: '16px',
          borderRadius: 14,
          border: '1px solid rgba(34,197,94,0.3)',
          background: 'rgba(34,197,94,0.08)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: 20 }}>✓</span>
          <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>
            Discovery Call Booked
          </span>
        </div>

        <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.7 }}>
          <Row label="Date" value={bookingResult.start} />
          <Row label="Attendee" value={attendee.name} />
          <Row label="Email" value={attendee.email} />
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          {bookingResult.html_link && (
            <a
              href={bookingResult.html_link}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                padding: '9px 14px',
                borderRadius: 10,
                border: 'none',
                background: 'var(--agicent-gradient-trigger, var(--accent))',
                color: 'white',
                fontWeight: 700,
                fontSize: 13,
                cursor: 'pointer',
                textDecoration: 'none',
                display: 'inline-block',
              }}
            >
              Open Calendar Event
            </a>
          )}
          <button
            type="button"
            onClick={() => {
              setStatus('idle')
              setSelectedSlot(null)
              setBookingResult(null)
              setErrorMsg(null)
            }}
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
            Schedule Another Call
          </button>
        </div>
      </div>
    )
  }

  // ── Slot picker ───────────────────────────────────────────────────────────
  return (
    <div style={{ marginTop: 12 }}>
      {/* Slot buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {slots.map((slot) => {
          const isSelected = selectedSlot?.start === slot.start
          return (
            <button
              key={slot.start}
              type="button"
              onClick={() => setSelectedSlot(isSelected ? null : slot)}
              style={{
                padding: '10px 14px',
                borderRadius: 10,
                border: isSelected
                  ? '2px solid var(--accent, #e23e30)'
                  : '1px solid var(--border-strong)',
                background: isSelected
                  ? 'rgba(226, 62, 48, 0.08)'
                  : 'var(--bg)',
                color: isSelected ? 'var(--accent, #e23e30)' : 'var(--text)',
                fontWeight: isSelected ? 700 : 500,
                fontSize: 13,
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s ease',
              }}
            >
              {slot.display}
            </button>
          )
        })}
      </div>

      {/* Inline attendee form — only shown when not collected yet */}
      {selectedSlot && !hasStoredAttendee && (
        <div
          style={{
            marginTop: 12,
            padding: '12px 14px',
            borderRadius: 12,
            border: '1px solid var(--border-strong)',
            background: 'var(--bg-2)',
          }}
        >
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginBottom: 8 }}>
            Your details for the calendar invite:
          </div>
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
      )}

      {/* Selected slot summary + book button */}
      {selectedSlot && (
        <div style={{ marginTop: 12 }}>
          <div
            style={{
              fontSize: 12,
              color: 'var(--text-2)',
              marginBottom: 8,
            }}
          >
            Selected:{' '}
            <span style={{ fontWeight: 600, color: 'var(--text)' }}>
              {selectedSlot.display}
            </span>
          </div>

          {errorMsg && (
            <div
              style={{
                marginBottom: 8,
                padding: '8px 10px',
                borderRadius: 8,
                background: 'rgba(239,68,68,0.1)',
                border: '1px solid rgba(239,68,68,0.2)',
                color: '#f87171',
                fontSize: 12,
              }}
            >
              {errorMsg}
            </div>
          )}

          <button
            type="button"
            onClick={handleBook}
            disabled={!canBook}
            style={{
              width: '100%',
              padding: '11px',
              borderRadius: 10,
              border: 'none',
              background: canBook
                ? 'var(--agicent-gradient-trigger, var(--accent, #e23e30))'
                : 'var(--bg-4, #444)',
              color: canBook ? 'white' : 'var(--text-3)',
              fontWeight: 700,
              fontSize: 14,
              cursor: canBook ? 'pointer' : 'not-allowed',
              transition: 'opacity 0.15s ease',
              opacity: status === 'booking' ? 0.7 : 1,
            }}
          >
            {status === 'booking' ? 'Booking…' : 'Book Discovery Call'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Small helpers ──────────────────────────────────────────────────────────

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: 6, marginBottom: 2 }}>
      <span style={{ minWidth: 64 }}>{label}:</span>
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
        width: '100%',
        padding: '8px 10px',
        borderRadius: 8,
        border: '1px solid var(--border-strong)',
        background: 'var(--bg)',
        color: 'var(--text)',
        fontSize: 13,
        outline: 'none',
        fontFamily: 'var(--font)',
        boxSizing: 'border-box',
      }}
    />
  )
}
