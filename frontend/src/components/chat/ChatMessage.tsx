import { useState } from 'react'
import { FileText, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChatMessage as ChatMessageType } from '@/hooks/useChat'

interface Props { message: ChatMessageType }

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  function handleCopy() {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }
  return (
    <button
      onClick={handleCopy}
      className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-border/60 transition-all"
      title="Copiar"
    >
      {copied
        ? <Check className="size-3.5 text-green-500" />
        : <Copy className="size-3.5" />
      }
    </button>
  )
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'
  const primarySource = !isUser && message.sources.length > 0 ? message.sources[0] : null

  return (
    <div className={cn('flex flex-col gap-1', isUser ? 'items-end' : 'items-start')}>

      <div className={cn('relative max-w-[82%] group', isUser ? 'items-end' : 'items-start')}>
        <div className={cn(
          'px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'bg-primary text-primary-foreground rounded-2xl rounded-br-sm'
            : 'bg-card border border-border text-foreground rounded-2xl rounded-bl-sm shadow-sm'
        )}>
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {!isUser && (
          <div className="absolute -right-8 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyButton text={message.content} />
          </div>
        )}
      </div>

      {primarySource && (
        <div className="max-w-[82%] flex items-center gap-1.5 px-1">
          <FileText className="size-3 text-muted-foreground/60 shrink-0" />
          <p className="text-[10px] text-muted-foreground/70 italic truncate">
            {primarySource.document_name}
            {primarySource.page_number != null ? `, p.${primarySource.page_number}` : ''}
            {message.sources.length > 1 ? ` +${message.sources.length - 1}` : ''}
          </p>
        </div>
      )}

      <span className="text-[10px] text-muted-foreground/50 px-1">{formatTime(message.created_at)}</span>
    </div>
  )
}
