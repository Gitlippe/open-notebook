'use client'

import { formatDistanceToNow } from 'date-fns'
import { Download, ExternalLink } from 'lucide-react'

import { ArtifactJobResult } from '@/lib/types/artifacts'
import { artifactsApi } from '@/lib/api/artifacts'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useTranslation } from '@/lib/hooks/use-translation'
import { getDateLocale } from '@/lib/utils/date-locale'
import { cn } from '@/lib/utils'

// Human-readable labels for MIME types
function mimeLabel(mimeType: string): string {
  const map: Record<string, string> = {
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
    'application/json': 'JSON',
    'text/markdown': 'Markdown',
    'text/html': 'HTML',
    'image/png': 'PNG',
    'image/svg+xml': 'SVG',
    'video/mp4': 'MP4',
    'application/zip': 'ZIP',
    'application/octet-stream': 'File',
  }
  return map[mimeType] ?? mimeType.split('/')[1]?.toUpperCase() ?? 'File'
}

interface ArtifactCardProps {
  artifact: ArtifactJobResult
  onOpenPreview?: (artifact: ArtifactJobResult) => void
  className?: string
}

export function ArtifactCard({ artifact, onOpenPreview, className }: ArtifactCardProps) {
  const { t, language } = useTranslation()

  const distance = artifact.created_at
    ? formatDistanceToNow(new Date(artifact.created_at), {
        addSuffix: true,
        locale: getDateLocale(language),
      })
    : null

  const handleCardClick = () => {
    onOpenPreview?.(artifact)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onOpenPreview?.(artifact)
    }
  }

  return (
    <Card
      className={cn(
        'shadow-sm transition-shadow hover:shadow-md',
        onOpenPreview && 'cursor-pointer',
        className
      )}
      onClick={onOpenPreview ? handleCardClick : undefined}
      onKeyDown={onOpenPreview ? handleKeyDown : undefined}
      role={onOpenPreview ? 'button' : undefined}
      tabIndex={onOpenPreview ? 0 : undefined}
    >
      <CardContent className="p-4 space-y-3">
        {/* Header row */}
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-1 flex-1 min-w-0">
            <h3 className="text-sm font-semibold leading-tight text-foreground truncate">
              {artifact.title ?? artifact.artifact_type}
            </h3>
            {distance ? (
              <p className="text-xs text-muted-foreground">
                {t('common.created').replace('{time}', distance)}
              </p>
            ) : null}
          </div>
          <Badge variant="secondary" className="shrink-0 text-xs capitalize">
            {artifact.artifact_type.replace(/_/g, ' ')}
          </Badge>
        </div>

        {/* Summary */}
        {artifact.summary ? (
          <p className="text-xs text-muted-foreground line-clamp-2">{artifact.summary}</p>
        ) : null}

        {/* Download buttons */}
        {artifact.files && artifact.files.length > 0 ? (
          <div
            className="flex flex-wrap gap-1.5"
            onClick={(e) => e.stopPropagation()}
          >
            {artifact.files.map((file, index) => {
              const isPptx =
                file.mime_type ===
                'application/vnd.openxmlformats-officedocument.presentationml.presentation'

              return (
                <div key={index} className="flex gap-1">
                  <Button
                    asChild
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs gap-1"
                  >
                    <a
                      href={artifactsApi.downloadUrl(file.path)}
                      download
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Download className="h-3 w-3" />
                      {file.name ?? mimeLabel(file.mime_type)}
                    </a>
                  </Button>
                  {isPptx ? (
                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs gap-1"
                    >
                      <a
                        href={`ms-powerpoint:ofe|u|${artifactsApi.downloadUrl(file.path)}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="h-3 w-3" />
                        {t('artifacts.openInPowerPoint')}
                      </a>
                    </Button>
                  ) : null}
                </div>
              )
            })}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
