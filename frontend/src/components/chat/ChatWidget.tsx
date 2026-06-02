import { useChat } from '@/hooks/useChat'

import { ConsultantPanel } from './ConsultantPanel'
import { FloatingTrigger } from './FloatingTrigger'

export function ChatWidget() {
  const chat = useChat()

  return (
    <div data-component="chat-widget" data-agicent-consultant-widget>
      {/* Floating trigger button — always visible when closed */}
      <FloatingTrigger
        viewMode={chat.viewMode}
        messageCount={chat.messages.length}
        onClick={() =>
          chat.setViewMode(chat.viewMode === 'closed' ? 'widget' : 'closed')
        }
      />

      {/* The consultant panel (widget or expanded) */}
      {chat.viewMode !== 'closed' && <ConsultantPanel chat={chat} />}
    </div>
  )
}
