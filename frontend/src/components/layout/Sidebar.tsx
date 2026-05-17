import { useNavigate } from 'react-router-dom'
import { Plus, LogOut, Trash2, FileSearch, MessageSquarePlus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useAuthStore } from '@/store/authStore'
import { useChatSessions, useCreateSession, useDeleteSession } from '@/hooks/useChat'
import { useChatStore } from '@/store/chatStore'
import DocumentList from '@/components/documents/DocumentList'
import DocumentUpload from '@/components/documents/DocumentUpload'
import McpTokenPanel from './McpTokenPanel'
import ThemeToggle from './ThemeToggle'
import LanguageSwitcher from './LanguageSwitcher'
import { cn } from '@/lib/utils'

export default function Sidebar() {
  const navigate = useNavigate()
  const { logout, email } = useAuthStore()
  const { activeSessionId, setActiveSession } = useChatStore()
  const { t: tc } = useTranslation('common')
  const { t: tch } = useTranslation('chat')

  const { data: sessions } = useChatSessions()
  const createSession = useCreateSession()
  const deleteSession = useDeleteSession()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  async function handleNewSession() {
    if (sessions && sessions.length > 0) {
      const last = sessions[0]
      if (!last.title) {
        navigate(`/sessions/${last.id}`)
        setActiveSession(last.id)
        return
      }
    }
    const session = await createSession.mutateAsync()
    navigate(`/sessions/${session.id}`)
    setActiveSession(session.id)
  }

  async function handleDeleteSession(sessionId: string) {
    await deleteSession.mutateAsync(sessionId)
    if (activeSessionId === sessionId) {
      navigate('/')
      setActiveSession(null)
    }
  }

  return (
    <aside className="flex flex-col h-full w-60 bg-sidebar border-r border-border shrink-0">
      {/* Header */}
      <div className="shrink-0 px-4 py-4 flex items-center gap-2.5">
        <div className="size-7 rounded-lg flex items-center justify-center bg-primary text-primary-foreground shrink-0">
          <FileSearch className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0">
          <h1 className="font-display text-base leading-tight text-foreground">HRRag</h1>
          <p className="text-[10px] text-muted-foreground truncate">{email}</p>
        </div>
      </div>

      <Separator className="shrink-0" />

      {/* Documents */}
      <div className="shrink-0 px-2 py-2">
        <p className="px-2 py-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          {tc('documents')}
        </p>
        <div className="max-h-48 overflow-y-auto">
          <DocumentList />
        </div>
        <div className="mt-2">
          <DocumentUpload />
        </div>
      </div>

      <Separator className="shrink-0 my-1" />

      {/* Sessions */}
      <div className="flex-1 min-h-0 overflow-y-auto px-2 py-1">
        <div className="flex items-center justify-between px-2 py-1">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
            {tc('conversations')}
          </p>
          <Button
            variant="ghost"
            size="icon"
            className="size-5 text-muted-foreground hover:text-foreground"
            onClick={handleNewSession}
            disabled={createSession.isPending}
            title={tch('newSession')}
          >
            <MessageSquarePlus className="size-3.5" />
          </Button>
        </div>

        {(!sessions || sessions.length === 0) && (
          <p className="px-2 py-2 text-xs text-muted-foreground">{tch('noSessions')}</p>
        )}

        {sessions?.map((session) => (
          <div
            key={session.id}
            className={cn(
              'w-full flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs group cursor-pointer transition-all duration-100',
              activeSessionId === session.id
                ? 'bg-active-subtle text-active-subtle-foreground font-medium'
                : 'text-sidebar-foreground hover:bg-border/60'
            )}
          >
            <button
              className="flex-1 text-left truncate"
              onClick={() => {
                setActiveSession(session.id)
                navigate(`/sessions/${session.id}`)
              }}
            >
              {session.title ?? tch('newSession')}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); handleDeleteSession(session.id) }}
              className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0 text-muted-foreground hover:text-destructive p-0.5"
              title={tc('delete')}
            >
              <Trash2 className="size-3" />
            </button>
          </div>
        ))}

        <button
          className="w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs
            text-muted-foreground hover:text-foreground hover:bg-border/60
            transition-all duration-100 mt-0.5"
          onClick={handleNewSession}
          disabled={createSession.isPending}
        >
          <Plus className="size-3 shrink-0" />
          {tch('newSession')}
        </button>
      </div>

      <Separator className="shrink-0" />

      {/* MCP Token */}
      <McpTokenPanel />

      <Separator className="shrink-0" />

      {/* Footer */}
      <div className="shrink-0 px-3 py-2 flex items-center justify-between">
        <button
          onClick={handleLogout}
          title={tc('logout')}
          className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-border/60 transition-all"
        >
          <LogOut className="size-4" />
        </button>
        <div className="flex items-center gap-1">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </aside>
  )
}
