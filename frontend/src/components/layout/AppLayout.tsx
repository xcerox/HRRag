import { Outlet, useParams } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useChatSession } from '@/hooks/useChat'

function Header() {
  const { sessionId } = useParams<{ sessionId?: string }>()
  const { data: session } = useChatSession(sessionId ?? '')

  if (!sessionId || !session?.title) return null

  return (
    <div className="shrink-0 h-11 px-4 flex items-center border-b border-border bg-background">
      <span className="text-sm text-foreground font-medium truncate">{session.title}</span>
    </div>
  )
}

export default function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <div className="flex-1 min-h-0">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
