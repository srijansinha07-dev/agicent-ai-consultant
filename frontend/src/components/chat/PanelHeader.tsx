import type { ViewMode } from '@/types/chat'

import { ConsultantLogo } from './ConsultantLogo'

interface PanelHeaderProps {
  viewMode: ViewMode
  showHome: boolean
  onHome: () => void
  onExpand: () => void
  onClose: () => void
  isAdminView?: boolean
  onToggleAdmin?: () => void
}

export function PanelHeader({
  viewMode,
  showHome,
  onHome,
  onExpand,
  onClose,
  isAdminView = false,
  onToggleAdmin,
}: PanelHeaderProps) {
  const isExpanded = viewMode === 'expanded'

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: isExpanded ? '12px 20px' : '14px 16px',
        background: 'var(--agicent-gradient)',
        borderBottom: isExpanded ? '1px solid var(--border-strong)' : 'none',
        borderRadius: isExpanded ? 0 : 'var(--radius) var(--radius) 0 0',
        flexShrink: 0,
      }}
    >
      {isAdminView ? (
        <button
          type="button"
          onClick={onToggleAdmin}
          style={{
            border: 'none',
            background: 'rgba(255,255,255,0.18)',
            color: 'white',
            cursor: 'pointer',
            fontFamily: 'var(--font)',
            fontSize: '13px',
            fontWeight: 600,
            padding: '6px 12px',
            borderRadius: '8px',
            flexShrink: 0,
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.28)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.18)'
          }}
        >
          ← Back to Chat
        </button>
      ) : showHome ? (
        <button
          type="button"
          onClick={onHome}
          style={{
            border: 'none',
            background: 'rgba(255,255,255,0.18)',
            color: 'white',
            cursor: 'pointer',
            fontFamily: 'var(--font)',
            fontSize: '13px',
            fontWeight: 600,
            padding: '6px 12px',
            borderRadius: '8px',
            flexShrink: 0,
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.28)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.18)'
          }}
        >
          ← Home
        </button>
      ) : (
        <ConsultantLogo size={36} iconSize={14} />
      )}

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontWeight: 600,
            fontSize: isExpanded ? '16px' : '15px',
            color: 'var(--header-text)',
            letterSpacing: '-0.01em',
            lineHeight: 1.2,
          }}
        >
          {isAdminView ? 'Agicent Admin Console' : 'Agicent AI Consultant'}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'rgba(255,255,255,0.88)',
            marginTop: '2px',
          }}
        >
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: '#4ade80',
            }}
          />
          {isAdminView ? 'Manage schedules & consultants' : 'Ask about AI, MVPs & development'}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {!isAdminView && onToggleAdmin && (
          <button
            type="button"
            onClick={onToggleAdmin}
            style={{
              border: 'none',
              background: 'rgba(255,255,255,0.18)',
              color: 'white',
              cursor: 'pointer',
              fontSize: '11px',
              fontWeight: 700,
              padding: '6px 10px',
              borderRadius: '6px',
              transition: 'background 0.15s',
              marginRight: '4px',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.28)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.18)'
            }}
          >
            Admin
          </button>
        )}

        <HeaderIconButton
          label={isExpanded ? 'Collapse to widget' : 'Expand workspace'}
          onClick={onExpand}
          variant="dark"
        >
          {isExpanded ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M9 2H12V5M5 12H2V9M12 2L8 6M2 12L6 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 9V12H5M9 2H12V5M12 2L8 6M2 12L6 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
          )}
        </HeaderIconButton>

        <HeaderIconButton label="Close" onClick={onClose} variant="dark">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M1.5 1.5L10.5 10.5M10.5 1.5L1.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </HeaderIconButton>
      </div>
    </div>
  )
}


function HeaderIconButton({
  label,
  onClick,
  children,
  variant,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
  variant: 'light' | 'dark'
}) {
  const isLight = variant === 'light'
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      style={{
        width: '32px',
        height: '32px',
        borderRadius: '8px',
        border: 'none',
        background: isLight ? 'var(--bg-2)' : 'rgba(255,255,255,0.15)',
        color: isLight ? 'var(--text-2)' : 'white',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = isLight ? 'var(--bg-3)' : 'rgba(255,255,255,0.28)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = isLight ? 'var(--bg-2)' : 'rgba(255,255,255,0.15)'
      }}
    >
      {children}
    </button>
  )
}
