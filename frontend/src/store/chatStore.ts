import { create } from 'zustand'

interface ChatState {
  activeSessionId: string | null
  isStreaming: boolean
  setActiveSession: (id: string | null) => void
  setStreaming: (v: boolean) => void
}

export const useChatStore = create<ChatState>()((set) => ({
  activeSessionId: null,
  isStreaming: false,
  setActiveSession: (id) => set({ activeSessionId: id }),
  setStreaming: (v) => set({ isStreaming: v }),
}))
