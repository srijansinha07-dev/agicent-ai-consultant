import { useCallback, useEffect, useRef, useState } from 'react'

import { env } from '@/config/env'
import { useVoiceInput } from '@/hooks/useVoiceInput'

interface ChatInputProps {
  onSend: (query: string, languageOverride?: string, voiceNoteUrl?: string) => void
  onVoiceLanguage?: (language: string) => void
  disabled?: boolean
  isEmpty?: boolean
  isExpanded?: boolean
}

export function ChatInput({
  onSend,
  onVoiceLanguage,
  disabled,
  isEmpty,
  isExpanded,
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const [isVoiceMenuOpen, setIsVoiceMenuOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const voiceEnabled = env.voiceEnabled

  const handleVoiceTranscript = useCallback(
    (result: { text: string; language: string; audioUrl?: string }) => {
      onVoiceLanguage?.(result.language)
      onSend(result.text, result.language, result.audioUrl)
    },
    [onSend, onVoiceLanguage],
  )

  const voice = useVoiceInput(handleVoiceTranscript)

  const voiceBusy = voice.status === 'recording' || voice.status === 'processing'
  const inputDisabled = disabled || voiceBusy

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || inputDisabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [value, inputDisabled, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsVoiceMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleMicClick = () => {
    if (!voiceEnabled || !voice.isSupported) {
      return
    }

    if (voice.status === 'recording') {
      voice.stopRecording()
      return
    }

    if (inputDisabled) {
      return
    }

    if (voice.status === 'error') {
      voice.cancelRecording()
    }

    setIsVoiceMenuOpen((prev) => !prev)
  }

  const handleRecordAudio = async () => {
    setIsVoiceMenuOpen(false)
    await voice.startRecording()
  }

  const handleUploadAudio = () => {
    setIsVoiceMenuOpen(false)
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    await voice.processAudioFile(file)
    e.target.value = ''
  }

  const canSend = value.trim().length > 0 && !inputDisabled
  const showMic = voiceEnabled && voice.isSupported

  const micLabel =
    voice.status === 'recording'
      ? 'Stop recording'
      : voice.status === 'processing'
        ? 'Transcribing audio'
        : 'Open voice menu'

  return (
    <div
      style={{
        padding: isExpanded ? '16px 20px 20px' : '12px 16px',
        borderTop: '1px solid var(--border)',
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-end',
        background: 'var(--bg)',
        borderRadius: isExpanded ? 0 : '0 0 var(--radius) var(--radius)',
        flexShrink: 0,
        maxWidth: isExpanded ? '720px' : undefined,
        width: isExpanded ? '100%' : undefined,
        margin: isExpanded ? '0 auto' : undefined,
      }}
    >
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={isEmpty ? 'Ask anything about Agicent…' : 'Continue the conversation…'}
          disabled={inputDisabled}
          rows={1}
          style={{
            width: '100%',
            resize: 'none',
            background: 'var(--bg-2)',
            border: '1px solid var(--border-strong)',
            borderRadius: '10px',
            padding: '10px 14px',
            color: 'var(--text)',
            fontSize: '14px',
            fontFamily: 'var(--font)',
            lineHeight: 1.5,
            outline: 'none',
            minHeight: '42px',
            maxHeight: '120px',
            overflowY: 'auto',
            transition: 'border-color 0.15s',
            opacity: inputDisabled ? 0.6 : 1,
            boxSizing: 'border-box',
          }}
          onFocus={(e) => {
            e.target.style.borderColor = 'var(--agicent-red)'
          }}
          onBlur={(e) => {
            e.target.style.borderColor = 'var(--border-strong)'
          }}
        />

        {voice.status === 'recording' && (
          <span
            style={{
              fontSize: '12px',
              color: 'var(--agicent-red)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: 'var(--agicent-red)',
                animation: 'pulse-dot 1.2s ease-in-out infinite',
              }}
            />
            Recording… tap mic to stop
          </span>
        )}

        {voice.status === 'processing' && (
          <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>Transcribing…</span>
        )}

        {voice.error && (
          <span style={{ fontSize: '12px', color: '#f87171' }}>{voice.error}</span>
        )}
      </div>

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="audio/*,.mp3,.wav,.webm,.ogg,.mp4,.m4a"
        style={{ display: 'none' }}
      />
      <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', flexShrink: 0 }}>
        {showMic && (
          <div style={{ position: 'relative' }} ref={menuRef}>
            {isVoiceMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 8px)',
                  right: 0,
                  background: 'var(--bg-2)',
                  border: '1px solid var(--border-strong)',
                  borderRadius: '12px',
                  padding: '6px',
                  boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  minWidth: '160px',
                  zIndex: 50,
                }}
              >
                <button
                  type="button"
                  onClick={handleRecordAudio}
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--text)',
                    fontSize: '13px',
                    fontWeight: 500,
                    textAlign: 'left',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    transition: 'background 0.15s',
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.background = 'var(--bg-4)')}
                  onMouseOut={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <rect x="6.5" y="1.5" width="3" height="6" rx="1.5" fill="currentColor" />
                    <path
                      d="M3.5 7.5C3.5 9.985 5.515 12 8 12C10.485 12 12.5 9.985 12.5 7.5"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                    />
                    <path d="M8 12V14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                  </svg>
                  Record Audio
                </button>
                <button
                  type="button"
                  onClick={handleUploadAudio}
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--text)',
                    fontSize: '13px',
                    fontWeight: 500,
                    textAlign: 'left',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    transition: 'background 0.15s',
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.background = 'var(--bg-4)')}
                  onMouseOut={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  Upload Audio
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={handleMicClick}
              disabled={inputDisabled && voice.status !== 'recording'}
              aria-label={micLabel}
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                border: voice.status === 'recording' ? '1px solid var(--agicent-red)' : '1px solid var(--border-strong)',
                background:
                  voice.status === 'recording'
                    ? 'rgba(226, 62, 48, 0.12)'
                    : voice.status === 'processing'
                      ? 'var(--bg-4)'
                      : 'var(--bg-2)',
                color: voice.status === 'recording' ? 'var(--agicent-red)' : 'var(--text-2)',
                cursor: inputDisabled && voice.status !== 'recording' ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.15s',
              }}
            >
              {voice.status === 'processing' ? (
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                  style={{ animation: 'spin 1s linear infinite' }}
                >
                  <circle
                    cx="7"
                    cy="7"
                    r="5.5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeDasharray="17"
                    strokeDashoffset="8"
                  />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <rect x="6.5" y="1.5" width="3" height="6" rx="1.5" fill="currentColor" />
                  <path
                    d="M3.5 7.5C3.5 9.985 5.515 12 8 12C10.485 12 12.5 9.985 12.5 7.5"
                    stroke="currentColor"
                    strokeWidth="1.4"
                    strokeLinecap="round"
                  />
                  <path d="M8 12V14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              )}
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            border: 'none',
            background: canSend ? 'var(--agicent-gradient)' : 'var(--bg-4)',
            color: canSend ? '#fff' : 'var(--text-3)',
            cursor: canSend ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'all 0.15s',
            transform: canSend ? 'scale(1)' : 'scale(0.95)',
          }}
        >
          {disabled ? (
            <svg
              width="14"
              height="14"
              viewBox="0 0 14 14"
              fill="none"
              style={{ animation: 'spin 1s linear infinite' }}
            >
              <circle
                cx="7"
                cy="7"
                r="5.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeDasharray="17"
                strokeDashoffset="8"
              />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path
                d="M2 7H12M7 2L12 7L7 12"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}
