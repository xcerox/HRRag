import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowUp, Square } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  onSend: (content: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSend, disabled }: Props) {
  const { t } = useTranslation('chat')
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.cssText = `height: auto; height: ${Math.min(el.scrollHeight, 160)}px`
  }, [value])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleSend() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.cssText = 'height: auto'
    }
  }

  const canSend = value.trim().length > 0 && !disabled

  return (
    <div className="px-4 py-4">
      <div className={cn(
        'relative flex items-end gap-2 rounded-2xl border bg-card shadow-sm transition-all duration-150',
        'focus-within:ring-2 focus-within:ring-ring focus-within:border-transparent',
        disabled ? 'opacity-70' : 'border-border'
      )}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('inputPlaceholder')}
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent px-4 py-3 text-sm text-foreground
            placeholder:text-muted-foreground/60
            focus:outline-none
            min-h-[48px] max-h-[160px]
            leading-relaxed"
        />

        <div className="shrink-0 pb-2.5 pr-2.5">
          <button
            onClick={handleSend}
            disabled={!canSend}
            className={cn(
              'size-8 rounded-xl flex items-center justify-center transition-all duration-150',
              canSend
                ? 'bg-primary text-primary-foreground hover:opacity-90 active:scale-95 shadow-sm'
                : disabled
                  ? 'bg-muted text-muted-foreground cursor-default'
                  : 'bg-muted text-muted-foreground/40'
            )}
          >
            {disabled
              ? <Square className="size-3.5 fill-current" />
              : <ArrowUp className="size-4" />
            }
          </button>
        </div>
      </div>

      <p className="mt-1.5 text-center text-[10px] text-muted-foreground/50">
        {t('inputHint')}
      </p>
    </div>
  )
}
