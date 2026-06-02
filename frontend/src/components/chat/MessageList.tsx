import { useEffect, useRef } from 'react'

import type { ChatMessage } from '@/types/chat'

import { Message } from './Message'
import { ConsultantLogo } from './ConsultantLogo'

interface MessageListProps {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
}

export function MessageList({ messages, isLoading, error }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div
      className="chat-scroll"
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px 0',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}
    >
      {messages.map((message) => (
        <Message key={message.id} message={message} />
      ))}

      {isLoading && <TypingIndicator />}

      {error && (
        <div
          className="animate-fade-in"
          style={{
            padding: '12px 16px',
            borderRadius: '10px',
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.2)',
            color: '#f87171',
            fontSize: '13px',
            lineHeight: 1.5,
          }}
        >
          <span style={{ marginRight: '8px' }}>⚠</span>
          {error}
        </div>
      )}

      <div ref={bottomRef} style={{ height: 1 }} />
    </div>
  )
}

function TypingIndicator() {
  return (
    <div
      className="animate-fade-in"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '12px 0 4px',
      }}
    >
      {/* Avatar */}
      <ConsultantLogo size={24} iconSize={10} />

      {/* Dots */}
      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            style={{
              width: '5px',
              height: '5px',
              borderRadius: '50%',
              background: 'var(--text-3)',
              display: 'block',
              animation: 'pulse-dot 1.4s ease-in-out infinite',
              animationDelay: `${i * 0.16}s`,
            }}
          />
        ))}
      </div>
    </div>
  )
}
