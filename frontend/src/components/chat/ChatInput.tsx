import { useCallback, useRef, useState } from 'react'

interface ChatInputProps {
  onSend: (query: string) => void
  disabled?: boolean
  isEmpty?: boolean
  isExpanded?: boolean
}

export function ChatInput({ onSend, disabled, isEmpty, isExpanded }: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [value, disabled, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value)
    // Auto-grow
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }

  const canSend = value.trim().length > 0 && !disabled

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
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder={isEmpty ? 'Ask anything about Agicent…' : 'Continue the conversation…'}
        disabled={disabled}
        rows={1}
        style={{
          flex: 1,
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
          opacity: disabled ? 0.6 : 1,
        }}
        onFocus={(e) => {
          e.target.style.borderColor = 'var(--agicent-red)'
        }}
        onBlur={(e) => {
          e.target.style.borderColor = 'var(--border-strong)'
        }}
      />

      <button
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
          // Loading spinner
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            style={{ animation: 'spin 1s linear infinite' }}
          >
            <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="17" strokeDashoffset="8" />
          </svg>
        ) : (
          // Send arrow
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
  )
}
