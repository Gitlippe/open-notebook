'use client'

import { useCallback, useEffect, useState } from 'react'
import { Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'

import { useArtifactTypes, useGenerateArtifact, useArtifactJob } from '@/lib/hooks/use-artifacts'
import { useArtifactsStore } from '@/lib/stores/artifacts-store'
import { useNotebooks } from '@/lib/hooks/use-notebooks'
import { ArtifactType, ArtifactJobResult } from '@/lib/types/artifacts'
import { artifactsApi } from '@/lib/api/artifacts'
import { ArtifactTypeSelector } from './ArtifactTypeSelector'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useTranslation } from '@/lib/hooks/use-translation'
import { cn } from '@/lib/utils'

type Step = 'type' | 'sources' | 'config' | 'progress'

// ─── Per-type optional config fields ─────────────────────────────────────────

const TYPE_CONFIG_FIELDS: Record<string, Array<{ key: string; label: string; type: string; placeholder?: string }>> = {
  flashcards:  [{ key: 'max_items', label: 'Max cards',   type: 'number', placeholder: '20' }],
  quiz:        [{ key: 'max_items', label: 'Max questions', type: 'number', placeholder: '10' }],
  timeline:    [{ key: 'max_items', label: 'Max events',  type: 'number', placeholder: '15' }],
  slide_deck:  [{ key: 'max_items', label: 'Max slides',  type: 'number', placeholder: '12' }],
  pitch_deck:  [{ key: 'max_items', label: 'Max slides',  type: 'number', placeholder: '10' }],
  faq:         [{ key: 'max_items', label: 'Max Q&A pairs', type: 'number', placeholder: '15' }],
  study_guide: [{ key: 'max_items', label: 'Max sections', type: 'number', placeholder: '8' }],
  data_tables: [{ key: 'max_items', label: 'Max rows',    type: 'number', placeholder: '50' }],
}

// ─── Steps ────────────────────────────────────────────────────────────────────

function StepIndicator({ current }: { current: Step }) {
  const steps: { id: Step; label: string }[] = [
    { id: 'type',     label: '1. Type' },
    { id: 'sources',  label: '2. Sources' },
    { id: 'config',   label: '3. Configure' },
    { id: 'progress', label: '4. Generate' },
  ]

  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground mb-2">
      {steps.map((step) => (
        <span
          key={step.id}
          className={cn(
            'px-2 py-0.5 rounded-full',
            current === step.id
              ? 'bg-primary text-primary-foreground font-medium'
              : 'bg-muted'
          )}
        >
          {step.label}
        </span>
      ))}
    </div>
  )
}

// ─── Progress view ────────────────────────────────────────────────────────────

