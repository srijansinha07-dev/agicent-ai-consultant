type ConsultantLogoProps = {
  size?: number
  iconSize?: number
  style?: React.CSSProperties
}

export function ConsultantLogo({ size = 28, iconSize = 12, style }: ConsultantLogoProps) {
  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'var(--agicent-gradient)',
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: '0 2px 8px rgba(226, 62, 48, 0.25)',
        ...style,
      }}
    >
      <svg width={iconSize} height={iconSize} viewBox="0 0 12 12" fill="none">
        <path
          d="M6 1L7.2 4.6L11 6L7.2 7.4L6 11L4.8 7.4L1 6L4.8 4.6L6 1Z"
          fill="white"
        />
      </svg>
    </div>
  )
}

