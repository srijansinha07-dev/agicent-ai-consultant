import type { ChatMessage } from '@/types/chat'

import { FormattedAnswer } from './FormattedAnswer'
import { ConsultantLogo } from './ConsultantLogo'

interface MessageProps {
  message: ChatMessage
}

export function Message({ message }: MessageProps) {
  const isUser = message.role === 'user'

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
        {isUser ? (
          <span>{message.content}</span>
        ) : (
          <FormattedAnswer content={message.content} />
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
