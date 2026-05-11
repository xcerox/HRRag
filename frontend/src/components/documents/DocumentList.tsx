import { FileText, Trash2, Loader2, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useDocuments, useDeleteDocument } from '@/hooks/useDocuments'

const statusIcon: Record<string, React.ReactNode> = {
  indexed: <CheckCircle2 className="size-3.5 text-green-500 shrink-0" />,
  indexing: <Loader2 className="size-3.5 text-primary animate-spin shrink-0" />,
  pending: <Clock className="size-3.5 text-yellow-500 shrink-0" />,
  error: <AlertCircle className="size-3.5 text-destructive shrink-0" />,
}

export default function DocumentList() {
  const { data: docs } = useDocuments()
  const del = useDeleteDocument()
  const { t } = useTranslation('documents')

  if (!docs || docs.length === 0) {
    return <p className="p-2 text-xs text-muted-foreground">{t('noDocuments')}</p>
  }

  return (
    <div className="space-y-1 mt-1">
      {docs.map((doc) => (
        <div key={doc.id} className="flex items-center gap-1.5 px-2 py-1.5 rounded-md hover:bg-muted group text-sm">
          <FileText className="size-3.5 text-muted-foreground shrink-0" />
          <span className="flex-1 truncate text-sidebar-foreground min-w-0 text-xs">{doc.original_name}</span>
          {statusIcon[doc.status] || null}
          <Button
            variant="ghost"
            size="icon"
            className="size-5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
            onClick={() => del.mutate(doc.id)}
          >
            <Trash2 className="size-3" />
          </Button>
        </div>
      ))}
    </div>
  )
}
