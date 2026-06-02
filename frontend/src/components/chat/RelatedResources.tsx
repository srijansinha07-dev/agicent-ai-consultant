import type { Source } from '@/types/chat'
import { getDisplayResources, getResourceTitle, getResourceUrl } from '@/utils/sourceLabel'

interface RelatedResourcesProps {
  sources: Source[]
}

/** Meaningful Agicent page links — hidden when nothing quality to show. */
export function RelatedResources({ sources }: RelatedResourcesProps) {
  const resources = getDisplayResources(sources)
  if (resources.length === 0) return null

  return (
    <div
      style={{
        marginTop: '16px',
        paddingTop: '14px',
        borderTop: '1px solid var(--border)',
      }}
    >
      <div
        style={{
          fontSize: '11px',
          fontWeight: 600,
          color: 'var(--text-3)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          marginBottom: '10px',
        }}
      >
        Related Agicent Resources
      </div>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {resources.map((source) => {
          const title = getResourceTitle(source)!
          const href = getResourceUrl(source)!
          return (
            <li key={href}>
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                  fontSize: '13px',
                  fontWeight: 500,
                  color: 'var(--agicent-navy)',
                  textDecoration: 'none',
                  lineHeight: 1.4,
                  padding: '8px 10px',
                  borderRadius: '8px',
                  background: 'var(--bg-2)',
                  border: '1px solid var(--border)',
                  transition: 'border-color 0.15s, background 0.15s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--accent-border)'
                  e.currentTarget.style.background = 'var(--accent-dim)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.background = 'var(--bg-2)'
                }}
              >
                <span aria-hidden style={{ flexShrink: 0 }}>
                  📄
                </span>
                <span>{title}</span>
              </a>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
