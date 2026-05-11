import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, Sparkles } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import { useChatSession } from '@/hooks/useChat'
import { useChatStore } from '@/store/chatStore'
import { useAuthStore } from '@/store/authStore'

interface Props {
  sessionId: string
}

export default function ChatWindow({ sessionId }: Props) {
  const { data: session, isLoading } = useChatSession(sessionId)
  const { isStreaming, setStreaming } = useChatStore()
  const { token } = useAuthStore()
  const qc = useQueryClient()
  const bottomRef = useRef<HTMLDivElement>(null)
  const [streamingText, setStreamingText] = useState('')
  const [pendingUser, setPendingUser] = useState('')
  const { t, i18n } = useTranslation('chat')

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session?.messages, streamingText])

  async function handleSend(content: string) {
    setStreaming(true)
    setPendingUser(content)
    setStreamingText('')

    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
      const resp = await fetch(`${baseUrl}/hr/sessions/${sessionId}/messages/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ content, lang: i18n.language }),
      })

      if (!resp.ok || !resp.body) throw new Error('Stream failed')

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'token') {
              setStreamingText((prev) => prev + event.token)
            } else if (event.type === 'done') {
              await Promise.all([
                qc.invalidateQueries({ queryKey: ['session', sessionId] }),
                qc.invalidateQueries({ queryKey: ['sessions'] }),
              ])
            }
          } catch {}
        }
      }
    } catch (e) {
      console.error('Stream error:', e)
    } finally {
      setPendingUser('')
      setStreamingText('')
      setStreaming(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const isEmpty = !session?.messages?.length && !isStreaming

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <EmptySession />
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">
            {session?.messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}

            {pendingUser && (
              <div className="flex justify-end">
                <div className="max-w-[82%] px-4 py-3 text-sm bg-primary text-primary-foreground rounded-2xl rounded-br-sm leading-relaxed">
                  <p className="whitespace-pre-wrap">{pendingUser}</p>
                </div>
              </div>
            )}

            {streamingText && (
              <div className="flex justify-start">
                <div className="max-w-[82%] rounded-2xl rounded-bl-sm px-4 py-3 text-sm bg-card border border-border shadow-sm text-foreground leading-relaxed">
                  <p className="whitespace-pre-wrap">
                    {streamingText}
                    <span className="inline-block w-[2px] h-3.5 ml-0.5 bg-primary rounded-sm align-middle animate-pulse" />
                  </p>
                </div>
              </div>
            )}

            {isStreaming && !streamingText && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 px-4 py-3 rounded-2xl rounded-bl-sm bg-card border border-border shadow-sm">
                  <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">{t('searching')}</span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}
        {isEmpty && <div ref={bottomRef} />}
      </div>

      <div className="border-t border-border bg-background">
        <div className="max-w-3xl mx-auto">
          <ChatInput onSend={handleSend} disabled={isStreaming} />
        </div>
      </div>
    </div>
  )
}

function EmptySession() {
  const { t } = useTranslation('chat')
  return (
    <div className="flex flex-col h-full items-center justify-center gap-5 px-6 py-12 text-center">
      <div className="size-12 rounded-2xl bg-primary/10 flex items-center justify-center">
        <Sparkles className="size-6 text-primary" />
      </div>
      <div className="space-y-1.5 max-w-xs">
        <p className="font-medium text-foreground">{t('newConversationTitle')}</p>
        <p className="text-sm text-muted-foreground">{t('newConversationSubtitle')}</p>
      </div>
    </div>
  )
}
