import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'

export interface ChatSession {
  id: string
  user_email: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface SourceChunk {
  document_name: string
  chunk_index: number
  excerpt: string
  page_number: number | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: SourceChunk[]
  created_at: string
}

export interface SessionWithMessages extends ChatSession {
  messages: ChatMessage[]
}

export function useChatSessions() {
  return useQuery<ChatSession[]>({
    queryKey: ['sessions'],
    queryFn: async () => {
      const res = await api.get('/hr/sessions')
      return res.data
    },
  })
}

export function useChatSession(sessionId: string) {
  return useQuery<SessionWithMessages>({
    queryKey: ['session', sessionId],
    queryFn: async () => {
      const res = await api.get(`/hr/sessions/${sessionId}`)
      return res.data
    },
    enabled: !!sessionId,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
  })
}

export function useCreateSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post('/hr/sessions').then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  })
}

export function useDeleteSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) => api.delete(`/hr/sessions/${sessionId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  })
}
