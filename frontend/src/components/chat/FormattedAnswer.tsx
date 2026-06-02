interface FormattedAnswerProps {
  content: string
}

/** Renders consultant markdown: ### headings, bullets, numbered lists, bold. */
export function FormattedAnswer({ content }: FormattedAnswerProps) {
  const blocks = content.split(/\n\n+/)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {blocks.map((block, bi) => (
        <Block key={bi} text={block.trim()} />
      ))}
    </div>
  )
}

function Block({ text }: { text: string }) {
  if (!text) return null

  const lines = text.split('\n')
  const firstLine = lines[0]?.trim() ?? ''

  const headingMatch = firstLine.match(/^(#{1,3})\s+(.+)$/)
  if (headingMatch) {
    const body = lines.slice(1).join('\n').trim()
    return (
      <section>
        <h4
          style={{
            margin: '0 0 8px',
            fontWeight: 600,
            fontSize: '14px',
            color: 'var(--text)',
            letterSpacing: '-0.01em',
          }}
        >
          <InlineFormatted text={headingMatch[2]} />
        </h4>
        {body ? <Block text={body} /> : null}
      </section>
    )
  }

  const isBullet = lines.every((l) => !l.trim() || /^[-•*]\s/.test(l.trim()))
  const isNumbered = lines.every((l) => !l.trim() || /^\d+[.)]\s/.test(l.trim()))

  if (isBullet && lines.some((l) => /^[-•*]\s/.test(l.trim()))) {
    return (
      <ul style={{ margin: 0, paddingLeft: '20px' }}>
        {lines
          .filter((l) => l.trim())
          .map((line, i) => (
            <li key={i} style={{ marginBottom: '5px', lineHeight: 1.55, fontSize: '14px' }}>
              <InlineFormatted text={line.replace(/^[-•*]\s*/, '')} />
            </li>
          ))}
      </ul>
    )
  }

  if (isNumbered && lines.some((l) => /^\d+[.)]\s/.test(l.trim()))) {
    return (
      <ol style={{ margin: 0, paddingLeft: '20px' }}>
        {lines
          .filter((l) => l.trim())
          .map((line, i) => (
            <li key={i} style={{ marginBottom: '5px', lineHeight: 1.55, fontSize: '14px' }}>
              <InlineFormatted text={line.replace(/^\d+[.)]\s*/, '')} />
            </li>
          ))}
      </ol>
    )
  }

  return (
    <p style={{ margin: 0, lineHeight: 1.6, fontSize: '14px' }}>
      {lines.map((line, i) => (
        <span key={i}>
          {i > 0 && <br />}
          <InlineFormatted text={line} />
        </span>
      ))}
    </p>
  )
}

function InlineFormatted({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return (
            <strong key={i} style={{ fontWeight: 600 }}>
              {part.slice(2, -2)}
            </strong>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}
