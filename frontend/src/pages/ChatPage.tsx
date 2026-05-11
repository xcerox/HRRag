import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useChatStore } from '@/store/chatStore'
import ChatWindow from '@/components/chat/ChatWindow'

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const setActiveSession = useChatStore((s) => s.setActiveSession)
  const { t } = useTranslation('chat')

  useEffect(() => {
    setActiveSession(sessionId ?? null)
  }, [sessionId])

  if (!sessionId) {
    return (
      <div className="flex flex-col h-full items-center justify-center gap-4 text-center px-6">
        <div className="size-12 rounded-2xl bg-primary/10 flex items-center justify-center">
          <Sparkles className="size-6 text-primary" />
        </div>
        <div className="space-y-1.5 max-w-xs">
          <p className="font-medium text-foreground">{t('welcomeTitle')}</p>
          <p className="text-sm text-muted-foreground">{t('welcomeSubtitle')}</p>
        </div>
      </div>
    )
  }

  return <ChatWindow sessionId={sessionId} />
}
