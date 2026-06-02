import type { ViewMode } from '@/types/chat'

import { ConsultantLogo } from './ConsultantLogo'

interface FloatingTriggerProps {
  viewMode: ViewMode
  messageCount: number
  onClick: () => void
}

export function FloatingTrigger({ viewMode, messageCount, onClick }: FloatingTriggerProps) {
  const isOpen = viewMode !== 'closed'

  if (viewMode === 'expanded') {
    return null
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={isOpen ? 'Close AI consultant' : 'Open Agicent AI Consultant'}
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 2147483001,
        minWidth: isOpen ? '58px' : 'auto',
        height: '52px',
        padding: isOpen ? 0 : '0 18px 0 14px',
        borderRadius: '26px',
        background: isOpen ? 'var(--bg)' : 'var(--agicent-gradient-trigger)',
        border: isOpen ? '1px solid var(--border-strong)' : 'none',
        color: isOpen ? 'var(--text-2)' : '#fff',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: isOpen ? 0 : '8px',
        boxShadow: isOpen
          ? 'var(--shadow-sm)'
          : '0 6px 24px rgba(240, 90, 40, 0.45), 0 2px 8px rgba(45, 46, 69, 0.12)',
        transition: 'transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s',
        fontFamily: 'var(--font)',
      }}
      onMouseEnter={(e) => {
        if (!isOpen) e.currentTarget.style.transform = 'scale(1.04)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'scale(1)'
      }}
    >
      {isOpen ? (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden>
          <path d="M3 3L17 17M17 3L3 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      ) : (
        <ConsultantLogo size={30} iconSize={14} />
      )}

      {!isOpen && messageCount > 0 && (
        <span
          style={{
            position: 'absolute',
            top: '2px',
            right: '2px',
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            background: 'var(--agicent-red)',
            border: '2px solid white',
          }}
        />
      )}
    </button>
  )
}