function ProgressView({
  jobId,
  artifactType,
  onComplete,
}: {
  jobId: string
  artifactType: string
  onComplete: (result: ArtifactJobResult) => void
}) {
  const { t } = useTranslation()
  const { job } = useArtifactJob(jobId)
  const { addCompletedArtifact } = useArtifactsStore()
  const [elapsed, setElapsed] = useState(0)
  const [notifiedDone, setNotifiedDone] = useState(false)

  // Tick elapsed seconds
  useEffect(() => {
    const interval = setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => clearInterval(interval)
  }, [])

  // Fire onComplete exactly once when the job reaches a terminal status
  useEffect(() => {
    if (!job || notifiedDone) return
    if (job.status === 'completed' || job.status === 'failed' || job.status === 'error') {
      setNotifiedDone(true)
      if (job.status === 'completed') {
        addCompletedArtifact(job)
        onComplete(job)
      }
    }
  }, [job, notifiedDone, addCompletedArtifact, onComplete])

  const status = job?.status ?? 'submitted'
  const isRunning = status === 'submitted' || status === 'running' || status === 'processing'
  const isComplete = status === 'completed'
  const isFailed = status === 'failed' || status === 'error'

  return (
    <div className="space-y-4 py-4">
      <div className="flex items-start gap-3">
        {isRunning ? (
          <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-primary" />
        ) : isComplete ? (
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
        ) : (
          <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
        )}

        <div className="space-y-1 flex-1 min-w-0">
          <p className="text-sm font-medium">
            {isRunning
              ? t('artifacts.generating')
              : isComplete
              ? t('artifacts.completed')
              : t('artifacts.failed')}
          </p>
          <p className="text-xs text-muted-foreground capitalize">
            {artifactType.replace(/_/g, ' ')}
          </p>
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {elapsed}s
          </p>
        </div>
      </div>

      {isFailed && job?.error_message ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/30">
          <p className="text-xs text-red-700 dark:text-red-400 whitespace-pre-wrap">
            {job.error_message}
          </p>
        </div>
      ) : null}

      {isComplete && job?.files && job.files.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-foreground uppercase tracking-wide">
            Files
          </p>
          {job.files.map((file, idx) => (
            <div key={idx} className="flex items-center justify-between gap-2 rounded border px-3 py-2 text-xs">
              <span className="truncate text-muted-foreground">{file.name ?? file.path.split('/').pop()}</span>
              <Button asChild variant="outline" size="sm" className="h-6 text-xs shrink-0 gap-1">
                <a href={artifactsApi.downloadUrl(file.path)} download>
                  {t('artifacts.download')}
                </a>
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

// ─── Main dialog ──────────────────────────────────────────────────────────────

interface GenerateArtifactDialogProps {
  open: boolean
  onClose: () => void
  defaultNotebookId?: string
  onArtifactReady?: (artifact: ArtifactJobResult) => void
}

export function GenerateArtifactDialog({
  open,
  onClose,
  defaultNotebookId,
  onArtifactReady,
}: GenerateArtifactDialogProps) {
  const { t } = useTranslation()
  const { types, isLoading: loadingTypes } = useArtifactTypes()
  const generateMutation = useGenerateArtifact()
  const { data: notebooks } = useNotebooks()

  const [step, setStep] = useState<Step>('type')
  const [selectedType, setSelectedType] = useState<ArtifactType | null>(null)
  const [notebookId, setNotebookId] = useState<string>(defaultNotebookId ?? '')
  const [inlineContent, setInlineContent] = useState('')
  const [title, setTitle] = useState('')
  const [configValues, setConfigValues] = useState<Record<string, string>>({})
  const [activeJobId, setActiveJobId] = useState<string | null>(null)

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setStep('type')
      setSelectedType(null)
      setNotebookId(defaultNotebookId ?? '')
      setInlineContent('')
      setTitle('')
      setConfigValues({})
      setActiveJobId(null)
    }
  }, [open, defaultNotebookId])

  const handleClose = () => {
    onClose()
  }

  const handleTypeSelect = (type: ArtifactType) => {
    setSelectedType(type)
  }

  const handleNextFromType = () => {
    if (selectedType) setStep('sources')
  }

  const handleNextFromSources = () => {
    if (notebookId || inlineContent.trim()) setStep('config')
  }

  const handleGenerate = () => {
    if (!selectedType) return

    const config: Record<string, unknown> = {}
    const fields = TYPE_CONFIG_FIELDS[selectedType.id] ?? []
    for (const field of fields) {
      const val = configValues[field.key]
      if (val) {
        config[field.key] = field.type === 'number' ? Number(val) : val
      }
    }

    generateMutation.mutate(
      {
        artifact_type: selectedType.id,
        notebook_id: notebookId || undefined,
        content: !notebookId && inlineContent ? inlineContent : undefined,
        title: title || undefined,
        config: Object.keys(config).length > 0 ? config : undefined,
      },
      {
        onSuccess: (data) => {
          setActiveJobId(data.job_id)
          setStep('progress')
        },
      }
    )
  }

  const handleArtifactComplete = useCallback(
    (artifact: ArtifactJobResult) => {
      onArtifactReady?.(artifact)
    },
    [onArtifactReady]
  )

  const configFields = selectedType ? (TYPE_CONFIG_FIELDS[selectedType.id] ?? []) : []

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose() }}>
      <DialogContent className="w-[min(92vw,680px)] max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>{t('artifacts.newArtifact')}</DialogTitle>
          <DialogDescription>
            {step === 'type'     && t('artifacts.pickType')}
            {step === 'sources'  && t('artifacts.selectSources')}
            {step === 'config'   && t('artifacts.configure')}
            {step === 'progress' && (selectedType?.label ?? t('artifacts.generating'))}
          </DialogDescription>
        </DialogHeader>

        <StepIndicator current={step} />

        <ScrollArea className="flex-1 pr-1 overflow-auto">
          {/* Step 1 — Type */}
          {step === 'type' ? (
            <ArtifactTypeSelector
              types={types}
              selected={selectedType?.id ?? null}
              onSelect={handleTypeSelect}
              disabled={loadingTypes}
            />
          ) : null}

          {/* Step 2 — Sources */}
          {step === 'sources' ? (
            <div className="space-y-4 py-1">
              <div className="space-y-1.5">
                <Label htmlFor="notebook-select">Notebook (optional)</Label>
                <Select
                  value={notebookId}
                  onValueChange={setNotebookId}
                >
                  <SelectTrigger id="notebook-select">
                    <SelectValue placeholder="Select a notebook…" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">None</SelectItem>
                    {(notebooks ?? []).map((nb) => (
                      <SelectItem key={nb.id} value={nb.id}>
                        {nb.name ?? nb.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {!notebookId ? (
                <div className="space-y-1.5">
                  <Label htmlFor="inline-content">
                    Paste content
                    <span className="ml-1 text-xs text-muted-foreground">(if no notebook)</span>
                  </Label>
                  <Textarea
                    id="inline-content"
                    value={inlineContent}
                    onChange={(e) => setInlineContent(e.target.value)}
                    placeholder="Paste your source text here…"
                    rows={8}
                    className="font-mono text-xs"
                  />
                </div>
              ) : null}
            </div>
          ) : null}

          {/* Step 3 — Config */}
          {step === 'config' ? (
            <div className="space-y-4 py-1">
              <div className="space-y-1.5">
                <Label htmlFor="artifact-title">
                  {t('common.title')}
                  <span className="ml-1 text-xs text-muted-foreground">({t('common.optional')})</span>
                </Label>
                <Input
                  id="artifact-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={`${selectedType?.label ?? 'Artifact'} title…`}
                />
              </div>

              {configFields.map((field) => (
                <div key={field.key} className="space-y-1.5">
                  <Label htmlFor={`cfg-${field.key}`}>{field.label}</Label>
                  <Input
                    id={`cfg-${field.key}`}
                    type={field.type}
                    value={configValues[field.key] ?? ''}
                    onChange={(e) =>
                      setConfigValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                    }
                    placeholder={field.placeholder ?? ''}
                    min={field.type === 'number' ? 1 : undefined}
                  />
                </div>
              ))}

              <div className="rounded-md border bg-muted/30 px-4 py-3 text-xs space-y-1 text-muted-foreground">
                <p className="font-semibold text-foreground text-sm">Summary</p>
                <p>Type: <span className="text-foreground capitalize">{selectedType?.label}</span></p>
                {notebookId ? (
                  <p>Source: <span className="text-foreground">Notebook</span></p>
                ) : (
                  <p>Source: <span className="text-foreground">Inline content ({inlineContent.length} chars)</span></p>
                )}
              </div>
            </div>
          ) : null}

          {/* Step 4 — Progress */}
          {step === 'progress' && activeJobId ? (
            <ProgressView
              jobId={activeJobId}
              artifactType={selectedType?.id ?? ''}
              onComplete={handleArtifactComplete}
            />
          ) : null}
        </ScrollArea>

        {/* Footer buttons */}
        <div className="flex justify-between gap-2 pt-2 border-t">
          {step !== 'progress' ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={step === 'type' ? handleClose : () => setStep(
                  step === 'sources' ? 'type' : step === 'config' ? 'sources' : 'type'
                )}
              >
                {step === 'type' ? t('common.cancel') : t('common.back')}
              </Button>

              {step === 'type' ? (
                <Button
                  size="sm"
                  disabled={!selectedType}
                  onClick={handleNextFromType}
                >
                  {t('common.next')}
                </Button>
              ) : step === 'sources' ? (
                <Button
                  size="sm"
                  disabled={!notebookId && !inlineContent.trim()}
                  onClick={handleNextFromSources}
                >
                  {t('common.next')}
                </Button>
              ) : step === 'config' ? (
                <Button
                  size="sm"
                  disabled={generateMutation.isPending}
                  onClick={handleGenerate}
                >
                  {generateMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('artifacts.generating')}
                    </>
                  ) : (
                    t('artifacts.generate')
                  )}
                </Button>
              ) : null}
            </>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="ml-auto"
              onClick={handleClose}
            >
              {t('common.done')}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
