import type { ViewMode } from '@/types/chat'

interface ExpandButtonProps {
  viewMode: ViewMode
  onClick: () => void
}

export function ExpandButton({ viewMode, onClick }: ExpandButtonProps) {
  const label = viewMode === 'widget' ? 'Expand chat' : 'Minimize chat'

  return (
    <button type="button" onClick={onClick} aria-label={label} />
  )
}
