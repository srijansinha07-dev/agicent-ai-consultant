import '@/styles/globals.css'

import { ChatWidget } from '@/components/chat/ChatWidget'
import { env } from '@/config/env'

export default function App() {
  const embedMode = env.embedMode

  if (embedMode) {
    return <ChatWidget />
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#ffffff',
        fontFamily: 'var(--font)',
      }}
    >
      {/* Demo page — simulates agicent.com host; hidden in embed mode */}
      <div
        style={{
          padding: '48px 32px',
          maxWidth: '720px',
          color: 'var(--agicent-navy)',
        }}
      >
        <div
          style={{
            fontSize: '28px',
            fontWeight: 700,
            color: 'var(--agicent-red)',
            letterSpacing: '-0.02em',
          }}
        >
          AGICENT
        </div>
        <h1
          style={{
            fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
            fontWeight: 700,
            lineHeight: 1.2,
            marginTop: '24px',
            marginBottom: '16px',
          }}
        >
          AI-Powered Digital Transformation
          <span
            style={{
              background: 'linear-gradient(transparent 60%, var(--agicent-yellow) 60%)',
            }}
          >
            {' '}
            &amp; Dev Services
          </span>
        </h1>
        <p style={{ color: 'var(--text-2)', lineHeight: 1.6, maxWidth: '520px' }}>
          Preview host page for the embeddable AI Consultant widget. Set{' '}
          <code style={{ fontSize: '13px' }}>VITE_EMBED_MODE=true</code> when embedding on
          agicent.com.
        </p>
      </div>

      <ChatWidget />
    </div>
  )
}
