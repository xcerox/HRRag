import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'

export interface Document {
  id: string
  user_email: string
  original_name: string
  file_size: number | null
  mime_type: string | null
  chunks_count: number
  status: 'pending' | 'indexing' | 'indexed' | 'error'
  created_at: string
}

export function useDocuments() {
  return useQuery<Document[]>({
    queryKey: ['documents'],
    queryFn: async () => {
      const res = await api.get('/hr/documents')
      return res.data
    },
    refetchInterval: (query) => {
      const docs = query.state.data
      if (docs?.some((d) => d.status === 'indexing')) return 3000
      return false
    },
  })
}

export function useUploadDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.post('/hr/documents', form).then((r) => r.data)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })
}

export function useDeleteDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (docId: string) => api.delete(`/hr/documents/${docId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })
}
