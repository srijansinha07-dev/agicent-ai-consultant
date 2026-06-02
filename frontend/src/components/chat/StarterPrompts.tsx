import { ConsultantLogo } from './ConsultantLogo'

interface StarterPromptsProps {
  welcome: string
  prompts: string[]
  onSelect: (prompt: string) => void
  isExpanded?: boolean
}

export function StarterPrompts({ welcome, prompts, onSelect, isExpanded }: StarterPromptsProps) {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        padding: isExpanded ? '32px 0 24px' : '20px 16px',
        gap: isExpanded ? '28px' : '20px',
        minHeight: isExpanded ? 'min(60vh, 520px)' : undefined,
        justifyContent: isExpanded ? 'center' : 'flex-start',
      }}
    >
      <div
        style={{
          display: 'flex',
          gap: '10px',
          alignItems: 'flex-start',
        }}
      >
          <ConsultantLogo size={28} iconSize={12} />
        <div
          style={{
            flex: 1,
            padding: '12px 14px',
            borderRadius: '4px 14px 14px 14px',
            background: 'var(--assistant-bubble)',
            border: '1px solid var(--border)',
            fontSize: '14px',
            lineHeight: 1.6,
            color: 'var(--text)',
          }}
        >
          {welcome}
        </div>
      </div>

      <div>
        <p
          style={{
            fontSize: '12px',
            fontWeight: 600,
            color: 'var(--text-3)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            margin: '0 0 10px',
          }}
        >
          Suggested topics
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {prompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onSelect(prompt)}
              style={{
                textAlign: 'left',
                padding: '12px 14px',
                borderRadius: '10px',
                border: '1px solid var(--border)',
                background: 'var(--bg)',
                color: 'var(--text)',
                cursor: 'pointer',
                fontSize: '13px',
                lineHeight: 1.45,
                fontFamily: 'var(--font)',
                transition: 'border-color 0.15s, background 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent-border)'
                e.currentTarget.style.background = 'var(--accent-dim)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border)'
                e.currentTarget.style.background = 'var(--bg)'
              }}
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
