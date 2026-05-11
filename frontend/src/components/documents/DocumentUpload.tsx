import { useRef } from 'react'
import { Upload } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useUploadDocument } from '@/hooks/useDocuments'

export default function DocumentUpload() {
  const upload = useUploadDocument()
  const inputRef = useRef<HTMLInputElement>(null)
  const { t } = useTranslation('documents')

  function handleFiles(files: FileList | null) {
    if (!files) return
    Array.from(files).forEach((f) => upload.mutate(f))
  }

  function openFilePicker() {
    inputRef.current?.click()
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      inputRef.current?.click()
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onDrop={(e) => { e.preventDefault(); handleFiles(e.dataTransfer.files) }}
      onDragOver={(e) => e.preventDefault()}
      onClick={openFilePicker}
      onKeyDown={handleKeyDown}
      className="border-2 border-dashed border-border rounded-lg p-3 text-center hover:border-primary transition-colors cursor-pointer"
    >
      <Upload className="size-5 mx-auto mb-1 text-muted-foreground" />
      <p className="text-xs text-muted-foreground">{t('upload')}</p>
      <p className="text-[10px] text-muted-foreground">{t('supportedFormats')}</p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt,.md"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  )
}
