'use client'

import { useState } from 'react'
import { Download, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react'

import { ArtifactJobResult, ArtifactFile } from '@/lib/types/artifacts'
import { artifactsApi } from '@/lib/api/artifacts'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useTranslation } from '@/lib/hooks/use-translation'

// ─── Per-mime renderers ───────────────────────────────────────────────────────

function MarkdownRenderer({ url }: { url: string }) {
  const [text, setText] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Lazy-load the text on first render
  if (text === null && !loading && !error) {
    setLoading(true)
    fetch(url)
      .then((r) => r.text())
      .then((t) => {
        setText(t)
        setLoading(false)
      })
      .catch(() => {
        setError('Could not load file.')
        setLoading(false)
      })
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (error) return <p className="text-sm text-destructive">{error}</p>

  return (
    <pre className="rounded bg-muted/40 p-4 text-xs whitespace-pre-wrap overflow-auto max-h-[50vh] font-mono">
      {text}
    </pre>
  )
}

function HtmlRenderer({ url }: { url: string }) {
  return (
    <iframe
      src={url}
      sandbox="allow-scripts allow-same-origin"
      className="w-full rounded border"
      style={{ minHeight: '50vh' }}
      title="Artifact HTML preview"
    />
  )
}

function ImageRenderer({ url, alt }: { url: string; alt: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={alt}
      className="max-w-full rounded border mx-auto block"
    />
  )
}

function VideoRenderer({ url }: { url: string }) {
  return (
    <video
      controls
      src={url}
      className="w-full rounded border"
      style={{ maxHeight: '60vh' }}
    />
  )
}

function JsonRenderer({ url }: { url: string }) {
  const [json, setJson] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (json === null && !loading && !error) {
    setLoading(true)
    fetch(url)
      .then((r) => r.json())
      .then((d) => {
        setJson(d)
        setLoading(false)
      })
      .catch(() => {
        setError('Could not load JSON.')
        setLoading(false)
      })
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>
  if (error) return <p className="text-sm text-destructive">{error}</p>

  return (
    <pre className="rounded bg-muted/40 p-4 text-xs whitespace-pre-wrap overflow-auto max-h-[50vh] font-mono">
      {JSON.stringify(json, null, 2)}
    </pre>
  )
}

function DownloadOnlyRenderer({ file, t }: { file: ArtifactFile; t: (key: string) => string }) {
  const isPptx =
    file.mime_type ===
    'application/vnd.openxmlformats-officedocument.presentationml.presentation'

  const downloadHref = artifactsApi.downloadUrl(file.path)

  return (
    <div className="flex flex-col items-center gap-3 py-6">
      <p className="text-sm text-muted-foreground">
        This file type cannot be previewed in the browser.
      </p>
      <div className="flex flex-wrap gap-2 justify-center">
        <Button asChild variant="default" size="sm">
          <a href={downloadHref} download>
            <Download className="mr-2 h-4 w-4" />
            {t('artifacts.download')}
          </a>
        </Button>
        {isPptx ? (
          <Button asChild variant="outline" size="sm">
            <a href={`ms-powerpoint:ofe|u|${downloadHref}`}>
              <ExternalLink className="mr-2 h-4 w-4" />
              {t('artifacts.openInPowerPoint')}
            </a>
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function FilePreview({ file, artifact }: { file: ArtifactFile; artifact: ArtifactJobResult }) {
  const { t } = useTranslation()
  const downloadHref = artifactsApi.downloadUrl(file.path)
  const mime = file.mime_type

  const renderContent = () => {
    if (mime === 'text/markdown') {
      return <MarkdownRenderer url={downloadHref} />
    }
    if (mime === 'text/html') {
      return <HtmlRenderer url={downloadHref} />
    }
    if (mime.startsWith('image/')) {
      return <ImageRenderer url={downloadHref} alt={artifact.title ?? 'Artifact image'} />
    }
    if (mime === 'video/mp4') {
      return <VideoRenderer url={downloadHref} />
    }
    if (mime === 'application/json') {
      return <JsonRenderer url={downloadHref} />
    }
    // Word / Excel / PPTX / unknown
    return <DownloadOnlyRenderer file={file} t={t} />
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <Badge variant="outline" className="text-xs uppercase tracking-wide">
          {mime.split('/')[1]}
        </Badge>
        <Button asChild variant="ghost" size="sm" className="h-7 text-xs gap-1">
          <a href={downloadHref} download onClick={(e) => e.stopPropagation()}>
            <Download className="h-3 w-3" />
            {t('artifacts.download')}
          </a>
        </Button>
      </div>
      {renderContent()}
    </div>
  )
}

// ─── Provenance block ─────────────────────────────────────────────────────────

function ProvenanceBlock({ artifact }: { artifact: ArtifactJobResult }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  const p = artifact.provenance
  if (!p) return null

  return (
    <div className="border rounded-md overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-left bg-muted/40 hover:bg-muted/60 transition-colors"
      >
        <span>{t('artifacts.provenance')}</span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {open ? (
        <div className="px-4 py-3 space-y-2 text-xs text-muted-foreground bg-background">
          <div className="grid grid-cols-2 gap-1.5">
            {p.provider ? (
              <>
                <span className="font-medium text-foreground">Provider</span>
                <span>{p.provider}</span>
              </>
            ) : null}
            {p.model_id ? (
              <>
                <span className="font-medium text-foreground">Model</span>
                <span className="truncate">{p.model_id}</span>
              </>
            ) : null}
            {p.call_count !== undefined ? (
              <>
                <span className="font-medium text-foreground">LLM calls</span>
                <span>{p.call_count}</span>
              </>
            ) : null}
            {p.total_tokens !== undefined ? (
              <>
                <span className="font-medium text-foreground">Total tokens</span>
                <span>{p.total_tokens.toLocaleString()}</span>
              </>
            ) : null}
          </div>

          {p.calls && p.calls.length > 0 ? (
            <details>
              <summary className="cursor-pointer font-medium text-foreground">
                {p.calls.length} call{p.calls.length !== 1 ? 's' : ''}
              </summary>
              <div className="mt-2 space-y-1.5">
                {p.calls.map((call, i) => (
                  <div key={i} className="rounded bg-muted/40 p-2 space-y-0.5">
                    <p>
                      <span className="font-medium text-foreground">in:</span>{' '}
                      {call.tokens_in?.toLocaleString() ?? '—'} tokens
                    </p>
                    <p>
                      <span className="font-medium text-foreground">out:</span>{' '}
                      {call.tokens_out?.toLocaleString() ?? '—'} tokens
                    </p>
                    <p>
                      <span className="font-medium text-foreground">latency:</span>{' '}
                      {call.latency_ms ? `${call.latency_ms}ms` : '—'}
                    </p>
                  </div>
                ))}
              </div>
            </details>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

// ─── Main dialog ──────────────────────────────────────────────────────────────

interface ArtifactPreviewProps {
  artifact: ArtifactJobResult | null
  open: boolean
  onClose: () => void
}

export function ArtifactPreview({ artifact, open, onClose }: ArtifactPreviewProps) {
  const { t } = useTranslation()

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="w-[min(92vw,860px)] max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span className="truncate">{artifact?.title ?? artifact?.artifact_type ?? 'Artifact'}</span>
            {artifact?.artifact_type ? (
              <Badge variant="secondary" className="text-xs capitalize">
                {artifact.artifact_type.replace(/_/g, ' ')}
              </Badge>
            ) : null}
          </DialogTitle>
          {artifact?.summary ? (
            <DialogDescription className="text-xs line-clamp-2">
              {artifact.summary}
            </DialogDescription>
          ) : null}
        </DialogHeader>

        <ScrollArea className="flex-1 pr-1 overflow-auto">
          {artifact ? (
            <div className="space-y-4 pb-2">
              {/* File previews */}
              {artifact.files && artifact.files.length > 0 ? (
                <div className="space-y-4">
                  {artifact.files.map((file, idx) => (
                    <FilePreview key={idx} file={file} artifact={artifact} />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-6">
                  {t('common.noResults')}
                </p>
              )}

              {/* Provenance */}
              <ProvenanceBlock artifact={artifact} />
            </div>
          ) : null}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}
