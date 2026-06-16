import { useEffect, useRef, useState } from 'react'

import type { ChatMessage } from '@/types/chat'

import { FormattedAnswer } from './FormattedAnswer'
import { ConsultantLogo } from './ConsultantLogo'
import { BookingSlotPicker } from './BookingSlotPicker'

interface MessageProps {
  message: ChatMessage
  voiceEnabled?: boolean
  speechSupported?: boolean
  isSpeaking?: boolean
  onListen?: () => void
}

export function Message({
  message,
  voiceEnabled = false,
  speechSupported = false,
  isSpeaking = false,
  onListen,
}: MessageProps) {
  const isUser = message.role === 'user'
  const isHindi = message.language && message.language.startsWith('hi')
  const showListen = !isUser && voiceEnabled && speechSupported && !isHindi
  const isVoiceNote = isUser && Boolean(message.voiceNoteUrl)

  return (
    <div
      className="animate-slide-up"
      style={{
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-start',
        flexDirection: isUser ? 'row-reverse' : 'row',
        marginBottom: '14px',
      }}
    >
      {!isUser && <ConsultantAvatar />}

      <div
        style={{
          maxWidth: isUser ? '85%' : '92%',
          padding: isUser ? '10px 14px' : '12px 14px',
          borderRadius: isUser ? '16px 16px 4px 16px' : '4px 16px 16px 16px',
          background: isUser ? 'var(--user-bubble)' : 'var(--assistant-bubble)',
          border: isUser ? '1px solid rgba(226, 62, 48, 0.12)' : '1px solid var(--border)',
          color: 'var(--text)',
          fontSize: '14px',
          lineHeight: 1.65,
          wordBreak: 'break-word',
          boxShadow: isUser ? 'none' : 'var(--shadow-sm)',
        }}
      >
        {isVoiceNote ? (
          <VoiceNoteBubble url={message.voiceNoteUrl!} transcript={message.content} />
        ) : isUser ? (
          <span>{message.content}</span>
        ) : (
          <>
            <FormattedAnswer content={message.content} />

            {message.availableSlots && message.availableSlots.length > 0 && (
              <BookingSlotPicker
                slots={message.availableSlots}
                consultationSummary={message.consultationSummary}
              />
            )}

            {showListen && (
              <button
                type="button"
                onClick={onListen}
                aria-label={isSpeaking ? 'Stop speaking' : 'Listen to response'}
                style={{
                  marginTop: '10px',
                  border: 'none',
                  background: 'transparent',
                  color: isSpeaking ? 'var(--agicent-red)' : 'var(--text-3)',
                  padding: '4px',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: '4px',
                  transition: 'color 0.15s',
                }}
                onMouseOver={(e) => (e.currentTarget.style.color = isSpeaking ? 'var(--agicent-red)' : 'var(--text-2)')}
                onMouseOut={(e) => (e.currentTarget.style.color = isSpeaking ? 'var(--agicent-red)' : 'var(--text-3)')}
              >
                {isSpeaking ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <rect x="6" y="6" width="12" height="12" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
                  </svg>
                )}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function ConsultantAvatar() {
  return (
    <ConsultantLogo size={28} iconSize={12} style={{ marginTop: '2px' }} />
  )
}

// ── Voice Note Bubble ────────────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

interface VoiceNoteBubbleProps {
  url: string
  transcript: string
}

function VoiceNoteBubble({ url, transcript }: VoiceNoteBubbleProps) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [duration, setDuration] = useState<number | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [showTranscript, setShowTranscript] = useState(false)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onLoaded = () => setDuration(audio.duration)
    const onTimeUpdate = () => setCurrentTime(audio.currentTime)
    const onEnded = () => { setIsPlaying(false); setCurrentTime(0) }

    audio.addEventListener('loadedmetadata', onLoaded)
    audio.addEventListener('timeupdate', onTimeUpdate)
    audio.addEventListener('ended', onEnded)

    return () => {
      audio.removeEventListener('loadedmetadata', onLoaded)
      audio.removeEventListener('timeupdate', onTimeUpdate)
      audio.removeEventListener('ended', onEnded)
    }
  }, [])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return
    if (isPlaying) {
      audio.pause()
      setIsPlaying(false)
    } else {
      audio.play().catch(() => {})
      setIsPlaying(true)
    }
  }

  const displayTime = duration != null
    ? `${formatDuration(currentTime)} / ${formatDuration(duration)}`
    : '🎤 Voice Message'

  const progress = duration ? (currentTime / duration) * 100 : 0

  return (
    <div style={{ minWidth: '180px' }}>
      {/* Hidden audio element */}
      <audio ref={audioRef} src={url} preload="metadata" style={{ display: 'none' }} />

      {/* Controls row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Play / Pause button */}
        <button
          type="button"
          onClick={togglePlay}
          aria-label={isPlaying ? 'Pause voice message' : 'Play voice message'}
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            border: 'none',
            background: 'var(--agicent-red, #e23e30)',
            color: '#fff',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'opacity 0.15s',
          }}
          onMouseOver={(e) => (e.currentTarget.style.opacity = '0.85')}
          onMouseOut={(e) => (e.currentTarget.style.opacity = '1')}
        >
          {isPlaying ? (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <rect x="6" y="4" width="4" height="16" />
              <rect x="14" y="4" width="4" height="16" />
            </svg>
          ) : (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          )}
        </button>

        {/* Waveform / progress bar */}
        <div style={{ flex: 1 }}>
          <div
            style={{
              height: '4px',
              borderRadius: '2px',
              background: 'rgba(0,0,0,0.12)',
              overflow: 'hidden',
              marginBottom: '4px',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${progress}%`,
                background: 'var(--agicent-red, #e23e30)',
                transition: 'width 0.1s linear',
                borderRadius: '2px',
              }}
            />
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-3)', letterSpacing: '0.02em' }}>
            {displayTime}
          </div>
        </div>

        {/* Mic icon */}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flexShrink: 0 }}>
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
      </div>

      {/* Show transcript toggle (hidden by default) */}
      <button
        type="button"
        onClick={() => setShowTranscript((v) => !v)}
        style={{
          marginTop: '8px',
          background: 'none',
          border: 'none',
          padding: 0,
          cursor: 'pointer',
          fontSize: '11px',
          color: 'var(--text-3)',
          textDecoration: 'underline',
          textDecorationStyle: 'dotted',
        }}
      >
        {showTranscript ? 'Hide transcript' : 'Show transcript'}
      </button>

      {showTranscript && (
        <div
          style={{
            marginTop: '6px',
            fontSize: '12px',
            color: 'var(--text-2)',
            fontStyle: 'italic',
            lineHeight: 1.5,
            borderLeft: '2px solid var(--border)',
            paddingLeft: '8px',
          }}
        >
          {transcript}
        </div>
      )}
    </div>
  )
}

