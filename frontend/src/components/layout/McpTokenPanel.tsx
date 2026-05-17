import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Copy, Check, Terminal, ChevronDown } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

export default function McpTokenPanel() {
  const { t } = useTranslation('common')
  const token = useAuthStore((s) => s.token)
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!token) return null

  async function handleCopy() {
    await navigator.clipboard.writeText(token!)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="px-2 py-1.5">
      {/* Header — always visible */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-2 py-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-border/60 transition-all duration-100"
      >
        <div className="flex items-center gap-1.5">
          <Terminal className="size-3 shrink-0" />
          <span className="text-[10px] font-semibold uppercase tracking-widest">
            {t('mcp.title')}
          </span>
        </div>
        <ChevronDown
          className={`size-3 shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Collapsible body */}
      {open && (
        <div className="mt-1 rounded-lg border border-border bg-muted/40 p-2.5 space-y-2">
          <p className="text-[10px] text-muted-foreground leading-relaxed">
            {t('mcp.description')}
          </p>
          <div className="flex items-center gap-1.5 rounded-md border border-border bg-background px-2 py-1.5">
            <code className="flex-1 text-[9px] text-muted-foreground font-mono truncate">
              {token.slice(0, 28)}…
            </code>
            <button
              onClick={handleCopy}
              title={copied ? t('mcp.copied') : t('mcp.copy')}
              className="shrink-0 p-0.5 rounded text-muted-foreground hover:text-foreground transition-colors"
            >
              {copied
                ? <Check className="size-3 text-green-500" />
                : <Copy className="size-3" />
              }
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
