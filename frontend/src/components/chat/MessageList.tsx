import { useEffect, useRef, useState } from 'react'

import { env } from '@/config/env'
import type { ChatMessage } from '@/types/chat'
import { useSpeechOutput } from '@/hooks/useSpeechOutput'
import { sanitizeForSpeech } from '@/hooks/useSpeechOutput'

import { Message } from './Message'
import { ConsultantLogo } from './ConsultantLogo'

interface MessageListProps {
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
}

export function MessageList({ messages, isLoading, error }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const speech = useSpeechOutput()
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null)
  const voiceEnabled = env.voiceEnabled

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    if (!speech.isSpeaking) {
      setSpeakingMessageId(null)
    }
  }, [speech.isSpeaking])

  const handleListen = (message: ChatMessage) => {
    if (!voiceEnabled || !speech.isSupported || message.role !== 'assistant') {
      return
    }

    if (speakingMessageId === message.id && speech.isSpeaking) {
      speech.stop()
      setSpeakingMessageId(null)
      return
    }

    speech.speak(sanitizeForSpeech(message.content), message.language)
    setSpeakingMessageId(message.id)
  }

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
        <Message
          key={message.id}
          message={message}
          voiceEnabled={voiceEnabled}
          speechSupported={speech.isSupported}
          isSpeaking={speakingMessageId === message.id && speech.isSpeaking}
          onListen={() => handleListen(message)}
        />
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
      <ConsultantLogo size={24} iconSize={10} />

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
